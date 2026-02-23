from odoo import models

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def action_confirm(self):
        res = super().action_confirm()

        for so in self:
            if not so.origin:
                continue

            rab = self.env['rab.management'].search([
                ('name', '=', so.origin)
            ], limit=1)

            if not rab:
                continue

            price_map = {
                line.product_id.id: line.price_unit
                for line in so.order_line
            }

            for rab_line in rab.line_ids:
                final_price = price_map.get(rab_line.product_id.id)
                if final_price:
                    rab_line.with_context(from_so_confirm=True).write({
                        'sale_price': final_price
                    })

        return res
