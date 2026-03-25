from odoo import models, fields, api
from odoo.exceptions import UserError


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
        string='Jumlah',
        default=1.0,
        digits=(16, 2)
    )

    job_type = fields.Selection(
        [
            ('primary', 'Utama'),
            ('additional', 'Tambahan'),
        ],
        string='Tipe Pekerjaan',
        default='primary',
        required=True
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        
        # Prioritize context for parent_id
        parent_id = self.env.context.get('default_parent_id') or self.env.context.get('parent_id')
        
        # Fallback to active_id if we are clearly in a subtask creation context from a task form
        if not parent_id and self.env.context.get('active_model') == 'project.task':
            parent_id = self.env.context.get('active_id')
            
        if parent_id:
            parent = self.env['project.task'].browse(parent_id)
            if parent.exists():
                res['job_type'] = parent.job_type
        return res

    @api.onchange('parent_id')
    def _onchange_parent_id_job_type(self):
        # Only set if it's a new record and parent is set
        if self.parent_id and not self._origin:
            self.job_type = self.parent_id.job_type



    panjang = fields.Float(string='Panjang', digits=(16, 2))
    lebar = fields.Float(string='Lebar', digits=(16, 2))
    tebal = fields.Float(string='Tebal', digits=(16, 2))

    weight = fields.Float(
        string='Berat (kg)',
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
    material_picking_id = fields.Many2one(
        'stock.picking',
        string='Delivery Order Konsumsi Material',
        readonly=True,
        copy=False
    )
    material_picking_id_state = fields.Selection(
        related='material_picking_id.state',
        string='Status Delivery',
        readonly=True,
        store=False
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
                # PLAT rumus kg/mm³
                rec.weight = panjang * lebar * tebal * faktor * qty

            else:
                # PROFIL  kg/m di convert mm ke m
                rec.weight = (panjang / 1000.0) * faktor * qty

            # Fallback jika rumus di atas menghasilkan 0 atau tidak terpenuhi (untuk item non-dimensi)
            if not rec.weight and rec.product_id.weight:
                rec.weight = rec.product_id.weight * qty


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
                rec.panjang_las = 4 * (rec.panjang + rec.lebar)
            else:
                rec.panjang_las = rec.panjang

    


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

    def action_create_material_consumption_picking(self):
        self.ensure_one()

        if self.material_picking_id and self.material_picking_id.state != 'cancel':
            raise UserError(
                f"Delivery Order sudah dibuat sebelumnya ({self.material_picking_id.name}). "
                "Batalkan delivery tersebut terlebih dahulu jika ingin membuat ulang."
            )

        lines = self.material_needed_ids.filtered(lambda m: (m.qty_actual or 0.0) > 0)
        if not lines:
            raise UserError("Tidak ada material dengan Jumlah Aktual > 0.")

        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'outgoing'),
            ('sequence_code', '=', 'OUT'),
            ('warehouse_id.company_id', '=', self.env.company.id),
        ], limit=1)

        if not picking_type:
            raise UserError("Tidak ada tipe Delivery Order (outgoing) yang tersedia di perusahaan ini.")

        move_vals_list = []
        for line in lines:
            product = line.product_id
            if not product or product.type == 'service':
                continue
            move_vals_list.append({
                'description_picking': product.display_name,
                'product_id': product.id,
                'product_uom_qty': line.qty_actual,
                'product_uom': product.uom_id.id,
                'location_id': picking_type.default_location_src_id.id,
                'location_dest_id': picking_type.default_location_dest_id.id,
                'picking_type_id': picking_type.id,
                'company_id': self.env.company.id,
            })

        if not move_vals_list:
            raise UserError("Tidak ada material storable yang bisa dibuat delivery.")

        picking = self.env['stock.picking'].sudo().create({
            'picking_type_id': picking_type.id,
            'location_id': picking_type.default_location_src_id.id,
            'location_dest_id': picking_type.default_location_dest_id.id,
            'partner_id': self.project_id.partner_id.id if self.project_id else False,
            'company_id': self.env.company.id,
            'origin': self.name,
            'move_ids': [(0, 0, vals) for vals in move_vals_list],
        })

        picking.action_confirm()
        picking.action_assign()

        self.material_picking_id = picking

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Berhasil',
                'message': f'Delivery Order {picking.name} berhasil dibuat.',
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }






