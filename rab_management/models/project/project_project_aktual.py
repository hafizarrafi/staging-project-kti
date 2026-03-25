from odoo import models, fields, api


class ProjectProject(models.Model):
    _inherit = 'project.project'

    so_ditagihkan = fields.Monetary(
        string='SO Ditagihkan',
        compute='_compute_so_ditagihkan',
        store=True,
        currency_field='currency_id'
    )

    total_margin = fields.Float(
        string='Total Margin (%)',
        compute='_compute_total_margin',
        store=True
    )

    # === Ringkasan Aktual / Realisasi Biaya ===
    aktual_material = fields.Monetary(
        string='Material (Aktual)',
        compute='_compute_aktual_material',
        store=True,
        currency_field='currency_id'
    )
    aktual_equipment = fields.Monetary(
        string='Equipment & Tools (Aktual)',
        compute='_compute_aktual_equipment',
        store=True,
        currency_field='currency_id'
    )
    aktual_manpower = fields.Monetary(
        string='Man Power (Aktual)',
        compute='_compute_aktual_by_category',
        store=True,
        currency_field='currency_id',
    )
    aktual_operasional = fields.Monetary(
        string='Operasional (Aktual)',
        compute='_compute_aktual_by_category',
        store=True,
        currency_field='currency_id',
    )
    aktual_mobdemob = fields.Monetary(
        string='Mob Demob (Aktual)',
        compute='_compute_aktual_by_category',
        store=True,
        currency_field='currency_id',
    )
    aktual_kawat_las = fields.Monetary(
        string='Kawat Las (Aktual)',
        compute='_compute_aktual_kawat_las',
        store=True,
        currency_field='currency_id',
    )
    aktual_oksigen = fields.Monetary(
        string='Oksigen (Aktual)',
        compute='_compute_aktual_by_category',
        store=True,
        currency_field='currency_id',
    )
    aktual_lpg = fields.Monetary(
        string='LPG (Aktual)',
        compute='_compute_aktual_by_category',
        store=True,
        currency_field='currency_id',
    )
    sub_total_aktual = fields.Monetary(
        string='Total Aktual',
        compute='_compute_sub_total_aktual',
        store=True,
        currency_field='currency_id'
    )
    variance_aktual = fields.Monetary(
        string='Selisih (Aktual - Estimasi)',
        compute='_compute_variance_aktual',
        store=True,
        currency_field='currency_id'
    )
    variance_aktual_pct = fields.Float(
        string='% Selisih',
        compute='_compute_variance_aktual',
        store=True,
        digits=(16, 2)
    )
    margin_aktual = fields.Float(
        string='Margin Aktual (%)',
        compute='_compute_margin_aktual',
        store=True,
        digits=(16, 2)
    )

    @api.depends('project_sale_order_ids.amount_total', 'project_sale_order_ids.state')
    def _compute_so_ditagihkan(self):
        for rec in self:
            confirmed = rec.project_sale_order_ids.filtered(
                lambda so: so.state in ('sale', 'done')
            )
            rec.so_ditagihkan = sum(confirmed.mapped('amount_total'))

    @api.depends('so_ditagihkan', 'sub_total_summary')
    def _compute_total_margin(self):
        for rec in self:
            if rec.sub_total_summary > 0:
                rec.total_margin = ((rec.so_ditagihkan - rec.sub_total_summary) / rec.sub_total_summary) * 100
            else:
                rec.total_margin = 0.0

    @api.depends('material_master_ids.product_id', 'purchase_order_ids')
    def _compute_aktual_material(self):
        AccountMoveLine = self.env['account.move.line']
        for rec in self:
            material_product_ids = rec.material_master_ids.product_id.ids
            if not material_product_ids or not rec.purchase_order_ids:
                rec.aktual_material = 0.0
                continue

            bill_lines = AccountMoveLine.search([
                ('move_id.move_type', '=', 'in_invoice'),
                ('move_id.state', '=', 'posted'),
                ('purchase_line_id.order_id', 'in', rec.purchase_order_ids.ids),
                ('product_id', 'in', material_product_ids),
            ])
            rec.aktual_material = sum(bill_lines.mapped('price_subtotal'))

    @api.depends('equipment_master_ids.product_id', 'purchase_order_ids')
    def _compute_aktual_equipment(self):
        AccountMoveLine = self.env['account.move.line']
        for rec in self:
            equipment_product_ids = rec.equipment_master_ids.product_id.ids
            if not equipment_product_ids or not rec.purchase_order_ids:
                rec.aktual_equipment = 0.0
                continue

            bill_lines = AccountMoveLine.search([
                ('move_id.move_type', '=', 'in_invoice'),
                ('move_id.state', '=', 'posted'),
                ('purchase_line_id.order_id', 'in', rec.purchase_order_ids.ids),
                ('product_id', 'in', equipment_product_ids),
            ])
            rec.aktual_equipment = sum(bill_lines.mapped('price_subtotal'))

    @api.depends('aktual_material', 'aktual_equipment', 'aktual_manpower',
                 'aktual_operasional', 'aktual_mobdemob', 'aktual_kawat_las',
                 'aktual_oksigen', 'aktual_lpg')
    def _compute_sub_total_aktual(self):
        for rec in self:
            rec.sub_total_aktual = (
                rec.aktual_material + rec.aktual_equipment + rec.aktual_manpower +
                rec.aktual_operasional + rec.aktual_mobdemob + rec.aktual_kawat_las +
                rec.aktual_oksigen + rec.aktual_lpg
            )

    @api.depends('sub_total_aktual', 'sub_total_summary')
    def _compute_variance_aktual(self):
        for rec in self:
            rec.variance_aktual = rec.sub_total_aktual - rec.sub_total_summary
            if rec.sub_total_summary > 0:
                rec.variance_aktual_pct = (rec.variance_aktual / rec.sub_total_summary) * 100
            else:
                rec.variance_aktual_pct = 0.0

    @api.depends('kawat_las_product_id', 'rewelding_product_id', 'purchase_order_ids')
    def _compute_aktual_kawat_las(self):
        AccountMoveLine = self.env['account.move.line']
        for rec in self:
            product_ids = list(filter(None, [
                rec.kawat_las_product_id.id,
                rec.rewelding_product_id.id,
            ]))
            if not product_ids or not rec.purchase_order_ids:
                rec.aktual_kawat_las = 0.0
                continue

            bill_lines = AccountMoveLine.search([
                ('move_id.move_type', '=', 'in_invoice'),
                ('move_id.state', '=', 'posted'),
                ('purchase_line_id.order_id', 'in', rec.purchase_order_ids.ids),
                ('product_id', 'in', product_ids),
            ])
            rec.aktual_kawat_las = sum(bill_lines.mapped('price_subtotal'))

    @api.depends('purchase_order_ids')
    def _compute_aktual_by_category(self):
        AccountMoveLine = self.env['account.move.line']
        for rec in self:
            if not rec.purchase_order_ids:
                rec.aktual_oksigen = 0.0
                rec.aktual_lpg = 0.0
                continue

            bill_lines = AccountMoveLine.search([
                ('move_id.move_type', '=', 'in_invoice'),
                ('move_id.state', '=', 'posted'),
                ('purchase_line_id.order_id', 'in', rec.purchase_order_ids.ids),
                ('product_id.category_project', 'in', ['manpower', 'operasional', 'mobdemob', 'oksigen', 'lpg']),
            ])
            rec.aktual_manpower = sum(
                l.price_subtotal for l in bill_lines
                if l.product_id.category_project == 'manpower'
            )
            rec.aktual_operasional = sum(
                l.price_subtotal for l in bill_lines
                if l.product_id.category_project == 'operasional'
            )
            rec.aktual_mobdemob = sum(
                l.price_subtotal for l in bill_lines
                if l.product_id.category_project == 'mobdemob'
            )
            rec.aktual_oksigen = sum(
                l.price_subtotal for l in bill_lines
                if l.product_id.category_project == 'oksigen'
            )
            rec.aktual_lpg = sum(
                l.price_subtotal for l in bill_lines
                if l.product_id.category_project == 'lpg'
            )

    def action_recompute_aktual(self):
        self.ensure_one()
        self._compute_aktual_material()
        self._compute_aktual_equipment()
        self._compute_aktual_kawat_las()
        self._compute_aktual_by_category()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Selesai',
                'message': 'Aktual Material dan Equipment berhasil dihitung ulang.',
                'type': 'success',
                'sticky': False,
            },
        }

    @api.depends('so_ditagihkan', 'sub_total_aktual')
    def _compute_margin_aktual(self):
        for rec in self:
            if rec.sub_total_aktual > 0:
                rec.margin_aktual = ((rec.so_ditagihkan - rec.sub_total_aktual) / rec.sub_total_aktual) * 100
            else:
                rec.margin_aktual = 0.0
