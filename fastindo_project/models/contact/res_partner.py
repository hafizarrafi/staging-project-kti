from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    discount_category_id = fields.Many2one(
        comodel_name='discount.category',
        string='Kategori Diskon',
        ondelete='set null',
        help='Kategori diskon yang diterapkan ke Sales Order pelanggan ini secara otomatis.',
    )
    discount_percentage = fields.Float(
        string='Diskon (%)',
        related='discount_category_id.discount_percentage',
        readonly=True,
        help='Persentase diskon dari kategori yang dipilih.',
    )

    # New Technical Fields for Fastindo
    risk_category_id = fields.Many2one('partner.risk.category', string='Risk Category')
    #dipending dulu yang ini
    # receivable_category_id = fields.Many2one('partner.receivable.category', string='Receivable Category')
    segment_id = fields.Many2one('partner.segment', string='Customer Segment')
    
    is_suspended = fields.Boolean(string='Is Suspended', default=False, tracking=True)
    suspension_log_ids = fields.One2many('partner.suspension.log', 'partner_id', string='Suspension Logs')

    overpayment_balance = fields.Monetary(
        string='Stored Balance',
        compute='_compute_partner_finances',
        help='Overpayment or customer credit balance.'
    )
    
    default_expedition_id = fields.Many2one('res.partner', string='Default Expedition', domain=[('is_company', '=', True)])

    contact_type = fields.Selection([
        ('supplier', 'Supplier'),
        ('customer', 'Customer'),
        ('logistics', 'Ekspedisi Pengiriman')
    ], string="Partner Role")

    shipping_price_per_kg = fields.Float(string="Nominal per kg", help="Harga pengiriman per kg untuk tipe logistik.")

    def _compute_partner_finances(self):
        for partner in self:
            # Logic based on Odoo's outstanding credits widget:
            domain = [
                ('partner_id', '=', partner.commercial_partner_id.id),
                ('account_id.account_type', '=', 'asset_receivable'),
                ('parent_state', '=', 'posted'),
                ('reconciled', '=', False),
                ('amount_residual', '<', 0.0),
            ]
            outstanding_lines = self.env['account.move.line'].search(domain)
            partner.overpayment_balance = abs(sum(outstanding_lines.mapped('amount_residual')))

    def action_suspend_partner(self):
        self.ensure_one()
        return {
            'name': 'Suspend Customer',
            'type': 'ir.actions.act_window',
            'res_model': 'partner.suspension.log',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_id': self.id,
                'default_state': 'suspended',
            }
        }

    def action_activate_partner(self):
        self.ensure_one()
        self.is_suspended = False
        self.env['partner.suspension.log'].create({
            'partner_id': self.id,
            'state': 'active',
            'reason': 'Customer reactivated.'
        })

    def action_view_sale_order(self):
        self.ensure_one()
        action = self.env.ref('sale.action_orders').read()[0]
        action['domain'] = [('partner_id', 'child_of', self.ids)]
        action['context'] = {'default_partner_id': self.id}
        return action
