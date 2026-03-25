from odoo import models, fields, api


class BudgetEstimate(models.Model):
    _name = 'budget.estimate'
    _description = 'Budget Estimate per Periode'
    _order = 'date_from desc'

    budget_id = fields.Many2one(
        'budget.master',
        string='Master Budget',
        required=True,
        ondelete='restrict'
    )
    date_from = fields.Date(string='Dari Tanggal', required=True)
    date_to = fields.Date(string='Sampai Tanggal', required=True)
    amount = fields.Monetary(string='Estimasi Amount', required=True)
    currency_id = fields.Many2one(
        related='company_id.currency_id',
        readonly=True
    )
    company_id = fields.Many2one(
        'res.company',
        default=lambda self: self.env.company,
        required=True
    )
    state = fields.Selection(
        [('draft', 'Draft'), ('confirmed', 'Confirmed')],
        string='Status',
        default='draft',
        readonly=True
    )
    note = fields.Text(string='Keterangan')

    transaction_ids = fields.One2many(
        'budget.transaction',
        'budget_estimate_id',
        string='Transaksi'
    )
    amount_actual = fields.Monetary(
        string='Realisasi',
        compute='_compute_amount_actual',
        store=True
    )
    amount_remaining = fields.Monetary(
        string='Sisa Budget',
        compute='_compute_amount_actual',
        store=True
    )

    @api.depends('transaction_ids.amount')
    def _compute_amount_actual(self):
        for rec in self:
            rec.amount_actual = sum(rec.transaction_ids.mapped('amount'))
            rec.amount_remaining = rec.amount - rec.amount_actual

    def action_confirm(self):
        self.state = 'confirmed'

    def action_reset_draft(self):
        self.state = 'draft'

    _sql_constraints = [
        ('date_check', 'CHECK(date_from <= date_to)', 'Tanggal mulai harus lebih kecil dari tanggal akhir.')
    ]
