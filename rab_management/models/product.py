from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    massa_jenis = fields.Float(
        string='Massa Jenis / Berat per Meter',
        digits=(16, 10)
    )
