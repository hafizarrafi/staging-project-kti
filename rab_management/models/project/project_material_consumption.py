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
    display_stock_location = fields.Many2one(
        'stock.location',
        string='Source Location',
        related='project_id.stock_location_id',
        readonly=True
    )
    search_product_id = fields.Many2one('product.product', string='Filter Produk')
    search_task_id = fields.Many2one('project.task', string='Filter Pekerjaan')
    search_source_type = fields.Selection([
        ('task_primary', 'Pekerjaan Utama'),
        ('task_additional', 'Pekerjaan Additional'),
        ('additional', 'Additional Material'),
        ('equipment_primary', 'Equipment'),
        ('equipment_additional', 'Equipment Additional')
    ], string='Filter Sumber', default='task_primary')
    
    @api.onchange('search_source_type', 'search_product_id', 'search_task_id')
    def _onchange_filters_refresh(self):
        # Only task types need the task filter
        if self.search_source_type not in ['task_primary', 'task_additional']:
            self.search_task_id = False
        return self.action_refresh_requirements()

    def action_filter_task_primary(self):
        self.search_source_type = 'task_primary'
        return self.action_refresh_requirements()

    def action_filter_task_additional(self):
        self.search_source_type = 'task_additional'
        return self.action_refresh_requirements()

    def action_filter_additional_material(self):
        self.search_source_type = 'additional'
        return self.action_refresh_requirements()

    def action_filter_equipment_primary(self):
        self.search_source_type = 'equipment_primary'
        return self.action_refresh_requirements()

    def action_filter_equipment_additional(self):
        self.search_source_type = 'equipment_additional'
        return self.action_refresh_requirements()

    def action_view_project(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'project.project',
            'res_id': self.project_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
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

    @api.onchange('project_id')
    def _onchange_project_id_refresh(self):
        if self.project_id:
            return self.action_refresh_requirements()

    def action_calculate_summary(self):
        """Aggregate selected requirements into summary table. Merges with existing summary."""
        self.ensure_one()
        
        selected_lines = self.line_ids.filtered(lambda l: l.is_selected)
        if not selected_lines:
            return
            
        # Group by product_id
        aggregation = {} # product_id -> {weight, units, any_issued, fully_issued, is_task_source}
        for line in selected_lines:
            pid = line.product_id.id
            is_task_source = line.source_type in ['task_primary', 'task_additional']
            
            if pid not in aggregation:
                aggregation[pid] = {
                    'weight': 0.0, 
                    'units': 0.0, 
                    'any_issued': False, 
                    'fully_issued': True,
                    'product': line.product_id,
                    'is_task_source': is_task_source
                }
            
            data = aggregation[pid]
            data['weight'] += line.qty_required_kg
            data['any_issued'] = data['any_issued'] or (line.qty_issued_unit > 0)
            data['fully_issued'] = data['fully_issued'] and (line.qty_remaining_unit <= 0)
            
            if not is_task_source:
                data['units'] += line.qty_remaining_unit
        
        summary_vals = []
        existing_summary = {s.product_id.id: s for s in self.summary_ids}
        
        for pid, data in aggregation.items():
            units = data['units']
            if data['is_task_source']:
                p_weight = data['product'].weight or 0.0
                units = math.ceil(data['weight'] / p_weight) if p_weight > 0 else 0
            
            is_readonly = data['any_issued'] if data['is_task_source'] else data['fully_issued']

            if pid in existing_summary:
                # Update existing summary record
                existing_summary[pid].write({
                    'total_weight_kg': data['weight'],
                    'total_qty_unit': units,
                    'qty_to_issue_unit': units,
                    'is_readonly': is_readonly,
                })
            else:
                # Create new summary record
                summary_vals.append((0, 0, {
                    'consumption_id': self.id,
                    'product_id': pid,
                    'total_weight_kg': data['weight'],
                    'total_qty_unit': units,
                    'qty_to_issue_unit': units,
                    'is_readonly': is_readonly,
                }))
        
        if summary_vals:
            self.summary_ids = summary_vals

    def _compute_stock_quants(self):
        for rec in self:
            if rec.project_id.stock_location_id:
                rec.stock_quant_ids = self.env['stock.quant'].search([
                    ('location_id', 'child_of', rec.project_id.stock_location_id.id)
                ])
            else:
                rec.stock_quant_ids = False


    def action_refresh_requirements(self):
        for rec in self:
            if not rec.project_id:
                rec.line_ids = [(5, 0, 0)]
                continue

            # Load Search Filters
            sf_product = rec.search_product_id
            sf_task = rec.search_task_id

            # 1. TASK SOURCES
            tasks_domain = [('project_id', '=', rec.project_id.id)]
            if sf_task:
                tasks_domain.append(('id', 'child_of', sf_task.id))
            
            if rec.search_source_type == 'task_primary':
                tasks_domain.append(('job_type', '=', 'primary'))
            elif rec.search_source_type == 'task_additional':
                tasks_domain.append(('job_type', '=', 'additional'))
            
            tasks = self.env['project.task'].search(tasks_domain)
            
            # 2. ADDITIONAL PURCHASE SOURCE (Material Only, Manual Only)
            ap_domain = [('project_id', '=', rec.project_id.id), ('item_type', '=', 'material'), ('source', '=', 'manual')]
            if sf_product:
                ap_domain.append(('product_id', '=', sf_product.id))
            if sf_task:
                # Only show purchases linked to this task or its subtasks
                ap_domain.append(('task_id', 'child_of', sf_task.id))
            additional_purchases = self.env['project.additional.purchase'].search(ap_domain)
            
            # 3. EQUIPMENT MASTER SOURCE
            equipment_masters = []
            eq_domain = [('project_id', '=', rec.project_id.id)]
            if sf_product:
                eq_domain.append(('product_id', '=', sf_product.id))
            
            if rec.search_source_type == 'equipment_primary':
                eq_domain.append(('job_type', '=', 'primary'))
                equipment_masters = self.env['project.equipment.master'].search(eq_domain)
            elif rec.search_source_type == 'equipment_additional':
                eq_domain.append(('job_type', '=', 'additional'))
                equipment_masters = self.env['project.equipment.master'].search(eq_domain)
            elif not rec.search_source_type: # Global refresh fallback
                equipment_masters = self.env['project.equipment.master'].search(eq_domain)

            # 4. ADDITIONAL EQUIPMENT SOURCE (Purchases with type equipment)
            ap_equipment = []
            if rec.search_source_type == 'equipment_additional' or not rec.search_source_type:
                ap_eq_domain = [('project_id', '=', rec.project_id.id), ('item_type', '=', 'equipment')]
                if sf_product:
                    ap_eq_domain.append(('product_id', '=', sf_product.id))
                if sf_task:
                    ap_eq_domain.append(('task_id', 'child_of', sf_task.id))
                ap_equipment = self.env['project.additional.purchase'].search(ap_eq_domain)

            # Map existing lines for preservation
            existing_lines = {}
            for l in rec.line_ids:
                key = (l.task_id.id, l.product_id.id, l.source_type, l.additional_purchase_id.id, l.equipment_master_id.id)
                existing_lines[key] = l
            
            line_vals = []
            seen_requirements = set()

            def process_requirement(vals, key):
                # Filter by source type if set
                if rec.search_source_type and vals.get('source_type') != rec.search_source_type:
                    return

                # Filter by product if set
                if sf_product and vals.get('product_id') != sf_product.id:
                    return
                
                seen_requirements.add(key)
                if key in existing_lines:
                    line = existing_lines[key]
                    update_vals = {}
                    if line.qty_required_kg != vals.get('qty_required_kg', 0.0):
                        update_vals['qty_required_kg'] = vals.get('qty_required_kg', 0.0)
                    if line.qty_required_unit != vals.get('qty_required_unit', 0.0):
                        update_vals['qty_required_unit'] = vals.get('qty_required_unit', 0.0)
                    
                    if update_vals:
                        line_vals.append((1, line.id, update_vals))
                else:
                    line_vals.append((0, 0, vals))

            # PROCESS TASK REQUIREMENTS
            for task in tasks:
                source_type = 'task_primary' if task.job_type == 'primary' else 'task_additional'
                
                # Direct product on task
                if task.product_id:
                    key = (task.id, task.product_id.id, source_type, False, False)
                    weight = task.product_id.weight or 0.0
                    total_kg = task.weight or 0.0
                    units = math.ceil(total_kg / weight) if weight > 0 else 0
                    process_requirement({
                        'task_id': task.id,
                        'product_id': task.product_id.id,
                        'qty_required_kg': total_kg,
                        'qty_required_unit': total_kg, # Standardize to KG for tracking
                        'source_type': source_type,
                    }, key)
                
                # Manual entries
                for mat in task.material_needed_ids:
                    if mat.source != 'manual': continue
                    key = (task.id, mat.product_id.id, source_type, False, False)
                    weight = mat.product_id.weight or 0.0
                    total_kg = mat.weight or 0.0
                    units = math.ceil(total_kg / weight) if weight > 0 else 0
                    process_requirement({
                        'task_id': task.id,
                        'product_id': mat.product_id.id,
                        'qty_required_kg': total_kg,
                        'qty_required_unit': total_kg, # Standardize to KG for tracking
                        'source_type': source_type,
                    }, key)

            # PROCESS ADDITIONAL PURCHASES (Material)
            for ap in additional_purchases:
                key = (False, ap.product_id.id, 'additional', ap.id, False)
                process_requirement({
                    'product_id': ap.product_id.id,
                    'qty_required_kg': ap.total_weight or 0.0,
                    'qty_required_unit': ap.total_qty or 0.0,
                    'source_type': 'additional',
                    'additional_purchase_id': ap.id,
                }, key)

            # PROCESS EQUIPMENT MASTER
            for eq in equipment_masters:
                source_type = 'equipment_primary' if eq.job_type == 'primary' else 'equipment_additional'
                key = (False, eq.product_id.id, source_type, False, eq.id)
                process_requirement({
                    'product_id': eq.product_id.id,
                    'qty_required_kg': 0.0,
                    'qty_required_unit': eq.total_qty or 0.0,
                    'source_type': source_type,
                    'equipment_master_id': eq.id,
                }, key)

            # PROCESS ADDITIONAL EQUIPMENT PURCHASE
            for ap in ap_equipment:
                key = (False, ap.product_id.id, 'equipment_additional', ap.id, False) # Maps to additional eq source
                process_requirement({
                    'product_id': ap.product_id.id,
                    'qty_required_kg': ap.total_weight or 0.0,
                    'qty_required_unit': ap.total_qty or 0.0,
                    'source_type': 'equipment_additional',
                    'additional_purchase_id': ap.id,
                }, key)
            
            # Remove stale lines (BUT KEEP SELECTED ONES)
            for key, line in existing_lines.items():
                if key not in seen_requirements and not line.is_selected:
                    line_vals.append((2, line.id, 0))
            
            if line_vals:
                rec.line_ids = line_vals

    def action_generate_picking(self):
        self.ensure_one()
        # Use summary_ids instead of line_ids
        selected_summaries = self.summary_ids.filtered(lambda s: s.qty_to_issue_unit > 0)
        
        if not selected_summaries:
            raise UserError(_("Please calculate selection and ensure 'Akan Terbit' > 0."))

        # Search for picking type specifically with "OUT" in sequence or name
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'outgoing'),
            ('warehouse_id.company_id', '=', self.project_id.company_id.id),
            '|', ('sequence_id.name', 'ilike', 'OUT'), ('sequence_id.prefix', 'ilike', 'OUT')
        ], limit=1)

        if not picking_type:
            # Fallback to any outgoing that isn't POS or similar if possible
            picking_type = self.env['stock.picking.type'].search([
                ('code', '=', 'outgoing'),
                ('warehouse_id.company_id', '=', self.project_id.company_id.id),
                ('name', 'not ilike', 'POS')
            ], limit=1)

        if not picking_type:
            raise UserError(_("No 'outgoing' picking type found."))

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

        # Create stock moves and log lines per summary item
        selected_lines = self.line_ids.filtered(lambda l: l.is_selected)
        for summary in selected_summaries:
            self.env['stock.move'].create({
                'picking_id': picking.id,
                'description_picking': summary.product_id.name,
                'product_id': summary.product_id.id,
                'product_uom_qty': summary.qty_to_issue_unit,
                'product_uom': summary.product_id.uom_id.id,
                'location_id': picking.location_id.id,
                'location_dest_id': picking.location_dest_id.id,
                'origin': picking.origin,
                'company_id': self.project_id.company_id.id,
            })

            is_task_source = self.search_source_type in ['task_primary', 'task_additional']
            product_lines = selected_lines.filtered(lambda l: l.product_id == summary.product_id)

            if is_task_source:
                # Task sources: log each selected line as fully issued in weight terms
                for line in product_lines:
                    prod_weight = line.product_id.weight or 0.0
                    decimal_units = (line.qty_required_kg / prod_weight) if prod_weight > 0 else 1.0

                    self.env['project.material.issue.line'].create({
                        'issue_id': issue_log.id,
                        'product_id': line.product_id.id,
                        'task_id': line.task_id.id,
                        'qty_required_kg': line.qty_required_kg,
                        'qty_issue_unit': decimal_units,
                        'qty_issued_weight': line.qty_required_kg,
                    })
            else:
                # Distribute the DO quantity among individual lines (piece-based)
                remaining_to_distribute = summary.qty_to_issue_unit
                for line in product_lines:
                    if remaining_to_distribute <= 0:
                        break

                    line_remaining = line.qty_remaining_unit
                    if line_remaining <= 0:
                        continue

                    issue_qty = min(line_remaining, remaining_to_distribute)

                    self.env['project.material.issue.line'].create({
                        'issue_id': issue_log.id,
                        'product_id': line.product_id.id,
                        'task_id': line.task_id.id,
                        'additional_purchase_id': line.additional_purchase_id.id,
                        'equipment_master_id': line.equipment_master_id.id,
                        'qty_required_kg': line.qty_required_kg,
                        'qty_issue_unit': issue_qty,
                        'qty_issued_weight': issue_qty * (line.product_id.weight or 0.0),
                    })
                    remaining_to_distribute -= issue_qty

                # Edge case: attribute any leftover quantity to the last log line
                if remaining_to_distribute > 0 and product_lines:
                    log_line = self.env['project.material.issue.line'].search([
                        ('issue_id', '=', issue_log.id),
                        ('product_id', '=', summary.product_id.id)
                    ], limit=1, order='id desc')
                    if log_line:
                        log_line.qty_issue_unit += remaining_to_distribute

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
    _order = 'parent_task_display_id, task_id, id'

    consumption_id = fields.Many2one('project.material.consumption', string='Consumption', ondelete='cascade')
    is_selected = fields.Boolean(string='Select')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    task_id = fields.Many2one('project.task', string='Task/Subtask')
    additional_purchase_id = fields.Many2one('project.additional.purchase', string='Additonal Purchase Line')
    equipment_master_id = fields.Many2one('project.equipment.master', string='Equipment Line')
    
    source_type = fields.Selection([
        ('task_primary', 'Pekerjaan Utama'),
        ('task_additional', 'Pekerjaan Additional'),
        ('additional', 'Additional Material'),
        ('equipment_primary', 'Equipment'),
        ('equipment_additional', 'Equipment Additional')
    ], string='Sumber', default='task_primary')
    
    product_uom_id = fields.Many2one('uom.uom', string='UoM', related='product_id.uom_id', readonly=True)
    
    parent_task_display_id = fields.Many2one('project.task', string='Task Utama', compute='_compute_task_display', store=True)
    subtask_display_name = fields.Char(string='Subtask/Detail', compute='_compute_task_display', store=True)

    qty_available = fields.Float(string='Stok site', compute='_compute_qty_available')
    qty_required_kg = fields.Float(string='Dibutuhkan (kg)', digits=(16, 2))
    qty_required_unit = fields.Float(string='Butuh (unit)', digits=(16, 2))
    qty_issued_unit = fields.Float(string='Sudah Terbit (unit)', compute='_compute_qty_issued', store=False)
    qty_remaining_unit = fields.Float(string='Sisa (unit)', compute='_compute_qty_remaining', store=False)
    qty_to_issue_unit = fields.Float(string='Butuh (unit)', compute='_compute_qty_to_issue', store=False)
    
    is_fully_issued = fields.Boolean(string='Terbit Penuh', compute='_compute_issue_status', store=False)
    is_partially_issued = fields.Boolean(string='Terbit Sebagian', compute='_compute_issue_status', store=False)
    allow_partial_issue = fields.Boolean(string='Allow Partial', compute='_compute_allow_partial', store=False)
    is_selectable = fields.Boolean(string='Dapat Dipilih', compute='_compute_is_selectable')
    selection_status = fields.Char(string='Status', compute='_compute_is_selectable')

    def action_select_line(self):
        for rec in self:
            if rec.is_selectable:
                rec.is_selected = True

    def action_deselect_line(self):
        for rec in self:
            rec.is_selected = False

    @api.depends('qty_issued_unit', 'source_type', 'is_fully_issued')
    def _compute_is_selectable(self):
        for rec in self:
            if rec.source_type in ['task_primary', 'task_additional']:
                # For tasks: selectable ONLY if absolutely zero has been issued
                rec.is_selectable = (rec.qty_issued_unit == 0)
            else:
                # For manual/equipment: selectable if not fully issued
                rec.is_selectable = not rec.is_fully_issued
            
            rec.selection_status = _('Sudah Terbit') if not rec.is_selectable else ''

    @api.depends('task_id', 'task_id.parent_id', 'task_id.name', 'source_type', 'additional_purchase_id', 'equipment_master_id')
    def _compute_task_display(self):
        for rec in self:
            if rec.source_type == 'additional' and rec.additional_purchase_id:
                rec.parent_task_display_id = False
                rec.subtask_display_name = rec.additional_purchase_id.source_details
            elif rec.source_type in ['equipment_primary', 'equipment_additional'] and rec.equipment_master_id:
                rec.parent_task_display_id = False
                rec.subtask_display_name = _("Equipment: %s") % (rec.equipment_master_id.job_type or '')
            elif rec.source_type in ['task_primary', 'task_additional'] and rec.task_id:
                # Find the root task (top level)
                parent = rec.task_id
                while parent.parent_id:
                    parent = parent.parent_id
                rec.parent_task_display_id = parent.id
                
                # Show subtask name if it's not the root itself
                if rec.task_id.id != parent.id:
                    rec.subtask_display_name = rec.task_id.name
                else:
                    rec.subtask_display_name = False
            else:
                rec.parent_task_display_id = False
                rec.subtask_display_name = False

    def _compute_qty_available(self):
        # Batch Fetch Stock Quants for all lines
        if not self:
            return
            
        location_ids = self.mapped('consumption_id.project_id.stock_location_id').ids
        product_ids = self.mapped('product_id').ids
        
        # Search quants once
        quants = self.env['stock.quant'].search([
            ('product_id', 'in', product_ids),
            ('location_id', 'child_of', location_ids)
        ])
        
        # Aggregate in memory
        stock_map = {} # (location_id, product_id) -> qty
        for q in quants:
            key = (q.location_id.id, q.product_id.id)
            stock_map[key] = stock_map.get(key, 0.0) + q.quantity
            
        for rec in self:
            loc_id = rec.consumption_id.project_id.stock_location_id.id
            rec.qty_available = stock_map.get((loc_id, rec.product_id.id), 0.0)

    def _compute_qty_issued(self):
        # Batch Fetch Issued Quantities using read_group (N+1 Fix)
        if not self:
            return
            
        product_ids = self.mapped('product_id').ids
        task_ids = self.mapped('task_id').ids
        ap_ids = self.mapped('additional_purchase_id').ids
        eq_ids = self.mapped('equipment_master_id').ids
        
        groups = self.env['project.material.issue.line'].read_group(
            [
                ('product_id', 'in', product_ids),
                ('issue_id.state', '!=', 'cancel'),
                '|', '|',
                    ('task_id', 'in', task_ids),
                    ('additional_purchase_id', 'in', ap_ids),
                    ('equipment_master_id', 'in', eq_ids)
            ],
            ['qty_issue_unit:sum', 'qty_issued_weight:sum', 'task_id', 'product_id', 'additional_purchase_id', 'equipment_master_id'],
            ['task_id', 'product_id', 'additional_purchase_id', 'equipment_master_id'],
            lazy=False
        )
        
        amounts_unit = {} 
        amounts_weight = {}
        for res in groups:
            key = (
                res['task_id'][0] if res['task_id'] else False, 
                res['product_id'][0],
                res['additional_purchase_id'][0] if res['additional_purchase_id'] else False,
                res['equipment_master_id'][0] if res['equipment_master_id'] else False
            )
            amounts_unit[key] = res['qty_issue_unit']
            amounts_weight[key] = res['qty_issued_weight']
            
        for rec in self:
            key = (rec.task_id.id, rec.product_id.id, rec.additional_purchase_id.id, rec.equipment_master_id.id)
            if rec.source_type in ['task_primary', 'task_additional']:
                # Task sources are measured in KG on the dashboard
                rec.qty_issued_unit = amounts_weight.get(key, 0.0)
            else:
                # Manual/Equipment sources are measured in Units
                rec.qty_issued_unit = amounts_unit.get(key, 0.0)

    @api.depends('qty_issued_unit', 'qty_required_unit')
    def _compute_qty_remaining(self):
        for rec in self:
            rec.qty_remaining_unit = max(0.0, rec.qty_required_unit - rec.qty_issued_unit)

    @api.depends('qty_issued_unit', 'qty_required_unit', 'allow_partial_issue')
    def _compute_issue_status(self):
        for rec in self:
            rec.is_fully_issued = rec.qty_issued_unit >= rec.qty_required_unit and rec.qty_required_unit > 0
            # Strictly show partial ONLY if allow_partial_issue is True (Manual/Eq)
            rec.is_partially_issued = rec.allow_partial_issue and 0 < rec.qty_issued_unit < rec.qty_required_unit

    @api.depends('source_type')
    def _compute_allow_partial(self):
        for rec in self:
            # Partial issue ONLY for non-task sources
            rec.allow_partial_issue = rec.source_type not in ['task_primary', 'task_additional']

    @api.depends('qty_required_kg', 'product_id.weight', 'qty_required_unit')
    def _compute_qty_to_issue(self):
        for rec in self:
            # This is now informational only in the requirements table
            weight = rec.product_id.weight or 0.0
            if weight > 0:
                rec.qty_to_issue_unit = rec.qty_required_kg / weight
            else:
                rec.qty_to_issue_unit = rec.qty_required_unit

class ProjectMaterialConsumptionSummary(models.Model):
    _name = 'project.material.consumption.summary'
    _description = 'Material Consumption Aggregated Summary'

    consumption_id = fields.Many2one('project.material.consumption', ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    total_weight_kg = fields.Float(string='Total Required (kg)', digits=(16, 2))
    total_qty_unit = fields.Float(string='Total Required (unit)', digits=(16, 2))
    qty_to_issue_unit = fields.Float(string='Akan Terbit (unit)', digits=(16, 2))
    is_readonly = fields.Boolean(string='Readonly') # Calculated during aggregation

    def action_remove_summary(self):
        self.ensure_one()
        # Unselect all matching lines in the requirement table
        lines_to_unselect = self.consumption_id.line_ids.filtered(lambda l: l.product_id == self.product_id)
        lines_to_unselect.write({'is_selected': False})
        self.unlink()
