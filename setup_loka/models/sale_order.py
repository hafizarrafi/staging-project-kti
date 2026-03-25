from odoo import models, fields, api

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.onchange('product_uom_id', 'product_id')
    def _onchange_product_uom_custom_price(self):
        """Set harga otomatis jika satuan alternatif memiliki harga khusus."""
        if not self.product_id or not self.product_uom_id:
            return

        # Cari harga khusus di faktor konversi
        factor = self.env['product.uom.factor'].search([
            ('product_id', '=', self.product_id.product_tmpl_id.id),
            ('uom_id', '=', self.product_uom_id.id)
        ], limit=1)

        if factor and factor.price > 0:
            self.price_unit = factor.price

    @api.depends('product_id', 'product_id.uom_id', 'product_id.uom_factor_ids.uom_id')
    def _compute_allowed_uom_ids(self):
        """Masukkan satuan alternatif dalam daftar pilihan."""
        super()._compute_allowed_uom_ids()
        for line in self:
            if line.product_id:
                # Tambah satuan dari faktor konversi
                custom_uoms = line.product_id.product_tmpl_id.uom_factor_ids.mapped('uom_id')
                line.allowed_uom_ids |= custom_uoms

    def _action_launch_stock_rule(self, **kwargs):
        """Pastikan satuan tetap terjaga jika ada faktor konversi khusus."""
        has_custom_factor = any(
            line.product_id.product_tmpl_id.uom_factor_ids.filtered(lambda f: f.uom_id == line.product_uom_id)
            for line in self if line.product_id
        )
        if has_custom_factor:
            return super(SaleOrderLine, self.with_context(force_uom_propagation=True))._action_launch_stock_rule(**kwargs)
        return super()._action_launch_stock_rule(**kwargs)
