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
        currency_field='currency_id',
        default=0.0
    )
    aktual_operasional = fields.Monetary(
        string='Operasional (Aktual)',
        currency_field='currency_id',
        default=0.0
    )
    aktual_mobdemob = fields.Monetary(
        string='Mob Demob (Aktual)',
        currency_field='currency_id',
        default=0.0
    )
    aktual_kawat_las = fields.Monetary(
        string='Kawat Las (Aktual)',
        currency_field='currency_id',
        default=0.0
    )
    aktual_oksigen = fields.Monetary(
        string='Oksigen (Aktual)',
        currency_field='currency_id',
        default=0.0
    )
    aktual_lpg = fields.Monetary(
        string='LPG (Aktual)',
        currency_field='currency_id',
        default=0.0
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

    @api.depends('material_total_rab', 'material_add_total_rab')
    def _compute_aktual_material(self):
        for rec in self:
            rec.aktual_material = rec.material_total_rab + rec.material_add_total_rab

    @api.depends('equipment_total_rab', 'equipment_add_total_rab')
    def _compute_aktual_equipment(self):
        for rec in self:
            rec.aktual_equipment = rec.equipment_total_rab + rec.equipment_add_total_rab

    def _compute_aktual_kawat_las(self):
        for rec in self:
            total = sum(rec.issue_ids.filtered(lambda i: i.state == 'done').mapped('issue_line_ids').filtered(lambda l: l.product_id.is_consumable_project).mapped('qty_issued_weight'))
            rec.aktual_kawat_las = total
            rec._compute_aktual_total()
    
    def _compute_aktual_by_category(self):
        for rec in self:
            # category -> total_amount from vendor bills
            categories = ['manpower', 'operasional', 'mobdemob', 'oksigen', 'lpg']
            for cat in categories:
                po_lines = self.env['account.move.line'].search([
                    ('purchase_line_id.order_id.project_id', '=', rec.id),
                    ('product_id.category_project', '=', cat),
                    ('move_id.state', '=', 'posted'),
                ])
                setattr(rec, 'aktual_' + cat, sum(po_lines.mapped('price_subtotal')))

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

    @api.depends('so_ditagihkan', 'sub_total_aktual')
    def _compute_margin_aktual(self):
        for rec in self:
            if rec.sub_total_aktual > 0:
                rec.margin_aktual = ((rec.so_ditagihkan - rec.sub_total_aktual) / rec.sub_total_aktual) * 100
            else:
                rec.margin_aktual = 0.0
