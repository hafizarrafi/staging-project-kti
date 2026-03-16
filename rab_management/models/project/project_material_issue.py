from odoo import models, fields, api, _
from odoo.exceptions import UserError
import math

class ProjectMaterialIssue(models.Model):
    _name = 'project.material.issue'
    _description = 'Material Issue Log (History)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )
    project_id = fields.Many2one(
        'project.project',
        string='Project',
        required=True,
        tracking=True
    )
    date = fields.Date(
        string='Issue Date',
        default=fields.Date.today,
        required=True,
        tracking=True
    )
    state = fields.Selection([
        ('confirmed', 'Confirmed'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='confirmed', tracking=True)

    line_ids = fields.One2many(
        'project.material.issue.line',
        'issue_id',
        string='Issued Items'
    )

    picking_id = fields.Many2one(
        'stock.picking',
        string='Related DO',
        readonly=True,
        copy=False
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('project.material.issue') or _('New')
        return super().create(vals_list)

class ProjectMaterialIssueLine(models.Model):
    _name = 'project.material.issue.line'
    _description = 'Material Issue Log Line'

    issue_id = fields.Many2one('project.material.issue', string='Issue Log', ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    task_id = fields.Many2one('project.task', string='Task')
    additional_purchase_id = fields.Many2one('project.additional.purchase', string='Additional Purchase')
    equipment_master_id = fields.Many2one('project.equipment.master', string='Equipment Master')

    qty_required_kg = fields.Float(string='Orig. Req (kg)', digits=(16, 2))
    qty_issue_unit = fields.Float(string='Issued (unit)', digits='Product Unit of Measure')
    qty_issued_weight = fields.Float(string='Weight Issued (kg)', digits=(16, 2))
