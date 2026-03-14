from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ProjectMaterialConsumption(models.Model):
    _name = 'project.material.consumption'
    _description = 'Material Consumption tracking'
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
    ], string='Status', default='draft', tracking=True)

    line_ids = fields.One2many(
        'project.material.consumption.line',
        'consumption_id',
        string='Consumption Lines',
        copy=True
    )

    picking_id = fields.Many2one(
        'stock.picking',
        string='Consumption DO',
        readonly=True,
        copy=False
    )

    @api.onchange('project_id')
    def _onchange_project_id_load_requirements(self):
        if not self.project_id:
            self.line_ids = [(5, 0, 0)]
            return

        # Get all material requirements from tasks in this project
        tasks = self.env['project.task'].search([('project_id', '=', self.project_id.id)])
        line_vals = []
        
        for task in tasks:
            for mat in task.material_needed_ids:
                # We use the weight (kg) as the required amount
                line_vals.append((0, 0, {
                    'task_id': task.id,
                    'product_id': mat.product_id.id,
                    'qty_required_kg': mat.weight or 0.0,
                    'qty_used': 0.0,
                }))
        
        self.line_ids = [(5, 0, 0)] + line_vals

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('project.material.consumption') or _('New')
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
            picking_type = self.env['stock.picking.type'].search([('code', '=', 'outgoing')], limit=1)

        if not picking_type:
            raise UserError(_("No outgoing picking type found."))

        # Consumption: from Project Location to Virtual Location (Customer/Scrap/etc)
        src_location = self.project_id.stock_location_id
        dest_location = picking_type.default_location_dest_id

        if not src_location:
            raise UserError(_("Project does not have a stock location."))

        res = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': src_location.id,
            'location_dest_id': dest_location.id,
            'origin': self.name,
            'project_id': self.project_id.id,
            'partner_id': self.project_id.partner_id.id,
            'move_ids': [(0, 0, {
                'name': self.name,
                'product_id': line.product_id.id,
                'product_uom_qty': line.qty_used,
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

class ProjectMaterialConsumptionLine(models.Model):
    _name = 'project.material.consumption.line'
    _description = 'Material Consumption Line'

    consumption_id = fields.Many2one('project.material.consumption', string='Consumption', ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    task_id = fields.Many2one('project.task', string='Task')

    qty_available = fields.Float(string='Stok (uom)', compute='_compute_qty_available')
    qty_required_kg = fields.Float(string='Dibutuhkan (kg)', digits=(16, 2))
    qty_used = fields.Float(string='Aktual (kg)', required=True, default=0.0)
    qty_remaining = fields.Float(string='Sisa (kg)', compute='_compute_qty_remaining', store=True)

    @api.depends('product_id', 'consumption_id.project_id.stock_location_id')
    def _compute_qty_available(self):
        for rec in self:
            if not rec.product_id or not rec.consumption_id.project_id.stock_location_id:
                rec.qty_available = 0.0
                continue
            
            # Using Odoo's stock.quant to get real available quantity at project site
            domain = [
                ('product_id', '=', rec.product_id.id),
                ('location_id', '=', rec.consumption_id.project_id.stock_location_id.id)
            ]
            quants = self.env['stock.quant'].search(domain)
            rec.qty_available = sum(quants.mapped('quantity'))

    @api.depends('qty_required_kg', 'qty_used')
    def _compute_qty_remaining(self):
        for rec in self:
            rec.qty_remaining = rec.qty_required_kg - rec.qty_used
