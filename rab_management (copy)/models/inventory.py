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

    def _action_done(self):
        res = super()._action_done()
        for picking in self:
            if picking.picking_type_id.code != 'internal':
                continue
            if not picking.origin:
                continue

            so = self.env['sale.order'].search([('name', '=', picking.origin)], limit=1)
            if not so or not so.consume_material or not so.project_id:
                continue

            project = so.project_id
            for move in picking.move_ids.filtered(lambda m: m.state == 'done'):
                done_qty = move.quantity
                product = move.product_id

                # Cari di material master
                mat = project.material_master_ids.filtered(
                    lambda m: m.product_id.id == product.id
                )[:1]
                if mat:
                    mat.qty_on_site = min(mat.qty_on_site + done_qty, mat.total_qty)
                    continue

                # Cari di equipment master
                equip = project.equipment_master_ids.filtered(
                    lambda e: e.product_id.id == product.id
                )[:1]
                if equip:
                    equip.qty_on_site = min(equip.qty_on_site + done_qty, equip.total_qty)

        return res
