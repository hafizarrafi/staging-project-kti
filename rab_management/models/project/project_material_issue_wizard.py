from odoo import models, fields, api, _
from odoo.exceptions import UserError
import math

class ProjectMaterialIssueWizard(models.TransientModel):
    _name = 'project.material.issue.wizard'
    _description = 'Generate Material Issue From Task'

    project_id = fields.Many2one('project.project', string='Project', required=True)
    task_ids = fields.Many2many('project.task', string='Tasks', domain="[('project_id', '=', project_id)]")
    line_ids = fields.One2many('project.material.issue.wizard.line', 'wizard_id', string='Preview Lines')

    @api.onchange('task_ids')
    def _onchange_task_ids(self):
        if not self.task_ids:
            self.line_ids = [(5, 0, 0)]
            return

        material_map = {} # (product_id, task_id) -> qty_kg
        for task in self.task_ids:
            # Aggregate from task product
            if task.product_id:
                key = (task.product_id.id, task.id)
                material_map.setdefault(key, 0.0)
                material_map[key] += task.weight or 0.0
            
            # Aggregate from material_needed_ids
            # We filter for 'manual' or 'subtask' based on current requirement logic
            for mat in task.material_needed_ids:
                if mat.product_id:
                    key = (mat.product_id.id, task.id)
                    material_map.setdefault(key, 0.0)
                    material_map[key] += mat.weight or 0.0

        line_vals = []
        for (pid, tid), qty_kg in material_map.items():
            product = self.env['product.product'].browse(pid)
            weight = product.weight or 1.0
            qty_unit = math.ceil(qty_kg / weight) if weight > 0 else 0
            
            line_vals.append((0, 0, {
                'product_id': pid,
                'task_id': tid,
                'qty_required_kg': qty_kg,
                'unit_weight': weight,
                'qty_issue_unit': qty_unit,
            }))
        
        self.line_ids = [(5, 0, 0)] + line_vals

    def action_create_issue(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("No items to issue."))

        issue = self.env['project.material.issue'].create({
            'project_id': self.project_id.id,
            'line_ids': [(0, 0, {
                'product_id': line.product_id.id,
                'task_id': line.task_id.id,
                'qty_required_kg': line.qty_required_kg,
                'qty_issue_unit': line.qty_issue_unit,
            }) for line in self.line_ids]
        })

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'project.material.issue',
            'res_id': issue.id,
            'view_mode': 'form',
            'target': 'current',
        }

class ProjectMaterialIssueWizardLine(models.TransientModel):
    _name = 'project.material.issue.wizard.line'
    _description = 'Material Issue Wizard Line'

    wizard_id = fields.Many2one('project.material.issue.wizard', string='Wizard')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    task_id = fields.Many2one('project.task', string='Task')
    qty_required_kg = fields.Float(string='Req. (kg)', digits=(16, 2))
    unit_weight = fields.Float(string='Unit Weight', digits=(16, 2))
    qty_issue_unit = fields.Float(string='Issue (unit)', digits=(16, 2))
