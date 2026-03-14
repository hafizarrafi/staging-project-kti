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
        inventory_location = self.env.ref('stock.stock_location_inventory_loss', raise_if_not_found=False)
        if not inventory_location:
            inventory_location = self.env['stock.location'].search([
                ('usage', '=', 'inventory'), 
                '|', ('company_id', '=', self.project_id.company_id.id), ('company_id', '=', False)
            ], limit=1)
        
        if not inventory_location:
             raise UserError(_("Cannot find Inventory Adjustment location. Please check your inventory configuration."))

        # Create formal picking for audit trail
        # Try to find an appropriate picking type (usually 'incoming' for initial stock or 'internal')
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'incoming'),
            ('company_id', '=', self.project_id.company_id.id)
        ], limit=1)

        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id if picking_type else False,
            'location_id': inventory_location.id,
            'location_dest_id': self.location_id.id,
            'origin': _("Initial Stock Recognition: %s") % self.project_id.name,
            'move_type': 'direct',
            'company_id': self.project_id.company_id.id,
        })

        moves = self.env['stock.move']
        for line in self.line_ids:
            moves |= self.env['stock.move'].create({
                'name': line.product_id.display_name,
                'product_id': line.product_id.id,
                'product_uom_qty': line.quantity,
                'product_uom': line.product_id.uom_id.id,
                'picking_id': picking.id,
                'location_id': inventory_location.id,
                'location_dest_id': self.location_id.id,
                'company_id': self.project_id.company_id.id,
            })
        
        picking.action_confirm()
        picking.action_assign()
        
        # Set quantities and validate
        for move in picking.move_ids:
            if move.state == 'assigned':
                move.quantity_done = move.product_uom_qty
        
        picking.button_validate()

        return {'type': 'ir.actions.client', 'tag': 'reload'}

class ProjectStockOnsiteLine(models.TransientModel):
    _name = 'project.stock.onsite.line'
    _description = 'Wizard Line for Project Stock On Site'

    wizard_id = fields.Many2one('project.stock.onsite.wizard', string='Wizard')
    product_id = fields.Many2one('product.product', string='Product', required=True, domain=[('type', '!=', 'service')])
    quantity = fields.Float(string='Quantity On Site', required=True, default=1.0)
    uom_id = fields.Many2one('uom.uom', related='product_id.uom_id', string='Unit of Measure', readonly=True)
