from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ProjectMaterialConsumptionWizard(models.TransientModel):
    _name = 'project.material.consumption.wizard'
    _description = 'Consolidated Material Consumption Wizard'

    project_id = fields.Many2one('project.project', string='Project', required=True)
    date = fields.Date(string='Date', default=fields.Date.today, required=True)
    line_ids = fields.One2many(
        'project.material.consumption.wizard.line',
        'wizard_id',
        string='Consumption Lines'
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        project_id = self.env.context.get('default_project_id')
        if not project_id:
            return res
        
        project = self.env['project.project'].browse(project_id)
        # Get all tasks in this project
        tasks = self.env['project.task'].search([('project_id', '=', project.id)])
        
        line_vals = []
        for task in tasks:
            for mat in task.material_needed_ids:
                # Calculate consumed so far from project.task.material.actual
                past_consumptions = self.env['project.task.material.actual'].search([
                    ('task_id', '=', task.id),
                    ('product_id', '=', mat.product_id.id)
                ])
                total_consumed = sum(past_consumptions.mapped('qty_actual'))
                
                # Get available stock at project site
                qty_available = 0.0
                if project.stock_location_id:
                    quants = self.env['stock.quant'].search([
                        ('product_id', '=', mat.product_id.id),
                        ('location_id', '=', project.stock_location_id.id)
                    ])
                    qty_available = sum(quants.mapped('quantity'))

                line_vals.append((0, 0, {
                    'task_id': task.id,
                    'product_id': mat.product_id.id,
                    'qty_available': qty_available,
                    'qty_required_kg': mat.weight or 0.0,
                    'qty_consumed_kg': total_consumed,
                    'qty_remaining_kg': (mat.weight or 0.0) - total_consumed,
                }))
        
        res['line_ids'] = line_vals
        return res

    def action_process(self):
        self.ensure_one()
        lines = self.line_ids.filtered(lambda l: l.qty_input > 0)
        if not lines:
            raise UserError(_("No usage entered (Aktual kg must be > 0)."))

        # 1. Create Consumption Log (Header)
        consumption_header = self.env['project.material.consumption'].create({
            'project_id': self.project_id.id,
            'date': self.date,
            'state': 'draft',
        })

        # 2. Create Consumption Lines and Task Actuals
        for line in lines:
            # Add to project.material.consumption lines
            self.env['project.material.consumption.line'].create({
                'consumption_id': consumption_header.id,
                'task_id': line.task_id.id,
                'product_id': line.product_id.id,
                'qty_required_kg': line.qty_required_kg,
                'qty_used': line.qty_input,
            })

            # Add to project.task.material.actual (Task Ledger)
            self.env['project.task.material.actual'].create({
                'task_id': line.task_id.id,
                'product_id': line.product_id.id,
                'qty_actual': line.qty_input,
                'date': self.date,
            })

        # 3. Confirm and Generate DO
        consumption_header.action_confirm()
        res = consumption_header.action_generate_picking()
        
        # Return the picking view
        return res

class ProjectMaterialConsumptionWizardLine(models.TransientModel):
    _name = 'project.material.consumption.wizard.line'
    _description = 'Consolidated Consumption Wizard Line'

    wizard_id = fields.Many2one('project.material.consumption.wizard', string='Wizard')
    task_id = fields.Many2one('project.task', string='Task/Subtask')
    product_id = fields.Many2one('product.product', string='Material')
    qty_available = fields.Float(string='Stok (uom)')
    qty_required_kg = fields.Float(string='Dibutuhkan (kg)')
    qty_consumed_kg = fields.Float(string='Sudah Terpakai (kg)')
    qty_remaining_kg = fields.Float(string='Sisa (kg)')
    qty_input = fields.Float(string='Aktual (kg)')
