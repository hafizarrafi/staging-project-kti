from odoo import models, fields, api
from odoo.exceptions import UserError


class RabManagementLine(models.Model):
    _name = 'rab.management.line'
    _description = 'RAB Line'
    _sql_constraints = [
        ('unique_product_per_rab', 'UNIQUE(rab_id, product_id)', 
         'Produk yang sama tidak boleh dipilih lebih dari satu kali dalam satu RAB!')
    ]

    # --- Relasi utama ---
    rab_id = fields.Many2one(
        'rab.management',
        ondelete='cascade',
        required=True
    )

    product_id = fields.Many2one(
        'product.product',
        string='Produk',
        required=True
    )

    # Nama baris otomatis mengikuti produk yang dipilih
    name = fields.Char(
        string='Deskripsi',
        compute='_compute_name',
        store=True
    )

    quantity = fields.Float(
        default=1.0,
        digits='Product Unit of Measure'
    )

    # --- Perbandingan vendor ---
    vendor_line_ids = fields.One2many(
        'rab.vendor.comparison',
        'rab_line_id',
        string='Perbandingan Vendor'
    )

    # Vendor yang dipilih sebagai hasil akhir
    chosen_vendor_id = fields.Many2one(
        'res.partner',
        string='Vendor Terpilih',
        readonly=True
    )

    # Harga beli akhir yang diambil dari vendor terpilih
    purchase_price = fields.Monetary(
        string='Harga Beli',
        readonly=True
    )

    # --- Margin & harga jual ---
    margin_type = fields.Selection(
        [
            ('absolute', 'Nominal'),
            ('percentage', 'Persentase'),
        ],
        string='Tipe Margin',
        default='percentage',
        required=True
    )


    margin_value = fields.Float(
        string="Margin (%)",
        compute="_compute_margin_value",
        inverse="_inverse_margin_value",
        store=True,
    )


    # Harga jual dihitung dari harga beli + margin
    sale_price = fields.Monetary(
        string='Harga Jual',
        compute='_compute_sale_price',
        store=True,
        readonly=True
    )

    # --- Total ---
    subtotal = fields.Monetary(
        compute='_compute_subtotal',
        store=True
    )

    currency_id = fields.Many2one(
        related='rab_id.currency_id',
        store=True,
        readonly=True
    )

    # Penanda bahwa baris terkunci ketika RAB sudah disetujui
    is_locked = fields.Boolean(
        compute='_compute_is_locked',
        store=True
    )

    # Tahapan global proses perbandingan vendor
    vendor_comparison_stage = fields.Selection(
        [
            ('draft', 'Draft'),
            ('negotiation', 'Negosiasi'),
            ('selected', 'Terpilih'),
        ],
        default='draft',
        tracking=True,
        string='Tahap Perbandingan Vendor'
    )
    rab_state = fields.Selection(
        related='rab_id.state',
        store=True,
        readonly=True
    )
    



    # ------------------------------------------------------------------
    # Proteksi perubahan data
    # ------------------------------------------------------------------

    @api.constrains('product_id', 'rab_id')
    def _check_unique_product(self):
        """Validasi Python: Produk tidak boleh duplikat dalam satu RAB"""
        for rec in self:
            if rec.product_id and rec.rab_id:
                duplicate = self.search([
                    ('rab_id', '=', rec.rab_id.id),
                    ('product_id', '=', rec.product_id.id),
                    ('id', '!=', rec.id)
                ], limit=1)
                if duplicate:
                    raise UserError(
                        f"Produk '{rec.product_id.display_name}' sudah ada dalam RAB ini. "
                        "Setiap produk hanya boleh dipilih satu kali."
                    )
    @api.depends(
        'purchase_price',
        'sale_price',
        'rab_id.has_confirmed_sale_order',
    )
    def _compute_margin_value(self):
        for line in self:
            if (
                line.rab_id.source_type == 'accounting'
                and line.rab_id.has_confirmed_sale_order
                and line.purchase_price
            ):

                line.margin_value = (
                    (line.sale_price - line.purchase_price)
                    / line.purchase_price
                ) * 100


    def _inverse_margin_value(self):
        for line in self:
            if (
                line.rab_id.source_type == 'accounting'
                and line.rab_id.has_confirmed_sale_order
            ):
                return
            # setelah SO confirmed, margin tidak editable

            base_price = line._get_active_purchase_price()
            if not base_price:
                line.sale_price = 0.0
                return

            if line.margin_type == 'absolute':
                line.sale_price = base_price + line.margin_value
            else:
                line.sale_price = base_price * (1 + (line.margin_value / 100))


    @api.constrains('margin_value')
    def _check_margin_value(self):
        for rec in self:
            if rec.margin_value < 0:
                raise UserError("Nilai margin tidak boleh negatif.")


    def write(self, vals):
        # Baris RAB tidak boleh diubah jika RAB sudah dikonfirmasi
        # Kecuali perubahan datang dari vendor comparison (negosiasi harga)
        for rec in self:
            if rec.rab_id.state == 'confirmed' and not self.env.context.get('from_vendor_comparison')  or self.env.context.get('from_so_confirm'):
                # Hanya izinkan update field tertentu
                allowed_fields = {'vendor_line_ids', 'chosen_vendor_id', 'purchase_price', 'vendor_comparison_stage', 'sale_price'}
                if not set(vals.keys()).issubset(allowed_fields):
                    raise UserError(
                        "Baris RAB yang sudah dikonfirmasi tidak dapat diubah."
                    )
        for rec in self:
            if (
                rec.rab_id.source_type == 'accounting'
                and 'margin_value' in vals
                and rec.rab_id.has_confirmed_sale_order
                and not self.env.context.get('from_so_confirm')
            ):

                raise UserError("Margin tidak dapat diubah setelah Sales Order dikonfirmasi.")
        return super().write(vals)

    # ------------------------------------------------------------------
    # Method compute
    # ------------------------------------------------------------------

    @api.depends('rab_id.state')
    def _compute_is_locked(self):
        for rec in self:
            rec.is_locked = rec.rab_id.state == 'confirmed'

    @api.depends('product_id')
    def _compute_name(self):
        for line in self:
            line.name = line.product_id.display_name if line.product_id else ''


    @api.depends(
        'purchase_price',
        'margin_value',
        'margin_type',
        'rab_id.has_confirmed_sale_order',
        'rab_id.source_type',
    )
    def _compute_sale_price(self):
        for line in self:
            if (
                line.rab_id.source_type == 'accounting'
                and line.rab_id.has_confirmed_sale_order
            ):
                line.sale_price = line.get_final_sale_price()
                continue

            base_price = line._get_active_purchase_price()
            if not base_price:
                line.sale_price = 0.0
                continue

            if line.margin_type == 'absolute':
                line.sale_price = base_price + line.margin_value
            else:
                line.sale_price = base_price * (1 + (line.margin_value / 100))

    def get_final_sale_price(self):
        self.ensure_one()
        if self.rab_id.source_type == 'accounting' and self.rab_id.sale_order_id:
            sol = self.env['sale.order.line'].search([
                ('order_id', '=', self.rab_id.sale_order_id.id),
                ('product_id', '=', self.product_id.id),
            ], limit=1)
            return sol.price_unit if sol else 0.0
        return self.sale_price

    @api.depends('quantity', 'sale_price')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.quantity * line.sale_price

    # ------------------------------------------------------------------
    # Action
    # ------------------------------------------------------------------

    def action_open_rab_line(self):
        self.ensure_one()

        # Update data vendor dari histori
        # Saat buka form RAB Line
        self.env['rab.vendor.comparison'].auto_populate_from_last_purchase(self, update_existing=False)

        return {
            'type': 'ir.actions.act_window',
            'name': 'RAB Line',
            'res_model': 'rab.management.line',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @classmethod
    def _valid_field_parameter(cls, field, name):
        return name == 'tracking' or super()._valid_field_parameter(field, name)

    def _get_active_purchase_price(self):
        self.ensure_one()

        # 1. Jika sudah vendor final → pakai harga beli final
        if self.purchase_price:
            return self.purchase_price

        # 2. Jika belum final, tapi vendor sudah dipilih
        if self.chosen_vendor_id:
            vendor_line = self.vendor_line_ids.filtered(
                lambda v: v.vendor_id.id == self.chosen_vendor_id.id
            )[:1]

            if vendor_line:
                # pakai harga nego kalau ada, fallback ke quotation
                return vendor_line.negotiation_price or vendor_line.price

        return 0.0

