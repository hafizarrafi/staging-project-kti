from odoo import models, fields, api, _
from odoo.exceptions import UserError
import math

class ProjectMaterialIssue(models.Model):
    _name = 'project.material.issue'
    _description = 'Material Issue Planning'
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
        string='Date',
        default=fields.Date.today,
        required=True,
        tracking=True
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    line_ids = fields.One2many(
        'project.material.issue.line',
        'issue_id',
        string='Issue Lines'
    )

    picking_id = fields.Many2one(
        'stock.picking',
        string='Delivery Order',
        readonly=True,
        copy=False
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('project.material.issue') or _('New')
        return super().create(vals_list)

    def action_confirm(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError(_("Please add at least one line."))
            rec.state = 'confirmed'

    def action_generate_picking(self):
        self.ensure_one()
        if not self.line_ids:
            raise UserError(_("No lines to process."))

        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'outgoing'),
            ('warehouse_id.company_id', '=', self.project_id.company_id.id),
        ], limit=1)

        if not picking_type:
            # Fallback to any outgoing
            picking_type = self.env['stock.picking.type'].search([('code', '=', 'outgoing')], limit=1)

        if not picking_type:
            raise UserError(_("No outgoing picking type found."))

        src_location = picking_type.default_location_src_id
        dest_location = self.project_id.stock_location_id

        if not dest_location:
            raise UserError(_("Project does not have a stock location."))

        res = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': src_location.id,
            'location_dest_id': dest_location.id,
            'origin': self.name,
            'project_id': self.project_id.id, # If field exists in stock.picking
            'partner_id': self.project_id.partner_id.id,
            'move_ids': [(0, 0, {
                'name': self.name,
                'product_id': line.product_id.id,
                'product_uom_qty': line.qty_issue_unit,
                'product_uom': line.product_id.uom_id.id,
                'location_id': src_location.id,
                'location_dest_id': dest_location.id,
            }) for line in self.line_ids]
        })
        self.picking_id = res.id
        self.state = 'done'
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'res_id': res.id,
            'view_mode': 'form',
            'target': 'current',
        }

class ProjectMaterialIssueLine(models.Model):
    _name = 'project.material.issue.line'
    _description = 'Material Issue Planning Line'

    issue_id = fields.Many2one('project.material.issue', string='Issue', ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    task_id = fields.Many2one('project.task', string='Task')

    qty_required_kg = fields.Float(string='Req. (kg)', digits=(16, 2))
    unit_weight = fields.Float(string='Unit Weight', related='product_id.weight', readonly=True)
    
    qty_issue_unit = fields.Float(string='Issue (unit)', compute='_compute_qty_issue_unit', store=True, readonly=False)

    actual_weight_kg = fields.Float(string='Actual (kg)', compute='_compute_actual_weight', store=True)
    remaining_weight_kg = fields.Float(string='Remaining (kg)', compute='_compute_actual_weight', store=True)

    @api.depends('qty_required_kg', 'product_id.weight')
    def _compute_qty_issue_unit(self):
        for rec in self:
            weight = rec.product_id.weight or 1.0
            rec.qty_issue_unit = math.ceil(rec.qty_required_kg / weight) if weight > 0 else 0

    @api.depends('qty_issue_unit', 'qty_required_kg', 'product_id.weight')
    def _compute_actual_weight(self):
        for rec in self:
            weight = rec.product_id.weight or 0.0
            rec.actual_weight_kg = rec.qty_issue_unit * weight
            rec.remaining_weight_kg = rec.actual_weight_kg - rec.qty_required_kg
