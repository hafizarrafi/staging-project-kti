from odoo import models, fields, api


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    discount_category_id = fields.Many2one(
        comodel_name='discount.category',
        string='Kategori Diskon',
        readonly=False,
        help='Kategori diskon yang diterapkan ke semua baris pesanan.',
    )
    discount_percentage = fields.Float(
        string='Diskon (%)',
        related='discount_category_id.discount_percentage',
        readonly=True,
        store=True,
    )
    
    suggested_product_ids = fields.Many2many(
        'product.template', 
        string='Suggested Segment Products',
        related='partner_id.segment_id.product_ids',
        readonly=True
    )

    def action_load_segment_products(self):
        self.ensure_one()
        if not self.partner_id.segment_id:
            return
        
        for template in self.partner_id.segment_id.product_ids:
            product = template.product_variant_id
            if not product:
                continue
            # Add to order lines if not already present
            existing = self.order_line.filtered(lambda l: l.product_id == product)
            if not existing:
                self.order_line = [(0, 0, {
                    'product_id': product.id,
                    'product_uom_qty': 1.0,
                })]

    @api.onchange('partner_id')
    def _onchange_partner_discount_category(self):
        """Ambil kategori diskon dari pelanggan secara otomatis."""
        if self.partner_id and self.partner_id.discount_category_id:
            self.discount_category_id = self.partner_id.discount_category_id
        elif not self.partner_id:
            self.discount_category_id = False
        self._apply_discount_to_lines()

    @api.onchange('discount_category_id')
    def _onchange_discount_category_apply(self):
        """Terapkan persentase diskon ke semua baris order."""
        self._apply_discount_to_lines()

    def _apply_discount_to_lines(self):
        """Helper: set discount pada semua baris order sesuai kategori aktif."""
        discount = self.discount_category_id.discount_percentage if self.discount_category_id else 0.0
        for line in self.order_line:
            line.discount = discount

    def write(self, vals):
        """Saat discount_category_id disimpan, perbarui semua baris."""
        res = super().write(vals)
        if 'discount_category_id' in vals:
            for order in self:
                discount = order.discount_category_id.discount_percentage if order.discount_category_id else 0.0
                order.order_line.write({'discount': discount})
        return res


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.onchange('product_id', 'product_template_id')
    def _onchange_product_apply_discount(self):
        """Saat produk dipilih di baris baru, ambil diskon dari order induk."""
        if self.order_id and self.order_id.discount_category_id:
            self.discount = self.order_id.discount_category_id.discount_percentage

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

    @api.model_create_multi
    def create(self, vals_list):
        """Fallback: saat baris baru disimpan, terapkan diskon dari order induk."""
        lines = super().create(vals_list)
        for line in lines:
            if line.order_id.discount_category_id and not line.discount:
                line.discount = line.order_id.discount_category_id.discount_percentage
        return lines
