from odoo import models, fields, api, _
from odoo.exceptions import UserError


class RabManagement(models.Model):
    _name = 'rab.management'
    _description = 'RAB Management'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'
    active = fields.Boolean(default=True)


    # Informasi dasar RAB

    name = fields.Char(
        string='Nomor RAB',
        required=True,
        copy=False,
        default='New'
    )

    due_date = fields.Date(
        string='Tenggat Waktu',
        default=fields.Date.today
    )

    # Status workflow RAB
    state = fields.Selection(
        [
            ('draft', 'Draf'),
            ('negotiation', 'Negosiasi'),
            ('confirmed', 'Terkonfirmasi'),
        ],
        default='draft',
        tracking=True
    )

    # Customer tujuan penawaran
    customer_id = fields.Many2one(
        'res.partner',
        string='Pelanggan',
        required=True,
        domain=[('contact_type', 'in', ['customer', 'both'])],
    )

    # Detail RAB

    line_ids = fields.One2many(
        'rab.management.line',
        'rab_id',
        string='Detail RAB'
    )

    total_amount = fields.Monetary(
        string='Total Tagihan',
        compute='_compute_total',
        store=True
    )

    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id,
        required=True
    )

    # Relasi ke dokumen turunan

    # Sales Order utama yang dibuat dari RAB
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Pesanan Penjualan',
        readonly=True
    )

    # Semua Sales Order yang berasal dari RAB ini
    sale_order_ids = fields.One2many(
        'sale.order',
        compute='_compute_sale_orders',
        string='Daftar Pesanan Penjualan',
        readonly=True,
    )

    # Semua Purchase Order yang berasal dari RAB ini
    purchase_order_ids = fields.One2many(
        'purchase.order',
        compute='_compute_purchase_orders',
        string='Daftar Pesanan Pembelian',
        readonly=True,
    )

    # Flag untuk mengecek apakah ada SO confirmed
    has_confirmed_sale_order = fields.Boolean(
        compute='_compute_has_confirmed_sale_order',
        string='Has Confirmed SO'
    )

    source_type = fields.Selection(
        [
            ('project', 'Proyek'),
            ('additional', 'Pembelian Tambahan'),
            ('accounting', 'Akuntansi'),
        ],
        string='Sumber',
        default='accounting',
        required=True,
        readonly=True
    )
    
    project_id = fields.Many2one(
        'project.project',
        string='Dari Proyek',
        readonly=True,
        ondelete='set null'
    )

    # Workflow actions
    def unlink(self):
            for rec in self:
                if rec.state != 'draft':
                    raise UserError(_(
                        "RAB dengan status Confirmed / Disetujui tidak boleh dihapus.\n"
                        "Gunakan fitur Arsip."
                    ))
            return super().unlink()



    def action_save_draft(self):
        """Digunakan untuk menyimpan ulang RAB tanpa mengubah state."""
        self.ensure_one()
        
        # Validasi produk duplikat
        product_ids = self.line_ids.mapped('product_id')
        if len(product_ids) != len(self.line_ids):
            # Ada produk yang duplikat
            duplicates = []
            seen = set()
            for line in self.line_ids:
                if line.product_id.id in seen:
                    if line.product_id.display_name not in duplicates:
                        duplicates.append(line.product_id.display_name)
                seen.add(line.product_id.id)
            
            raise UserError(
                f"Produk berikut terduplikasi: {', '.join(duplicates)}. "
                "Setiap produk hanya boleh dipilih satu kali dalam satu RAB."
            )
        
        self.write({})
        return True

    def action_confirm(self):
        for rec in self:
            if rec.source_type == 'project':
                if not rec.line_ids:
                    raise UserError("RAB Project tidak boleh kosong.")

                if rec.line_ids.filtered(lambda l: not l.chosen_vendor_id):
                    raise UserError(
                        "Semua item Project harus memiliki vendor terpilih sebelum confirm."
                    )

                rec.state = 'confirmed'
                continue

            # === FLOW ACCOUNTING (LAMA) ===
            if not rec.customer_id:
                raise UserError("Customer harus diisi.")

            if not rec.has_confirmed_sale_order:
                raise UserError("Sales Order harus dikonfirmasi terlebih dahulu.")

            rec.state = 'confirmed'


    def action_approve(self):
        """Approve is no longer a separate state - confirmed is the final state."""
        # This method is kept for backward compatibility but does nothing
        # since 'confirmed' is now the final approved state
        pass

    # Pembuatan Sales Order dari RAB

    def action_create_sale_order(self):
        self.ensure_one()

        if self.state != 'confirmed':
            raise UserError("RAB harus dikonfirmasi sebelum membuat Sales Order.")

        if self.sale_order_id:
            raise UserError("Sales Order untuk RAB ini sudah dibuat.")

        SaleOrder = self.env['sale.order']
        SaleOrderLine = self.env['sale.order.line']

        # Buat SO header
        so = SaleOrder.create({
            'partner_id': self.customer_id.id,
            'origin': self.name,
        })

        # Tentukan nama prefix dari project atau nama RAB
        project_name = self.project_id.name if self.project_id else self.name

        # Buat SO line dari setiap baris RAB
        for termin_number, line in enumerate(self.line_ids, start=1):
            # Validasi harga jual - sementara di-comment
            # if not line.sale_price:
            #     raise UserError(
            #         f"Harga jual belum ditentukan untuk produk {line.product_id.display_name}"
            #     )

            SaleOrderLine.create({
                'order_id': so.id,
                'product_id': line.product_id.id,
                'product_uom_qty': line.quantity,
                'price_unit': line.sale_price,
                'name': f"{project_name} - service termin {termin_number}",
            })

        # Simpan referensi SO ke RAB (diizinkan meski RAB sudah confirmed)
        self.with_context(allow_confirmed_write=True).write({
            'sale_order_id': so.id
        })

        return {
            'type': 'ir.actions.act_window',
            'name': 'Sales Order',
            'res_model': 'sale.order',
            'res_id': so.id,
            'view_mode': 'form',
            'target': 'current',
        }

    # Pembuatan Purchase Order dari RAB

    def action_create_purchase_orders(self):
        self.ensure_one()

        if self.state != 'confirmed':
            raise UserError("RAB harus dikonfirmasi sebelum membuat Purchase Order.")

        PurchaseOrder = self.env['purchase.order']
        PurchaseOrderLine = self.env['purchase.order.line']

        # Kelompokkan baris RAB berdasarkan vendor
        vendor_map = {}

        for line in self.line_ids:
            if line.quantity <= 0.0:
                continue

            if not line.chosen_vendor_id:
                raise UserError(
                    f"Produk {line.product_id.display_name} belum memiliki vendor terpilih."
                )

            vendor = line.chosen_vendor_id
            vendor_map.setdefault(vendor, []).append(line)

        created_pos = self.env['purchase.order']

        # Buat satu PO untuk setiap vendor
        for vendor, lines in vendor_map.items():

            # Cegah duplikasi PO untuk vendor yang sama
            existing_po = PurchaseOrder.search([
                ('origin', '=', self.name),
                ('partner_id', '=', vendor.id),
            ], limit=1)

            if existing_po:
                raise UserError(
                    f"Purchase Order untuk vendor {vendor.display_name} sudah ada."
                )

            po_vals = {
                'partner_id': vendor.id,
                'origin': self.name,
                'rab_id': self.id,
            }
            if self.source_type == 'project' and self.project_id:
                po_vals['project_id'] = self.project_id.id

            po = PurchaseOrder.create(po_vals)

            for line in lines:
                if not line.purchase_price:
                    raise UserError(
                        f"Harga beli belum ditentukan untuk produk {line.product_id.display_name}"
                    )

                PurchaseOrderLine.create({
                    'order_id': po.id,
                    'product_id': line.product_id.id,
                    'name': line.name,
                    'product_qty': line.quantity,
                    'price_unit': line.purchase_price,
                    'date_planned': fields.Date.today(),
                })

            created_pos |= po

        # Tampilkan daftar PO yang berhasil dibuat
        return {
            'type': 'ir.actions.act_window',
            'name': 'Purchase Orders',
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', created_pos.ids)],
        }

    # Compute helpers

    def _compute_sale_orders(self):
        for rec in self:
            rec.sale_order_ids = self.env['sale.order'].search([
                ('origin', '=', rec.name)
            ])

    def _compute_purchase_orders(self):
        for rec in self:
            rec.purchase_order_ids = self.env['purchase.order'].search([
                ('origin', '=', rec.name)
            ])

    def _compute_has_confirmed_sale_order(self):
        for rec in self:
            confirmed_so = self.env['sale.order'].search([
                ('origin', '=', rec.name),
                ('state', 'in', ['sale', 'done'])
            ], limit=1)
            rec.has_confirmed_sale_order = bool(confirmed_so)

    @api.depends('line_ids.subtotal')
    def _compute_total(self):
        for rec in self:
            rec.total_amount = sum(rec.line_ids.mapped('subtotal'))

    # Proteksi write saat RAB sudah disetujui

    def write(self, vals):
        for rec in self:
            if rec.state == 'confirmed':
                # Izinkan update terbatas (misalnya set sale_order_id)
                if self.env.context.get('allow_confirmed_write'):
                    continue

                forbidden_fields = set(vals.keys()) - {'sale_order_id', 'active'}
                if forbidden_fields:
                    raise UserError("RAB yang sudah dikonfirmasi tidak dapat diubah.")

        return super().write(vals)

    # Sequence

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'rab.management'
                ) or 'New'
        return super().create(vals_list)


    # Action Buka Vendor Comparison OWL

    def action_open_vendor_comparison_owl(self):
        self.ensure_one()
        # Populate vendor untuk semua lines
        for line in self.line_ids:
            self.env['rab.vendor.comparison'].auto_populate_from_last_purchase(line, update_existing=False)
        # Return action client OWL
        return {
            'type': 'ir.actions.client',
            'tag': 'rab_vendor_comparison_action',
            'name': 'RAB Vendor Comparison',
            'context': {'active_id': self.id},
        }

    @classmethod
    def _valid_field_parameter(cls, field, name):
        return name == 'tracking' or super()._valid_field_parameter(field, name)
    


    # khusus project source
    def action_start_negotiation(self):
        self.ensure_one()

        if self.source_type != 'project':
            raise UserError("Negosiasi langsung hanya untuk RAB Project.")

        self.state = 'negotiation'

    def action_confirm(self):
        for rec in self:
            if rec.source_type == 'project':
                if not rec.line_ids.filtered(lambda l: l.chosen_vendor_id):
                    raise UserError("Vendor harus dipilih sebelum confirm RAB Project.")
            else:
                # logic lama (sales-based)
                pass

            rec.state = 'confirmed'

