from odoo import models, fields


class Budget(models.Model):
    _name = 'budget.master'
    _description = 'Master Budget'
    _order = 'name'

    name = fields.Char(string='Nama Budget', required=True)
    code = fields.Char(string='Kode', required=True, copy=False)
    description = fields.Text(string='Keterangan')
    active = fields.Boolean(default=True)

    estimate_ids = fields.One2many(
        'budget.estimate',
        'budget_id',
        string='Estimasi Budget'
    )

    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Kode budget harus unik.')
    ]
