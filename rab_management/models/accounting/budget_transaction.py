from odoo import models, fields


class BudgetTransaction(models.Model):
    _name = 'budget.transaction'
    _description = 'Budget Transaction'
    _order = 'date desc'

    budget_estimate_id = fields.Many2one(
        'budget.estimate',
        string='Budget Estimate',
        required=True,
        ondelete='restrict'
    )
    move_id = fields.Many2one(
        'account.move',
        string='Journal Entry',
        domain=[('state', '=', 'posted')],
        ondelete='restrict'
    )
    amount = fields.Monetary(string='Amount', required=True)
    currency_id = fields.Many2one(
        related='budget_estimate_id.currency_id',
        readonly=True
    )
    date = fields.Date(
        string='Tanggal',
        default=fields.Date.today,
        required=True
    )
    note = fields.Char(string='Keterangan')
