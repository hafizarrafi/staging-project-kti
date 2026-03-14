from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

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

        # 1. Hitung Stock Terkini di Lokasi Proyek
        quants = self.env['stock.quant'].search([
            ('location_id', '=', self.location_id.id),
            ('product_id', 'in', self.line_ids.mapped('product_id').ids)
        ])
        current_qty_map = {}
        for q in quants:
            current_qty_map[q.product_id.id] = current_qty_map.get(q.product_id.id, 0.0) + q.quantity

        # 2. Siapkan data move berdasarkan selisih (delta)
        move_vals = []
        for line in self.line_ids:
            qty_current = current_qty_map.get(line.product_id.id, 0.0)
            qty_target = line.quantity
            delta = qty_target - qty_current
            
            _logger.info("SYNC DELTA %s: current=%s, target=%s, delta=%s", 
                         line.product_id.display_name, qty_current, qty_target, delta)

            if delta == 0:
                continue
            
            if delta > 0:
                # Tambah Stok: Virtual -> Project
                src_loc = inventory_location.id
                dest_loc = self.location_id.id
                qty_move = delta
            else:
                # Kurangi Stok: Project -> Virtual
                src_loc = self.location_id.id
                dest_loc = inventory_location.id
                qty_move = abs(delta)

            move_vals.append({
                'product_id': line.product_id.id,
                'product_uom_qty': qty_move,
                'product_uom': line.product_id.uom_id.id,
                'location_id': src_loc,
                'location_dest_id': dest_loc,
                'company_id': self.project_id.company_id.id,
            })
        
        if not move_vals:
            # Tidak ada selisih, tidak perlu buat picking
            return {'type': 'ir.actions.client', 'tag': 'reload'}

        # Sederhanakan pencarian picking_type: cari incoming atau internal yang tersedia
        picking_type = self.env['stock.picking.type'].search([
            ('code', 'in', ['incoming', 'internal']),
            ('company_id', '=', self.project_id.company_id.id)
        ], limit=1)
        
        if not picking_type:
            # Fallback tanpa filter company jika perlu
            picking_type = self.env['stock.picking.type'].search([('code', 'in', ['incoming', 'internal'])], limit=1)

        # 3. Buat dan Proses Picking
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id if picking_type else False,
            'location_id': inventory_location.id, # Base location, moves will override if needed
            'location_dest_id': self.location_id.id,
            'origin': _("Stock Sync: %s") % self.project_id.name,
            'move_type': 'direct',
            'company_id': self.project_id.company_id.id,
        })

        for val in move_vals:
            val['picking_id'] = picking.id
        
        self.env['stock.move'].create(move_vals)
        
        picking.action_confirm()
        picking.action_assign()
        
        # Odoo 19: Use internal helper to set quantities correctly
        for move in picking.move_ids:
            move._set_quantity_done(move.product_uom_qty)
        
        # Use background-safe done action
        picking._action_done()

        return {'type': 'ir.actions.client', 'tag': 'reload'}

class ProjectStockOnsiteLine(models.TransientModel):
    _name = 'project.stock.onsite.line'
    _description = 'Wizard Line for Project Stock On Site'

    wizard_id = fields.Many2one('project.stock.onsite.wizard', string='Wizard')
    product_id = fields.Many2one('product.product', string='Product', required=True, domain=[('type', '!=', 'service')])
    quantity = fields.Float(string='Quantity On Site', required=True, default=1.0)
    uom_id = fields.Many2one('uom.uom', related='product_id.uom_id', string='Unit of Measure', readonly=True)
