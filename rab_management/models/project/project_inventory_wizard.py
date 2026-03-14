from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ProjectStockOnsiteWizard(models.TransientModel):
    _name = 'project.stock.onsite.wizard'
    _description = 'Wizard to Initialize Project Stock On Site'

    project_id = fields.Many2one('project.project', string='Project', required=True)
    location_id = fields.Many2one('stock.location', related='project_id.stock_location_id', string='Target Location', readonly=True)
    line_ids = fields.One2many('project.stock.onsite.line', 'wizard_id', string='Stock Lines')

    def action_confirm(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("Please add at least one product line."))
        
        if not self.location_id:
            self.project_id._create_stock_location()

        # Cari Inventory Adjustment Location (Virtual)
        # Sederhanakan pencarian: cari lokasi mana pun dengan usage 'inventory'
        # karena lokasi ini bersifat virtual (adjustment)
        inventory_location = self.env['stock.location'].search([('usage', '=', 'inventory')], limit=1)
        
        if not inventory_location:
             raise UserError(_("Cannot find Inventory Adjustment location (usage: inventory). Please check your inventory configuration."))

        # Hanya buat move untuk produk yang ada quantity-nya > 0
        lines_to_process = self.line_ids.filtered(lambda l: l.quantity > 0)
        
        if not lines_to_process:
            # Jika user sengaja mengosongkan semua (qty=0), 
            # kita anggap inisialisasi selesai tanpa membuat picking apapun.
            self.project_id.sudo().write({'is_stock_initialized': True})
            return {'type': 'ir.actions.client', 'tag': 'reload'}

        # Sederhanakan pencarian picking_type: cari incoming atau internal yang tersedia
        picking_type = self.env['stock.picking.type'].search([
            ('code', 'in', ['incoming', 'internal']),
            ('company_id', '=', self.project_id.company_id.id)
        ], limit=1)
        
        if not picking_type:
            # Fallback tanpa filter company jika perlu
            picking_type = self.env['stock.picking.type'].search([('code', 'in', ['incoming', 'internal'])], limit=1)

        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id if picking_type else False,
            'location_id': inventory_location.id,
            'location_dest_id': self.location_id.id,
            'origin': _("Initial Stock Adjustment: %s") % self.project_id.name,
            'move_type': 'direct',
            'company_id': self.project_id.company_id.id,
        })

        # Batch create moves for better performance (Odoo 19 compatible)
        move_vals = []
        for line in lines_to_process:
            move_vals.append({
                'description_picking': line.product_id.display_name,
                'product_id': line.product_id.id,
                'product_uom_qty': line.quantity,
                'product_uom': line.product_id.uom_id.id,
                'picking_id': picking.id,
                'location_id': inventory_location.id,
                'location_dest_id': self.location_id.id,
                'company_id': self.project_id.company_id.id,
                'state': 'draft',
            })
        
        self.env['stock.move'].create(move_vals)
        
        picking.action_confirm()
        picking.action_assign()
        
        # Set quantities and validate (Odoo 19: usage of 'quantity' field instead of 'quantity_done')
        for move in picking.move_ids:
            if move.state == 'assigned':
                # Di Odoo 17+, fieldnya biasanya 'quantity'. 
                # Kita gunakan helper jika tersedia atau set langsung ke move lines.
                for move_line in move.move_line_ids:
                    move_line.quantity = move_line.quantity_product_uom
        
        picking.button_validate()
        
        # Mark project as initialized
        self.project_id.sudo().write({'is_stock_initialized': True})

        return {'type': 'ir.actions.client', 'tag': 'reload'}

class ProjectStockOnsiteLine(models.TransientModel):
    _name = 'project.stock.onsite.line'
    _description = 'Wizard Line for Project Stock On Site'

    wizard_id = fields.Many2one('project.stock.onsite.wizard', string='Wizard')
    product_id = fields.Many2one('product.product', string='Product', required=True, domain=[('type', '!=', 'service')])
    quantity = fields.Float(string='Quantity On Site', required=True, default=1.0)
    uom_id = fields.Many2one('uom.uom', related='product_id.uom_id', string='Unit of Measure', readonly=True)
