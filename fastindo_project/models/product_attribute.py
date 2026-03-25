from odoo import models, fields


class ProductMaterial(models.Model):
    _name = 'product.material'
    _description = 'Product Material'
    _order = 'name'

    name = fields.Char(string='Material', required=True)


class ProductStandardization(models.Model):
    _name = 'product.standardization'
    _description = 'Product Standardization'
    _order = 'name'

    name = fields.Char(string='Standardization', required=True)


class ProductFinishing(models.Model):
    _name = 'product.finishing'
    _description = 'Product Finishing'
    _order = 'name'

    name = fields.Char(string='Finishing', required=True)
