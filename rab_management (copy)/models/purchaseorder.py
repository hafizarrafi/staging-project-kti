from odoo import models, fields


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    rab_id = fields.Many2one(
        'rab.management',
        string='RAB',
        readonly=True,
        copy=False,
        help='RAB yang menghasilkan Purchase Order ini',
    )
