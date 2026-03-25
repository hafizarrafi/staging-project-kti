from odoo import models, fields, api


class PartnerRiskCategory(models.Model):
    _name = 'partner.risk.category'
    _description = 'Partner Risk Category'
    _order = 'sequence, id'

    name = fields.Char(string='Category Name', required=True)
    sequence = fields.Integer(default=10)
    color = fields.Integer(string='Color Index')


#dipending dulu yang ini
# class PartnerReceivableCategory(models.Model):
#     _name = 'partner.receivable.category'
#     _description = 'Partner Receivable Category'
#     _order = 'name'
# 
#     name = fields.Char(string='Category Name', required=True)


class PartnerSegment(models.Model):
    _name = 'partner.segment'
    _description = 'Partner Market Segment'
    _order = 'name'

    name = fields.Char(string='Segment Name', required=True)
    product_ids = fields.Many2many(
        'product.template',
        string='Suggested Products',
        help='Products commonly requested by customers in this segment.'
    )


class PartnerSuspensionLog(models.Model):
    _name = 'partner.suspension.log'
    _description = 'Partner Suspension Log'
    _order = 'create_date desc'

    partner_id = fields.Many2one('res.partner', string='Partner', required=True, ondelete='cascade')
    state = fields.Selection([
        ('suspended', 'Suspended'),
        ('active', 'Active')
    ], string='Action', required=True)
    reason = fields.Text(string='Reason')
    user_id = fields.Many2one('res.users', string='Done By', default=lambda self: self.env.user)

    def action_confirm_suspension(self):
        self.ensure_one()
        if self.state == 'suspended':
            self.partner_id.is_suspended = True
        return {'type': 'ir.actions.act_window_close'}
