from odoo import models, fields, _
from odoo.exceptions import UserError


class StockPickingInherit(models.Model):
    _inherit = 'stock.picking'

    pic_penerima = fields.Char(
        string='PIC Penerima',
        tracking=True,
    )

    def button_validate(self):
        for picking in self:
            if picking.picking_type_id.code == 'outgoing' and picking.state == 'assigned':
                if not picking.pic_penerima:
                    raise UserError(_('PIC Penerima harus diisi sebelum melakukan validasi delivery.'))
        return super(StockPickingInherit, self).button_validate()
