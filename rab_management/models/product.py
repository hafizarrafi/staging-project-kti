from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    massa_jenis = fields.Float(
        string='Massa Jenis / Berat per Meter',
        digits=(16, 10)
    )

    category_project = fields.Selection([
        ('material', 'Material'),
        ('equipment', 'Equipment'),
        ('manpower', 'Man Power'),
        ('operasional', 'Operasional'),
        ('mobdemob', 'Mob Demob'),
        ('oksigen', 'Oksigen'),
        ('lpg', 'LPG'),
    ], string='Kategori Proyek')

    is_consumable_project = fields.Boolean(
        string='Consumable Project', default=False
    )
