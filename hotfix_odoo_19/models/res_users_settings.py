from odoo import api, fields, models


class ResUsersSettings(models.Model):
    _inherit = 'res.users.settings'

    color_scheme = fields.Selection(default='dark')

    @api.model_create_multi
    def create(self, vals_list):
        """Ensure color_scheme has default value on create."""
        for vals in vals_list:
            if 'color_scheme' not in vals or not vals.get('color_scheme'):
                vals['color_scheme'] = 'dark'
        return super().create(vals_list)

    def write(self, vals):
        """Ensure color_scheme is not set to NULL/False on write."""
        if 'color_scheme' in vals and not vals.get('color_scheme'):
            vals['color_scheme'] = 'dark'
        return super().write(vals)
