from odoo import models, fields


class ProjectTaskMaterialActual(models.Model):
    _name = 'project.task.material.actual'
    _description = 'Aktual Konsumsi Material per Task'
    _order = 'date desc, id desc'

    task_id = fields.Many2one(
        'project.task',
        required=True,
        ondelete='cascade'
    )
    product_id = fields.Many2one(
        'product.product',
        string='Material',
        domain=[('categ_id.name', '=', 'Material')],
        required=True
    )
    qty_actual = fields.Float(
        string='Qty Aktual',
        digits=(16, 2),
        required=True,
        default=1.0
    )
    uom_id = fields.Many2one(
        related='product_id.uom_id',
        readonly=True,
        string='Satuan'
    )
    date = fields.Date(
        string='Tanggal Konsumsi',
        default=fields.Date.today,
        required=True
    )
    note = fields.Char(string='Keterangan')
