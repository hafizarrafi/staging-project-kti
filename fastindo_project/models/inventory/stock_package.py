from odoo import models, fields, api

MIN_INNER_BOX = 7
MAX_INNER_BOX = 12

class StockPackage(models.Model):
    _inherit = 'stock.package'

    total_inner_qty = fields.Float(
        string="Total Inner",
        compute="_compute_package_metrics",
        store=False,
    )

    total_weight = fields.Float(
        string="Total Weight",
        compute="_compute_package_metrics",
        store=False,
    )

    fill_status = fields.Selection(
        [
            ('over', 'Over Occupied'),
            ('full', 'Full Box'),
            ('acceptable', 'Standard Fill'),
            ('under', 'Partial Fill'),
        ],
        string="Fill Status",
        compute="_compute_package_metrics",
        store=False,
    )

    @api.depends('move_line_ids.quantity')
    def _compute_package_metrics(self):
        for pkg in self:
            # mengganti move_line_ids karena standard odoo memfilter 'done' lines
            lines = self.env['stock.move.line'].search([
                ('result_package_id', '=', pkg.id),
                ('quantity', '>', 0)
            ])
            
            total = sum(lines.mapped('quantity'))
            pkg.total_inner_qty = total
            pkg.total_weight = sum(l.quantity * l.product_id.weight for l in lines)

            if total > MAX_INNER_BOX:
                pkg.fill_status = 'over'
            elif total >= MAX_INNER_BOX:
                pkg.fill_status = 'full'
            elif total >= MIN_INNER_BOX:
                pkg.fill_status = 'acceptable'
            else:
                pkg.fill_status = 'under'
