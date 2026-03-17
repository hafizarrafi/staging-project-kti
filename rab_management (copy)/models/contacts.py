from odoo import models, fields


class ResPartner(models.Model):
    _inherit = 'res.partner'

    contact_type = fields.Selection([
        ('customer', 'Customer'),
        ('vendor', 'Vendor'),
        ('both', 'Customer & Vendor'),
    ], string='Contact Type', copy=True)