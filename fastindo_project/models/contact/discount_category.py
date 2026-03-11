from odoo import models, fields, api
from odoo.exceptions import ValidationError


class DiscountCategory(models.Model):
    _name = 'discount.category'
    _description = 'Kategori Diskon Pelanggan'
    _order = 'name'

    name = fields.Char(
        string='Nama Kategori',
        required=True,
    )
    discount_percentage = fields.Float(
        string='Persentase Diskon (%)',
        required=True,
        default=0.0,
        help='Persentase diskon yang akan diterapkan secara otomatis pada Sales Order '
             'untuk pelanggan dengan kategori ini.',
    )
    description = fields.Text(
        string='Keterangan',
    )
    partner_count = fields.Integer(
        string='Jumlah Pelanggan',
        compute='_compute_partner_count',
    )
    active = fields.Boolean(default=True)

    @api.depends('name')
    def _compute_partner_count(self):
        for rec in self:
            rec.partner_count = self.env['res.partner'].search_count([
                ('discount_category_id', '=', rec.id)
            ])

    @api.constrains('discount_percentage')
    def _check_discount_percentage(self):
        for rec in self:
            if rec.discount_percentage < 0 or rec.discount_percentage > 100:
                raise ValidationError(
                    'Persentase diskon harus antara 0 dan 100.'
                )

    def action_view_partners(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Pelanggan - {self.name}',
            'res_model': 'res.partner',
            'view_mode': 'list,form',
            'domain': [('discount_category_id', '=', self.id)],
            'context': {'default_discount_category_id': self.id},
        }
