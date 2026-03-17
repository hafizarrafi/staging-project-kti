from odoo import models, fields, api

class RabManagement(models.Model):
    _inherit = 'rab.management'

    def action_create_purchase_orders(self):
        # Kita panggil super() dan dapatkan response-nya (bisa berisi view action)
        res = super().action_create_purchase_orders()
        
        # Cari PO yang baru dibuat dari RAB ini dan inject project_id
        if self.project_id:
            # Cari PO berdasarkan origin (RAB number)
            pos = self.env['purchase.order'].search([('origin', '=', self.name)])
            if pos:
                pos.write({'project_id': self.project_id.id})
                
        return res
