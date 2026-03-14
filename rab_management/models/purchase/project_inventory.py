from odoo import models, fields, api

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    project_id = fields.Many2one(
        'project.project',
        string='Project',
        readonly=True,
        help="Linked project for this purchase order."
    )

    def _prepare_picking(self):
        vals = super()._prepare_picking()
        if self.project_id and self.project_id.stock_location_id:
            vals['location_dest_id'] = self.project_id.stock_location_id.id
        return vals

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    def _prepare_stock_move_vals(self, picking, price_unit, product_uom_qty, product_uom):
        res = super()._prepare_stock_move_vals(picking, price_unit, product_uom_qty, product_uom)
        if self.order_id.project_id and self.order_id.project_id.stock_location_id:
            res['location_dest_id'] = self.order_id.project_id.stock_location_id.id
        return res
