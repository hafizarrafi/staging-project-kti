from odoo import models, fields, api, tools
from odoo.tools.misc import groupby
from odoo.tools.float_utils import float_compare


class StockMove(models.Model):
    _inherit = 'stock.move'

    @api.depends('product_id', 'product_uom', 'product_uom_qty', 'state')
    def _compute_product_qty(self):
        """Hitung jumlah stok dasar menggunakan faktor konversi khusus."""
        for move in self:
            if not move.product_id or not move.product_uom:
                move.product_qty = move.product_uom._compute_quantity(
                    move.product_uom_qty, move.product_id.uom_id, rounding_method='HALF-UP')
                continue

            # Cek faktor konversi khusus
            factor_record = self.env['product.uom.factor'].search([
                ('product_id', '=', move.product_id.product_tmpl_id.id),
                ('uom_id', '=', move.product_uom.id)
            ], limit=1)

            if factor_record and factor_record.conversion_factor > 0:
                # Base Qty = Alt Qty * Conversion Factor
                move.product_qty = move.product_uom_qty * factor_record.conversion_factor
            else:
                move.product_qty = move.product_uom._compute_quantity(
                    move.product_uom_qty, move.product_id.uom_id, rounding_method='HALF-UP')

    def _action_assign(self, force_qty=False):
        """Reservasi stok dengan konteks konversi yang benar."""
        for product, moves in groupby(self, key=lambda m: m.product_id):
            moves_recordset = self.env['stock.move'].concat(*moves)
            if product:
                super(StockMove, moves_recordset.with_context(
                    product_id=product.id,
                    product_model='product.product'
                ))._action_assign(force_qty=force_qty)
            else:
                super(StockMove, moves_recordset)._action_assign(force_qty=force_qty)
        return True

    @api.depends('move_line_ids.quantity', 'move_line_ids.product_uom_id')
    def _compute_quantity(self):
        """Hitung jumlah reservasi dengan konteks produk."""
        for move in self:
            if not move.product_id:
                move.quantity = move._quantity_sml()
                continue
            
            # Use product context for the sum calculation
            move.quantity = move.with_context(
                product_id=move.product_id.id,
                product_model='product.product'
            )._quantity_sml()

    @api.depends('product_id', 'product_qty', 'picking_type_id', 'quantity', 'priority', 'state', 'product_uom_qty', 'location_id')
    def _compute_forecast_information(self):
        """Pastikan informasi stok ramalan (forecasting) menggunakan konteks produk."""
        for product, moves in groupby(self, key=lambda m: m.product_id):
            moves_recordset = self.env['stock.move'].concat(*moves)
            if product:
                super(StockMove, moves_recordset.with_context(
                    product_id=product.id,
                    product_model='product.product'
                ))._compute_forecast_information()
            else:
                super(StockMove, moves_recordset)._compute_forecast_information()

    @api.depends('state', 'product_id', 'product_qty', 'location_id')
    def _compute_product_availability(self):
        """Hitung ketersediaan produk untuk tampilan view."""
        for move in self:
            if move.state == 'done':
                move.availability = move.product_qty
            else:
                if move.product_id:
                    # Get available quantity in base UoM
                    total_availability = self.env['stock.quant']._get_available_quantity(move.product_id, move.location_id)
                    move.availability = min(move.product_qty, total_availability)
                else:
                    move.availability = 0.0


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    @api.depends('quantity', 'product_uom_id', 'product_id')
    def _compute_quantity_product_uom(self):
        """Hitung jumlah stok dasar pada baris pengerjaan (move lines)."""
        for line in self:
            if not line.product_id or not line.product_uom_id:
                line.quantity_product_uom = line.product_uom_id._compute_quantity(
                    line.quantity, line.product_id.uom_id, rounding_method='HALF-UP')
                continue

            # Cek faktor konversi khusus
            factor_record = self.env['product.uom.factor'].search([
                ('product_id', '=', line.product_id.product_tmpl_id.id),
                ('uom_id', '=', line.product_uom_id.id)
            ], limit=1)

            if factor_record and factor_record.conversion_factor > 0:
                # Base Qty = Alt Qty * Conversion Factor
                line.quantity_product_uom = line.quantity * factor_record.conversion_factor
            else:
                line.quantity_product_uom = line.product_uom_id._compute_quantity(
                    line.quantity, line.product_id.uom_id, rounding_method='HALF-UP')
