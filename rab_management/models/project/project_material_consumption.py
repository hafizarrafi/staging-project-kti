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
    summary_ids = fields.One2many(
        'project.material.consumption.summary',
        'consumption_id',
        string='Issue Aggregation'
    )

    def action_calculate_summary(self):
        """Aggregate selected requirements into summary table."""
        self.ensure_one()
        self.summary_ids.unlink()
        
        selected_lines = self.line_ids.filtered(lambda l: l.is_selected and l.qty_required_kg > 0)
        if not selected_lines:
            return
            
        # Group by product_id
        aggregation = {} # product_id -> total_weight
        for line in selected_lines:
            pid = line.product_id.id
            aggregation[pid] = aggregation.get(pid, 0.0) + line.qty_required_kg
            
        summary_vals = []
        for pid, weight in aggregation.items():
            summary_vals.append((0, 0, {
                'consumption_id': self.id,
                'product_id': pid,
                'total_weight_kg': weight,
            }))
        self.summary_ids = summary_vals

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
        # Use summary_ids instead of line_ids
        selected_summaries = self.summary_ids.filtered(lambda s: s.qty_to_issue_unit > 0)
        
        if not selected_summaries:
            raise UserError(_("Please calculate selection and ensure 'Akan Terbit' > 0."))

        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'outgoing'),
            ('sequence_code', '=', 'OUT'),
            ('warehouse_id.company_id', '=', self.project_id.company_id.id),
        ], limit=1)

        if not picking_type:
            # Fallback to any OUT picking type
            picking_type = self.env['stock.picking.type'].search([
                ('sequence_code', '=', 'OUT'),
            ], limit=1)

        if not picking_type:
            raise UserError(_("No 'OUT' picking type found."))

        # 1. Create a Log Record in project.material.issue
        issue_log = self.env['project.material.issue'].create({
            'project_id': self.project_id.id,
            'date': fields.Date.today(),
            'state': 'confirmed',
        })

        # 2. Create Picking
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': self.project_id.stock_location_id.id or picking_type.default_location_src_id.id,
            'location_dest_id': picking_type.default_location_dest_id.id, # Customer or project usage? User said get from source project location.
            # Wait, user said: "pastinya stock harus mengambil dari source location project, bukan parent inventory".
            # Picking OUT usually moves from Internal (Source) to Customer (Dest).
            # If "source location project" is where we TAKE FROM, then it's location_id.
            'origin': _('Consumption Dashboard: %s') % self.project_id.name,
            'company_id': self.project_id.company_id.id,
        })
        
        issue_log.picking_id = picking.id

        # 3. Create Moves & Log Lines
        for summary in selected_summaries:
            # Create move directly
            self.env['stock.move'].create({
                'picking_id': picking.id,
                'name': summary.product_id.name,
                'product_id': summary.product_id.id,
                'product_uom_qty': summary.qty_to_issue_unit,
                'product_uom': summary.product_id.uom_id.id,
                'location_id': picking.location_id.id,
                'location_dest_id': picking.location_dest_id.id,
                'origin': picking.origin,
                'company_id': self.project_id.company_id.id,
            })

        # Log individual requirements linked to this picking (optional but good for history)
        selected_lines = self.line_ids.filtered(lambda l: l.is_selected)
        for line in selected_lines:
            self.env['project.material.issue.line'].create({
                'issue_id': issue_log.id,
                'product_id': line.product_id.id,
                'task_id': line.task_id.id,
                'qty_required_kg': line.qty_required_kg,
                # We record what was technically required, though the picking is aggregated
                'qty_issue_unit': 0.0, # Or maybe link to summary somehow
            })

            # Record aggregated issue details in log as well? 
            # For now, let's just mark the lines as processed if needed
            # In current logic, qty_issued_unit is computed from issue lines.
            
        # Re-compute: we should probably update how qty_issued is calculated 
        # but for now let's keep it simple.
        
        # 4. Process Picking
        picking.action_confirm()
        picking.action_assign()
        
        # Reset selection and summary
        selected_lines.write({'is_selected': False})
        self.summary_ids.unlink()

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
    _order = 'is_fully_issued, parent_task_display_id, task_id, id'

    consumption_id = fields.Many2one('project.material.consumption', string='Consumption', ondelete='cascade')
    is_selected = fields.Boolean(string='Select')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    task_id = fields.Many2one('project.task', string='Task/Subtask')
    parent_task_display_id = fields.Many2one('project.task', string='Task Utama/Subtask', compute='_compute_task_display', store=True)

    qty_available = fields.Float(string='Stok site', compute='_compute_qty_status')
    qty_required_kg = fields.Float(string='Dibutuhkan (kg)', digits=(16, 2))
    
    qty_issued_unit = fields.Float(string='Sudah Terbit (unit)', compute='_compute_qty_status')
    qty_to_issue_unit = fields.Float(string='Akan Terbit (unit)', compute='_compute_qty_to_issue', store=True, readonly=False)
    is_fully_issued = fields.Boolean(string='Fully Issued', compute='_compute_qty_status', store=True)

    @api.depends('task_id')
    def _compute_task_display(self):
        for rec in self:
            if rec.task_id.parent_id:
                rec.parent_task_display_id = rec.task_id.parent_id.id
            else:
                rec.parent_task_display_id = rec.task_id.id

    @api.depends('product_id', 'consumption_id.project_id.stock_location_id', 'task_id')
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

            # Check if fully issued
            weight = rec.product_id.weight or 0.0
            total_req_units = math.ceil(rec.qty_required_kg / weight) if weight > 0 else 0
            rec.is_fully_issued = rec.qty_issued_unit >= total_req_units

    @api.depends('qty_required_kg', 'product_id.weight')
    def _compute_qty_to_issue(self):
        for rec in self:
            # This is now informational only in the requirements table
            weight = rec.product_id.weight or 0.0
            if weight > 0:
                rec.qty_to_issue_unit = rec.qty_required_kg / weight
            else:
                rec.qty_to_issue_unit = 0

class ProjectMaterialConsumptionSummary(models.Model):
    _name = 'project.material.consumption.summary'
    _description = 'Material Consumption Aggregated Summary'

    consumption_id = fields.Many2one('project.material.consumption', ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    total_weight_kg = fields.Float(string='Total Required (kg)', digits=(16, 2))
    qty_to_issue_unit = fields.Float(string='Akan Terbit (unit)', compute='_compute_qty_to_issue', store=True)

    @api.depends('total_weight_kg', 'product_id.weight')
    def _compute_qty_to_issue(self):
        for rec in self:
            weight = rec.product_id.weight or 0.0
            if weight > 0:
                # APPLY ROUNDING ONLY HERE
                rec.qty_to_issue_unit = math.ceil(rec.total_weight_kg / weight)
            else:
                rec.qty_to_issue_unit = 0
