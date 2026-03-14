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
        
        for line in self.line_ids:
            # Create or Update Stock Quant
            quant = self.env['stock.quant'].search([
                ('product_id', '=', line.product_id.id),
                ('location_id', '=', self.location_id.id),
                ('lot_id', '=', False),
                ('package_id', '=', False),
                ('owner_id', '=', False)
            ], limit=1)
            
            if quant:
                quant.with_context(inventory_mode=True).write({
                    'inventory_quantity': quant.quantity + line.quantity
                })
                quant.action_apply_inventory()
            else:
                quant = self.env['stock.quant'].with_context(inventory_mode=True).create({
                    'product_id': line.product_id.id,
                    'location_id': self.location_id.id,
                    'inventory_quantity': line.quantity,
                })
                quant.action_apply_inventory()

        return {'type': 'ir.actions.client', 'tag': 'reload'}

class ProjectStockOnsiteLine(models.TransientModel):
    _name = 'project.stock.onsite.line'
    _description = 'Wizard Line for Project Stock On Site'

    wizard_id = fields.Many2one('project.stock.onsite.wizard', string='Wizard')
    product_id = fields.Many2one('product.product', string='Product', required=True, domain=[('type', '!=', 'service')])
    quantity = fields.Float(string='Quantity On Site', required=True, default=1.0)
    uom_id = fields.Many2one('uom.uom', related='product_id.uom_id', string='Unit of Measure', readonly=True)
