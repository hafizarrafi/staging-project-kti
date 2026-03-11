from odoo import models, fields, api
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    budget_master_id = fields.Many2one(
        'budget.master',
        string='Master Budget',
        copy=False,
        tracking=True,
    )
    budget_transaction_id = fields.Many2one(
        'budget.transaction',
        string='Budget Transaction',
        readonly=True,
        copy=False,
    )

    def action_add_to_budget(self):
        self.ensure_one()
        if not self.budget_master_id:
            raise UserError('Pilih Master Budget terlebih dahulu.')
        if self.budget_transaction_id and self.budget_transaction_id.exists():
            raise UserError(
                f'Journal entry ini sudah terhubung ke budget transaction: {self.budget_transaction_id.display_name}.'
            )
        accounting_date = self.date
        if not accounting_date:
            raise UserError('Accounting Date pada journal entry tidak boleh kosong.')

        estimate = self.env['budget.estimate'].search([
            ('budget_id', '=', self.budget_master_id.id),
            ('date_from', '<=', accounting_date),
            ('date_to', '>=', accounting_date),
            ('state', '=', 'confirmed'),
        ], limit=1)

        if not estimate:
            raise UserError(
                f'Tidak ditemukan Budget Estimate yang aktif (Confirmed) untuk master budget '
                f'"{self.budget_master_id.name}" pada tanggal {accounting_date}.'
            )

        transaction = self.env['budget.transaction'].create({
            'budget_estimate_id': estimate.id,
            'move_id': self.id,
            'amount': self.amount_total,
            'date': accounting_date,
            'note': self.name,
        })
        self.budget_transaction_id = transaction
