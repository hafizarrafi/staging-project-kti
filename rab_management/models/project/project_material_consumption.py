import math
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ProjectMaterialConsumption(models.Model):
    _name = 'project.material.consumption'
    _description = 'Material Consumption Dashboard'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    project_id = fields.Many2one(
        'project.project',
        string='Project',
        required=True,
        ondelete='cascade',
        index=True
    )
    date = fields.Date(
        string='Last Update',
        default=fields.Date.today,
        required=True
    )
    line_ids = fields.One2many(
        'project.material.consumption.line',
        'consumption_id',
        string='Requirement Lines',
        copy=True
    )
    issue_ids = fields.One2many(
        'project.material.issue',
        related='project_id.issue_ids',
        string='Material Issue Logs'
    )
    stock_quant_ids = fields.Many2many(
        'stock.quant',
        string='Project Inventory',
        compute='_compute_stock_quants'
    )

    def _compute_stock_quants(self):
        for rec in self:
            if rec.project_id.stock_location_id:
                rec.stock_quant_ids = self.env['stock.quant'].search([
                    ('location_id', 'child_of', rec.project_id.stock_location_id.id)
                ])
            else:
                rec.stock_quant_ids = False

    @api.onchange('project_id')
    def _onchange_project_id_load_requirements(self):
        self.action_refresh_requirements()

    def action_refresh_requirements(self):
        for rec in self:
            if not rec.project_id:
                rec.line_ids = [(5, 0, 0)]
                continue

            # Get all material requirements from tasks in this project
            tasks = self.env['project.task'].search([('project_id', '=', rec.project_id.id)])
            
            # Map existing lines to avoid duplicates and preserve selection if possible
            existing_lines = {(l.task_id.id, l.product_id.id): l for l in rec.line_ids}
            
            line_vals = []
            seen_requirements = set()
            
            for task in tasks:
                for mat in task.material_needed_ids:
                    key = (task.id, mat.product_id.id)
                    seen_requirements.add(key)
                    
                    if key in existing_lines:
                        # Update existing line quantities if needed
                        line = existing_lines[key]
                        line.write({
                            'qty_required_kg': mat.weight or 0.0,
                        })
                    else:
                        # Create new line
                        line_vals.append((0, 0, {
                            'task_id': task.id,
                            'product_id': mat.product_id.id,
                            'qty_required_kg': mat.weight or 0.0,
                        }))
            
            # Remove lines that are no longer in tasks
            for key, line in existing_lines.items():
                if key not in seen_requirements:
                    line_vals.append((2, line.id, 0))
            
            if line_vals:
                rec.line_ids = line_vals

    def action_generate_picking(self):
        self.ensure_one()
        selected_lines = self.line_ids.filtered(lambda l: l.is_selected and l.qty_to_issue_unit > 0)
        
        if not selected_lines:
            raise UserError(_("Please select items with 'Qty to Issue' > 0."))

        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'outgoing'),
            ('warehouse_id.company_id', '=', self.project_id.company_id.id),
        ], limit=1)

        if not picking_type:
            picking_type = self.env['stock.picking.type'].search([('code', '=', 'outgoing')], limit=1)

        if not picking_type:
            raise UserError(_("No outgoing picking type found."))

        # 1. Create a Log Record in project.material.issue
        issue_log = self.env['project.material.issue'].create({
            'project_id': self.project_id.id,
            'date': fields.Date.today(),
            'state': 'confirmed',
        })

        # 2. Create Picking
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': picking_type.default_location_src_id.id,
            'location_dest_id': self.project_id.stock_location_id.id,
            'origin': _('Consumption Dashboard: %s') % self.project_id.name,
            'company_id': self.project_id.company_id.id,
        })
        
        issue_log.picking_id = picking.id

        # 3. Create Moves
        move_vals = []
        for line in selected_lines:
            # Create Log Line
            self.env['project.material.issue.line'].create({
                'issue_id': issue_log.id,
                'product_id': line.product_id.id,
                'task_id': line.task_id.id,
                'qty_required_kg': line.qty_required_kg,
                'qty_issue_unit': line.qty_to_issue_unit,
            })

            # Create move directly without 'name' to avoid ValueError
            move_vals.append({
                'picking_id': picking.id,
                'product_id': line.product_id.id,
                'product_uom_qty': line.qty_to_issue_unit,
                'product_uom': line.product_id.uom_id.id,
                'location_id': picking_type.default_location_src_id.id,
                'location_dest_id': self.project_id.stock_location_id.id,
                'origin': picking.origin,
                'company_id': self.project_id.company_id.id,
            })

        self.env['stock.move'].create(move_vals)
        
        # 4. Process Picking
        picking.action_confirm()
        picking.action_assign()
        
        # Reset selection
        selected_lines.write({'is_selected': False})

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'res_id': picking.id,
            'view_mode': 'form',
            'target': 'current',
        }

class ProjectMaterialConsumptionLine(models.Model):
    _name = 'project.material.consumption.line'
    _description = 'Material Consumption Line'

    consumption_id = fields.Many2one('project.material.consumption', string='Consumption', ondelete='cascade')
    is_selected = fields.Boolean(string='Select')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    task_id = fields.Many2one('project.task', string='Task/Subtask')

    qty_available = fields.Float(string='Stok (uom)', compute='_compute_qty_status')
    qty_required_kg = fields.Float(string='Dibutuhkan (kg)', digits=(16, 2))
    
    qty_issued_unit = fields.Float(string='Sudah Terbit (unit)', compute='_compute_qty_status')
    qty_to_issue_unit = fields.Float(string='Akan Terbit (unit)', compute='_compute_qty_to_issue', store=True, readonly=False)

    @api.depends('product_id', 'consumption_id.project_id.stock_location_id')
    def _compute_qty_status(self):
        for rec in self:
            # 1. Available Stock at site
            rec.qty_available = 0.0
            if rec.product_id and rec.consumption_id.project_id.stock_location_id:
                quants = self.env['stock.quant'].search([
                    ('product_id', '=', rec.product_id.id),
                    ('location_id', '=', rec.consumption_id.project_id.stock_location_id.id)
                ])
                rec.qty_available = sum(quants.mapped('quantity'))

            # 2. Total Issued so far (from logs)
            rec.qty_issued_unit = sum(self.env['project.material.issue.line'].search([
                ('task_id', '=', rec.task_id.id),
                ('product_id', '=', rec.product_id.id),
                ('issue_id.state', '!=', 'cancel')
            ]).mapped('qty_issue_unit'))

    @api.depends('qty_required_kg', 'product_id.weight')
    def _compute_qty_to_issue(self):
        for rec in self:
            weight = rec.product_id.weight or 0.0
            if weight > 0:
                rec.qty_to_issue_unit = math.ceil(rec.qty_required_kg / weight)
            else:
                rec.qty_to_issue_unit = 0
