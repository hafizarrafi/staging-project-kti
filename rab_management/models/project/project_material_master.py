import math
from odoo import models, fields, api

class ProjectMaterialMaster(models.Model):
    _name = 'project.material.master'
    _description = 'Project Material Master'
    _order = 'product_id'

    project_id = fields.Many2one(
        'project.project',
        required=True,
        ondelete='cascade'
    )

    product_id = fields.Many2one(
        'product.product',
        required=True
    )

    job_type = fields.Selection(
        [
            ('primary', 'Utama'),
            ('additional', 'Tambahan'),
        ],
        string='Tipe Pekerjaan',
        default='primary',
        required=True
    )

    rab_id = fields.Many2one(
        'rab.management',
        string='Referensi RAB',
        readonly=True
    )
    
    total_weight = fields.Float(
        string='Total Berat (kg)',
        digits=(16, 2)
    )

    product_weight = fields.Float(
        string='Berat / Satuan (kg)',
        related='product_id.weight',
        readonly=True
    )

    total_qty = fields.Float(
        string='Total Qty Dibutuhkan',
        compute='_compute_total_qty',
        store=True,
    )

    @api.depends('total_weight', 'product_weight')
    def _compute_total_qty(self):
        for rec in self:
            if rec.total_weight and rec.product_weight:
                rec.total_qty = math.ceil(rec.total_weight / rec.product_weight)
            else:
                rec.total_qty = 0.0

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
        readonly=True
    )

    list_price = fields.Float(
        string='Harga Satuan',
        related='product_id.standard_price',
        readonly=True
    )

    subtotal = fields.Float(
        string='Subtotal',
        compute='_compute_subtotal',
        store=True
    )

    is_manual = fields.Boolean(
        string="Input Manual",
        default=True
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

    rab_total_subtotal = fields.Float(
        string='Total Subtotal RAB',
        compute='_compute_rab_price',
        store=True,
        digits=(16, 2),
    )

    subtotal_estimasi = fields.Float(
        string='Subtotal Estimasi',
        compute='_compute_rab_price',
        store=True,
        digits=(16, 2),
    )

    @api.depends('project_id.rab_id', 'project_id.rab_id.line_ids.sale_price', 'product_id', 'qty_beli', 'total_qty')
    def _compute_rab_price(self):
        for rec in self:
            rab = rec.project_id.rab_id
            if rab and rec.product_id:
                rab_line = rab.line_ids.filtered(
                    lambda l: l.product_id.id == rec.product_id.id
                )[:1]
                rec.rab_sale_price = rab_line.sale_price if rab_line else 0.0
                rec.rab_subtotal = rec.rab_sale_price * rec.qty_beli
                rec.rab_total_subtotal = rec.rab_sale_price * rec.total_qty
                rec.subtotal_estimasi = rec.rab_total_subtotal
            else:
                rec.rab_sale_price = 0.0
                rec.rab_subtotal = 0.0
                rec.rab_total_subtotal = 0.0
                rec.subtotal_estimasi = 0.0

    @api.depends('qty_beli', 'list_price')
    def _compute_subtotal(self):
        for rec in self:
            rec.subtotal = rec.qty_beli * rec.list_price

    @api.depends('total_qty', 'qty_on_site')
    def _compute_qty_beli(self):
        for rec in self:
            rec.qty_beli = max(
                (rec.total_qty or 0.0) - (rec.qty_on_site or 0.0),
                0.0
            )