from odoo import models, fields, api

class ProjectTaskMaterial(models.Model):
    _name = 'project.task.material'
    _description = 'Material Needed per Task'

    task_id = fields.Many2one(
        'project.task',
        required=True,
        ondelete='cascade'
    )

    product_id = fields.Many2one(
        'product.product',
        domain=[('categ_id.name','=','Material')],
        required=True
    )
    
    weight = fields.Float(
        string='Weight (kg)',
        digits=(16, 2),
        help='Berat material ini untuk task terkait'
    )

    total_qty = fields.Float(required=True)
    uom_id = fields.Many2one(
        related='product_id.uom_id',
        readonly=True
    )

    qty_actual = fields.Float(
        string='Jumlah Aktual',
        digits=(16, 2),
        default=0.0
    )

    qty_on_site = fields.Float(
        string='Qty On Site',
        default=0.0
    )

    qty_beli = fields.Float(
        string='Qty Beli',
        compute='_compute_qty_beli',
        store=True
    )


    source = fields.Selection(
        [
            ('subtask', 'From Subtask'),
            ('manual', 'Manual Adjustment'),
        ],
        default='subtask'
    )

    source_task_id = fields.Many2one(
        'project.task',
        string='Source Task',
        readonly=True
    )

    source_level = fields.Selection(
        [
            ('level_1', 'Subtask'),
            ('level_2', 'Sub-subtask'),
            ('level_3', 'Sub-sub-subtask'),
        ],
        string='Source Level',
        readonly=True
    )
    source_path = fields.Char(
        string='Source Path',
    )

    @api.depends('total_qty', 'qty_on_site')
    def _compute_qty_beli(self):
        for rec in self:
            rec.qty_beli = max(
                (rec.total_qty or 0.0) - (rec.qty_on_site or 0.0),
                0.0
            )
