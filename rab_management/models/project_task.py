from odoo import models, fields, api


class ProjectTask(models.Model):
    _inherit = 'project.task'

    purchase_order_id = fields.Many2one(
        'purchase.order',
        string='Purchase Order',
        tracking=True
    )
    product_id = fields.Many2one(
        'product.product',
        string='Material',
        domain=[('categ_id.name','=','Material')]
    )
    massa_jenis = fields.Float(
        string='Massa Jenis',
        related='product_id.massa_jenis',
        readonly=True,
        store=False
    )
    qty = fields.Float(
        string='Quantity',
        default=1.0,
        digits=(16, 2)
    )



    panjang = fields.Float(string='Panjang', digits=(16, 2))
    lebar = fields.Float(string='Lebar', digits=(16, 2))
    tebal = fields.Float(string='Tebal', digits=(16, 2))

    weight = fields.Float(
        string='Weight (kg)',
        compute='_compute_weight',
        store=True
    )

    panjang_las = fields.Float(
        string='Panjang Las',
        compute='_compute_panjang_las',
        store=True
    )

    material_needed_ids = fields.One2many(
        'project.task.material',
        'task_id',
        string='Material Needed'
    )

    def _get_all_parents(self):
        parents = self.env['project.task']
        current = self.parent_id
        while current:
            parents |= current
            current = current.parent_id
        return parents

    def _get_task_path(self):
        parts = []
        current = self
        while current:
            parts.append(current.name or str(current.id))
            current = current.parent_id
        return '/'.join(reversed(parts))


    # LOGIC WEIGHT
    @api.depends(
        'product_id',
        'product_id.massa_jenis',
        'panjang',
        'lebar',
        'tebal',
        'qty'
    )
    def _compute_weight(self):
        for rec in self:
            rec.weight = 0.0

            if not rec.product_id:
                continue

            kode = (rec.product_id.default_code or '').upper()
            faktor = rec.product_id.massa_jenis or 0.0
            qty = rec.qty or 0.0

            panjang = rec.panjang or 0.0
            lebar   = rec.lebar or 0.0
            tebal   = rec.tebal or 0.0

            if kode.startswith('P'):
                # PLAT → kg/mm³
                rec.weight = panjang * lebar * tebal * faktor * qty

            else:
                # PROFIL → kg/m → convert mm → m
                rec.weight = (panjang / 1000.0) * faktor * qty


    # LOGIC PANJANG LAS
    @api.depends('product_id', 'panjang', 'lebar', 'qty')
    def _compute_panjang_las(self):
        for rec in self:
            if not rec.product_id:
                rec.panjang_las = 0
                continue

            kode = (rec.product_id.default_code or '').upper()
            qty = rec.qty or 0

            if kode.startswith('P'):
                rec.panjang_las = 4 * (rec.panjang + rec.lebar) * qty
            else:
                rec.panjang_las = rec.panjang * qty

    


    def action_sync_material_from_subtask(self):
        if self.env.context.get('skip_material_sync'):
            return

        for task in self:
            material_map = {}

            # mulai dari task utama, level 1
            self._collect_material_3_level(
                root_task=task,
                current_task=task,
                level=1,
                material_map=material_map
            )

            # hapus hasil sync lama
            task.material_needed_ids.filtered(
                lambda m: m.source == 'subtask'
            ).unlink()

            # create ulang hasil baru
            for data in material_map.values():
                self.env['project.task.material'].with_context(
                    skip_material_sync=True
                ).create({
                    'task_id': task.id,
                    **data,
                    'source': 'subtask',
                })



    def _collect_material_3_level(self, root_task, current_task, level, material_map):
        if level > 3:
            return

        for child in current_task.child_ids:
            if child.product_id:
                key = (child.product_id.id, level)

                material_map.setdefault(key, {
                    'product_id': child.product_id.id,
                    'total_qty': 0.0,
                    'weight': 0.0,
                    'source_task_id': child.id,
                    'source_level': (
                        'level_1' if level == 1 else
                        'level_2' if level == 2 else
                        'level_3'
                    ),

                    'source_path': child._get_task_path(),
                })

                material_map[key]['total_qty'] += child.qty or 0.0
                material_map[key]['weight'] += child.weight or 0.0


            # lanjut ke level berikutnya
            self._collect_material_3_level(
                root_task,
                child,
                level + 1,
                material_map
            )


    @api.model
    def create(self, vals):
        record = super().create(vals)

        if record.parent_id:
            for parent in record._get_all_parents():
                parent.action_sync_material_from_subtask()

        return record



    def write(self, vals):
        if self.env.context.get('skip_material_sync'):
            return super().write(vals)

        parents = self.env['project.task']
        for rec in self:
            parents |= rec._get_all_parents()

        res = super().write(vals)

        if any(k in vals for k in ['product_id', 'qty', 'panjang', 'lebar', 'tebal']):
            parents.action_sync_material_from_subtask()

        return res




    def unlink(self):
        if self.env.context.get('skip_material_sync'):
            return super().unlink()

        parents = self.env['project.task']
        for rec in self:
            parents |= rec._get_all_parents()

        res = super().unlink()
        parents.action_sync_material_from_subtask()

        return res







