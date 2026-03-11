from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ProductUoMFactor(models.Model):
    _name = 'product.uom.factor'
    _description = 'Faktor Konversi Satuan Produk'
    _order = 'product_id, uom_id'

    product_id = fields.Many2one(
        'product.template',
        string='Produk',
        required=True,
        ondelete='cascade',
        help='Produk yang dikonversi'
    )

    currency_id = fields.Many2one(
        'res.currency', 
        string='Mata Uang', 
        related='product_id.currency_id'
    )

    uom_id = fields.Many2one(
        'uom.uom',
        string='Satuan Alternatif',
        required=True,
        help='Satuan alternatif untuk produk ini'
    )

    conversion_factor = fields.Float(
        string='Faktor Konversi',
        required=True,
        digits=(16, 2),
        help='Rasio konversi. Contoh: jika 1 Pickup = 0.8 m³, isi 0.8'
    )

    price = fields.Float(
        string='Harga',
        digits='Product Price',
        help='Harga per 1 satuan alternatif'
    )

    base_uom_id = fields.Many2one(
        'uom.uom',
        related='product_id.uom_id',
        readonly=True,
        string='Satuan Dasar',
        help='Satuan dasar/referensi produk ini'
    )

    qty_available_alt_uom = fields.Float(
        string='Stok Satuan Alternatif',
        compute='_compute_qty_available_alt_uom',
        inverse='_inverse_qty_available_alt_uom',
        digits=(16, 2),
        help='Stok dalam satuan alternatif. Mengubah ini akan memicu penyesuaian stok.'
    )

    notes = fields.Text(
        string='Catatan',
        help='Informasi tambahan konversi'
    )

    @api.depends('product_id.qty_available', 'conversion_factor')

    def _compute_qty_available_alt_uom(self):
        """Hitung stok dalam satuan alternatif."""
        for record in self:
            if record.conversion_factor > 0:
                # qty_available is in base UoM, convert to alternative UoM
                # If 1 Alt = 0.8 Base, then Alt = Base / 0.8
                record.qty_available_alt_uom = record.product_id.qty_available / record.conversion_factor
            else:
                record.qty_available_alt_uom = 0

    def _inverse_qty_available_alt_uom(self):
        """Metode inverse untuk penyesuaian stok saat Qty Satuan Alternatif diubah."""
        import logging
        _logger = logging.getLogger(__name__)
        
        for record in self:
            if not record.product_id:
                continue
            
            # Menggunakan variant produk pertama    
            product = record.product_id.product_variant_id
            if not product:
                continue
                
            # Menggunakan savepoint untuk setiap record untuk mencegah satu kegagalan menghentikan transaksi seluruhnya
            self.env.cr.execute('SAVEPOINT loka_uom_inverse_adjust')
            try:
                company = product.company_id or self.env.company
                warehouse = self.env['stock.warehouse'].search([('company_id', '=', company.id)], limit=1)
                if not warehouse:
                    warehouse = self.env['stock.warehouse'].search([], limit=1)
                    
                if not warehouse or not warehouse.lot_stock_id:
                    _logger.warning(f"No warehouse found for product {product.display_name}")
                    continue

                # Menghitung qty base yang diinginkan = qty alt baru * faktor konversi
                desired_base_qty = record.qty_available_alt_uom * (record.conversion_factor or 1.0)
                
                # Pastikan property_stock_inventory diatur untuk menghindari NotNullViolation (location_dest_id)
                # Properti ini biasanya pada level template
                template = product.product_tmpl_id
                if not template.sudo().with_company(company).property_stock_inventory:
                    inventory_location = self.env['stock.location'].search([
                        ('usage', '=', 'inventory'),
                        ('company_id', 'in', [company.id, False])
                    ], limit=1)
                    if inventory_location:
                        template.sudo().with_company(company).write({
                            'property_stock_inventory': inventory_location.id
                        })
                        template.flush_recordset(['property_stock_inventory'])
                    else:
                        _logger.error(f"No inventory location found for company {company.name}")
                        continue

                # Membuat stock.quant dengan inventory_mode=True
                # Menggunakan inventory_mode=True memungkinkan untuk menetapkan inventory_quantity langsung
                quant = self.env['stock.quant'].with_context(inventory_mode=True).create({
                    'product_id': product.id,
                    'location_id': warehouse.lot_stock_id.id,
                    'inventory_quantity': desired_base_qty,
                })
                quant.action_apply_inventory()
                self.env.cr.execute('RELEASE SAVEPOINT loka_uom_inverse_adjust')
            except Exception as e:
                # kembali ke savepoint untuk mencegah satu kegagalan menghentikan transaksi seluruhnya
                self.env.cr.execute('ROLLBACK TO SAVEPOINT loka_uom_inverse_adjust')
                _logger.error(f'Gagal menyesuaikan UoM live untuk {record.product_id.name}: {str(e)}')

    @api.constrains('conversion_factor', 'uom_id')
    def _check_conversion_factor(self):
        """Pastikan faktor konversi bernilai positif."""
        for record in self:
            # Hanya validasi jika baris sebenarnya sedang diisi (memiliki uom_id)
            if record.uom_id and record.conversion_factor <= 0:
                raise ValidationError('Maaf, Faktor Konversi harus bernilai positif / lebih dari 0.')

    _sql_constraints = [
        (
            'unique_product_uom',
            'UNIQUE(product_id, uom_id)',
            'Setiap produk hanya boleh memiliki satu faktor konversi per satuan.'
        ),
    ]

    def display_conversion(self):
        """Tampilkan keterangan konversi yang mudah dibaca."""
        return f"1 {self.uom_id.name} = {self.conversion_factor} {self.base_uom_id.name}"
