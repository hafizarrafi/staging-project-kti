from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError


class RabVendorComparison(models.Model):
    _name = 'rab.vendor.comparison'
    _description = 'Perbandingan Vendor per RAB Line'
    _sql_constraints = [
        (
            'unique_vendor_per_rab_line',
            'UNIQUE(rab_line_id, vendor_id)',
            'Vendor yang sama tidak boleh dipilih lebih dari satu kali untuk item ini!'
        )
    ]

    # ==========================================================
    # RELASI
    # ==========================================================

    rab_line_id = fields.Many2one(
        'rab.management.line',
        required=True,
        ondelete='cascade'
    )

    rab_id = fields.Many2one(
        'rab.management',
        related='rab_line_id.rab_id',
        store=True,
        readonly=True
    )

    rab_state = fields.Selection(
        related='rab_id.state',
        store=True,
        readonly=True
    )

    product_id = fields.Many2one(
        related='rab_line_id.product_id',
        store=True,
        readonly=True
    )

    vendor_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        required=True,
        domain=[('contact_type', 'in', ['vendor', 'both'])],
    )

    # ==========================================================
    # SO CONFIRM FLAG (SINGLE SOURCE OF TRUTH)
    # ==========================================================

    has_so_confirmed = fields.Boolean(
        compute='_compute_has_so_confirmed',
        store=False,
    )

    # ==========================================================
    # HARGA
    # ==========================================================

    price = fields.Float(
        string="Harga Awal",
        default=0.0,
    )

    negotiation_price = fields.Float(
        string="Harga Negosiasi",
        help="Harga akhir hasil negosiasi yang digunakan saat memilih vendor."
    )

    price_locked = fields.Boolean(
        string="Harga Dikunci",
        default=False
    )

    # ==========================================================
    # STATUS
    # ==========================================================

    vendor_state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('negotiation', 'Negosiasi'),
            ('final', 'Final'),
            ('cancelled', 'Tidak Terpilih'),
        ],
        default='draft',
        tracking=True,
        store=True,
    )

    has_final_vendor = fields.Boolean(
        compute="_compute_has_final_vendor",
        store=False
    )

    is_used_for_pricing = fields.Boolean(
        compute="_compute_is_used_for_pricing",
        store=False
    )

    # ==========================================================
    # HISTORI PEMBELIAN
    # ==========================================================

    last_purchase_price = fields.Float(
        compute="_compute_last_purchase",
        store=True
    )

    last_purchase_date = fields.Datetime(
        compute="_compute_last_purchase",
        store=True
    )
    source_type = fields.Selection(
        related='rab_id.source_type',
        store=True,
        readonly=True
    )

    # ==========================================================
    # ONCHANGE
    # ==========================================================

    @api.onchange('vendor_state')
    def _onchange_vendor_state(self):
        for rec in self:
            if rec.vendor_state == 'negotiation':
                if not rec.negotiation_price:
                    rec.negotiation_price = rec.price
                rec.price_locked = True

    # ==========================================================
    # AUTO POPULATE VENDOR
    # ==========================================================

    def _get_last_purchase_map(self, product):
        result = {}
        po_lines = self.env['purchase.order.line'].search(
            [
                ('product_id', '=', product.id),
                ('order_id.state', 'in', ['purchase', 'done']),
                ('partner_id.contact_type', 'in', ['vendor', 'both']),
            ],
            order='id desc'
        )
        for line in po_lines:
            vendor_id = line.partner_id.id
            if vendor_id not in result:
                result[vendor_id] = line.price_unit
        return result

    def _get_supplierinfo_map(self, product):
        result = {}
        for info in product.product_tmpl_id.seller_ids:
            if info.partner_id.contact_type in ['vendor', 'both']:
                result[info.partner_id.id] = info.price
        return result

    @api.model
    def auto_populate_from_last_purchase(self, rab_line, update_existing=False):
        product = rab_line.product_id
        if not product:
            return

        last_purchase_map = self._get_last_purchase_map(product)
        supplierinfo_map = self._get_supplierinfo_map(product)

        vendor_ids = set(last_purchase_map.keys()) | set(supplierinfo_map.keys())

        for vendor_id in vendor_ids:
            existing = self.search(
                [
                    ('rab_line_id', '=', rab_line.id),
                    ('vendor_id', '=', vendor_id),
                ],
                limit=1
            )

            last_price = last_purchase_map.get(vendor_id)
            vendor_price = supplierinfo_map.get(vendor_id)

            if existing:
                if last_price and existing.vendor_state == 'draft':
                    existing._compute_last_purchase()

                if (
                    update_existing
                    and existing.vendor_state == 'draft'
                    and not existing.price_locked
                    and vendor_price
                ):
                    existing.with_context(auto_update=True).write({
                        'price': vendor_price,
                    })
                continue

            if not (last_price or vendor_price):
                continue

            self.create({
                'rab_line_id': rab_line.id,
                'vendor_id': vendor_id,
                'vendor_state': 'draft',
                'price': 0.0,
            })

    # ==========================================================
    # ACTIONS
    # ==========================================================

    def action_set_negotiation(self):
        for rec in self:
            if rec.has_final_vendor:
                raise UserError(
                    "Vendor final sudah dipilih. Silakan reset terlebih dahulu."
                )

            if (
                rec.rab_id.source_type == 'accounting'
                and not rec.has_so_confirmed
            ):
                raise UserError(
                    "Sales Order harus dikonfirmasi sebelum masuk tahap negosiasi."
                )

            if rec.vendor_state != 'draft':
                continue

            rec.with_context(skip_negotiation_price_guard=True).write({
                'vendor_state': 'negotiation',
                'price_locked': True,
            })

    def action_use_for_pricing(self):
        self.ensure_one()

        if self.has_final_vendor:
            raise UserError("Vendor final sudah dipilih.")

        price = self.negotiation_price or self.price
        if not price:
            raise UserError("Harga vendor belum ada.")

        self.rab_line_id.with_context(from_vendor_comparison=True).write({
            'chosen_vendor_id': self.vendor_id.id,
            'purchase_price': price,
        })

    def action_set_final(self):
        self.ensure_one()

        if (
            self.rab_id.source_type == 'accounting'
            and not self.has_so_confirmed
        ):
            raise UserError(
                "Sales Order harus dikonfirmasi sebelum memilih vendor final."
            )

        final_price = self.negotiation_price or self.price
        if not final_price:
            raise UserError("Harga vendor tidak boleh kosong.")

        self.search([
            ('rab_line_id', '=', self.rab_line_id.id),
            ('vendor_state', '=', 'final'),
        ]).write({'vendor_state': 'cancelled'})

        self.write({
            'vendor_state': 'final',
            'price_locked': True,
        })

        self.rab_line_id.with_context(from_vendor_comparison=True).write({
            'chosen_vendor_id': self.vendor_id.id,
            'purchase_price': final_price,
            'vendor_comparison_stage': 'selected',
        })

    def action_reset_final(self):
        self.ensure_one()
        if self.vendor_state != 'final':
            return

        affected = self.search([
            ('rab_line_id', '=', self.rab_line_id.id),
            ('vendor_state', 'in', ['final', 'cancelled']),
        ])

        affected.write({
            'vendor_state': 'draft',
            'price_locked': False,
        })

        self.rab_line_id.with_context(from_vendor_comparison=True).write({
            'chosen_vendor_id': False,
            'purchase_price': 0.0,
            'vendor_comparison_stage': 'draft',
        })

    # ==========================================================
    # COMPUTE
    # ==========================================================

    @api.depends('rab_id.source_type', 'rab_id.has_confirmed_sale_order')
    def _compute_has_so_confirmed(self):
        for rec in self:
            if rec.rab_id.source_type == 'project':
                rec.has_so_confirmed = True
            else:
                rec.has_so_confirmed = rec.rab_id.has_confirmed_sale_order

    @api.depends('rab_line_id')
    def _compute_has_final_vendor(self):
        for rec in self:
            rec.has_final_vendor = bool(self.search([
                ('rab_line_id', '=', rec.rab_line_id.id),
                ('vendor_state', '=', 'final'),
            ], limit=1))

    @api.depends('rab_line_id.chosen_vendor_id', 'vendor_id')
    def _compute_is_used_for_pricing(self):
        for rec in self:
            rec.is_used_for_pricing = (
                rec.rab_line_id.chosen_vendor_id
                and rec.rab_line_id.chosen_vendor_id.id == rec.vendor_id.id
            )

    @api.depends('vendor_id', 'product_id')
    def _compute_last_purchase(self):
        for rec in self:
            rec.last_purchase_price = 0.0
            rec.last_purchase_date = False

            if not rec.vendor_id or not rec.product_id:
                continue

            line = self.env['purchase.order.line'].search(
                [
                    ('product_id', '=', rec.product_id.id),
                    ('partner_id', '=', rec.vendor_id.id),
                    ('order_id.state', 'in', ['purchase', 'done']),
                ],
                order='id desc',
                limit=1
            )

            if line:
                rec.last_purchase_price = line.price_unit
                rec.last_purchase_date = line.order_id.date_order

    # ==========================================================
    # WRITE OVERRIDE
    # ==========================================================

    def write(self, vals):
        for rec in self:
            if 'price' in vals and not self.env.context.get('auto_update'):
                vals['price_locked'] = True

            if rec.vendor_state == 'final' and (
                'price' in vals or 'negotiation_price' in vals
            ):
                raise UserError(
                    "Harga vendor final tidak dapat diubah."
                )

            if 'negotiation_price' in vals:
                if not self.env.context.get('skip_negotiation_price_guard'):
                    if rec.vendor_state != 'negotiation':
                        raise UserError(
                            "Harga negosiasi hanya dapat diubah saat tahap negosiasi."
                        )
                    if (
                        rec.rab_id.source_type == 'accounting'
                        and not rec.has_so_confirmed
                    ):
                        raise UserError(
                            "Sales Order harus dikonfirmasi terlebih dahulu sebelum dapat mengubah harga negosiasi."
                        )

        return super().write(vals)

    # ==========================================================
    # CONSTRAINTS
    # ==========================================================

    @api.constrains('vendor_id', 'rab_line_id')
    def _check_unique_vendor(self):
        for rec in self:
            duplicate = self.search([
                ('rab_line_id', '=', rec.rab_line_id.id),
                ('vendor_id', '=', rec.vendor_id.id),
                ('id', '!=', rec.id)
            ], limit=1)
            if duplicate:
                raise UserError(
                    f"Vendor '{rec.vendor_id.display_name}' sudah ada dalam item ini."
                )

    @api.constrains('price', 'negotiation_price')
    def _check_positive_prices(self):
        for rec in self:
            if rec.price < 0:
                raise ValidationError("Harga awal tidak boleh negatif.")
            if rec.negotiation_price < 0:
                raise ValidationError("Harga negosiasi tidak boleh negatif.")
            if (
                rec.negotiation_price
                and rec.price
                and rec.negotiation_price > rec.price
            ):
                raise ValidationError(
                    "Harga negosiasi tidak boleh lebih tinggi dari harga quotation."
                )

    @classmethod
    def _valid_field_parameter(cls, field, name):
        return name == 'tracking' or super()._valid_field_parameter(field, name)
