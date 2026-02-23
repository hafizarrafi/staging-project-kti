from odoo import models, fields, api

class ProjectEquipmentMaster(models.Model):
    _name = 'project.equipment.master'
    _description = 'Project Equipment Master'
    _order = 'product_id'

    project_id = fields.Many2one(
        'project.project',
        required=True,
        ondelete='cascade'
    )

    product_id = fields.Many2one(
        'product.product',
        string='Equipment',
        required=True
    )
    
    total_qty = fields.Float(
        string='Total Qty Required',
        default=1.0,
        digits=(16, 2)
    )

    qty_on_site = fields.Float(
        string='Qty On Site',
        default=0.0
    )

    qty_beli = fields.Float(
        string='Qty Beli',
        compute='_compute_qty_beli',
        store=True
    )

    uom_id = fields.Many2one(
        related='product_id.uom_id',
        readonly=True,
        string='UOM'
    )

    unit_price = fields.Float(
        string='Unit Price',
        related='product_id.standard_price',
        readonly=True
    )

    subtotal = fields.Float(
        string='Subtotal',
        compute='_compute_subtotal',
        store=True
    )

    rab_sale_price = fields.Float(
        string='Harga RAB',
        compute='_compute_rab_price',
        store=True,
        digits=(16, 2),
    )

    rab_subtotal = fields.Float(
        string='Subtotal RAB',
        compute='_compute_rab_price',
        store=True,
        digits=(16, 2),
    )

    @api.depends('project_id.rab_id', 'project_id.rab_id.line_ids.sale_price', 'product_id', 'qty_beli')
    def _compute_rab_price(self):
        for rec in self:
            rab = rec.project_id.rab_id
            if rab and rec.product_id:
                rab_line = rab.line_ids.filtered(
                    lambda l: l.product_id.id == rec.product_id.id
                )[:1]
                rec.rab_sale_price = rab_line.sale_price if rab_line else 0.0
                rec.rab_subtotal = rec.rab_sale_price * rec.qty_beli
            else:
                rec.rab_sale_price = 0.0
                rec.rab_subtotal = 0.0

    @api.depends('qty_beli', 'unit_price')
    def _compute_subtotal(self):
        for rec in self:
            rec.subtotal = rec.qty_beli * rec.unit_price

    @api.depends('total_qty', 'qty_on_site')
    def _compute_qty_beli(self):
        for rec in self:
            rec.qty_beli = max(
                (rec.total_qty or 0.0) - (rec.qty_on_site or 0.0),
                0.0
            )
