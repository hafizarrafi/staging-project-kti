from odoo import models, fields

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    is_project_so = fields.Boolean(
        string='Project SO',
        default=False,
        help='Menandai bahwa SO ini dibuat dari Project'
    )
    
