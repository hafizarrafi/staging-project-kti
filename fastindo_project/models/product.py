from odoo import models, fields, api


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    uom_factor_ids = fields.One2many(
        'product.uom.factor',
        'product_id',
        string='Faktor Konversi Satuan',
        help='Tentukan rasio konversi untuk satuan alternatif'
    )

    # New technical fields for Fastindo
    x_standardization_id = fields.Many2one(
        'product.standardization',
        string='Standardization',
        help='Select product standardization (DIN, JIS, ANSI, SNI, etc.)'
    )
    x_certificate = fields.Binary(
        string='Certificate (PDF)',
        help='Attach certificate in PDF format'
    )
    x_certificate_name = fields.Char(string='Certificate Filename')
    x_material_id = fields.Many2one(
        'product.material',
        string='Material',
        help='Select product material (Stainless, Carbon steel, etc.)'
    )
    x_grade = fields.Char(
        string='Grade',
        help='Product grade'
    )
    x_finishing_id = fields.Many2one(
        'product.finishing',
        string='Finishing',
        help='Select product finishing'
    )

    qty_alt_html = fields.Html(
        string='Stok Satuan Alternatif',
        compute='_compute_qty_alt_html',
        sanitize=True,
        help='Menampilkan stok dalam satuan alternatif (HTML)'
    )

    @api.depends('qty_available', 'uom_factor_ids.conversion_factor')
    def _compute_qty_alt_html(self):
        for tmpl in self:
            lines = []
            base_qty = tmpl.qty_available or 0.0
            for factor in tmpl.uom_factor_ids:
                try:
                    if factor.conversion_factor and factor.conversion_factor > 0:
                        alt_qty = base_qty / factor.conversion_factor
                    else:
                        alt_qty = 0.0
                except Exception:
                    alt_qty = 0.0
                lines.append(f"{alt_qty:,.2f} {factor.uom_id.name}")
            # buat HTML sederhana
            html = '<div class="o_alt_uom_list">' + ''.join(f'<div>{l}</div>' for l in lines) + '</div>'
            tmpl.qty_alt_html = html

    def _get_converted_quantity(self, quantity, from_uom, to_uom):
        """Konversi satuan menggunakan faktor khusus produk."""
        if from_uom == to_uom:
            return quantity
        
        factor_record = self.uom_factor_ids.filtered(lambda f: f.uom_id == to_uom)
        if not factor_record:
            return from_uom._compute_quantity(quantity, to_uom)
        
        return quantity / factor_record[0].conversion_factor
