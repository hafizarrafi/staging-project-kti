from odoo import models, fields, api, _
from odoo.exceptions import UserError

class ProjectProject(models.Model):
    _inherit = 'project.project'

    stock_location_id = fields.Many2one(
        'stock.location',
        string='Project Stock Location',
        readonly=True,
        tracking=True,
        help="Location used for inventory related to this project."
    )

    @api.model_create_multi
    def create(self, vals_list):
        projects = super().create(vals_list)
        for project in projects:
            project._create_stock_location()
        return projects

    def _create_stock_location(self):
        self.ensure_one()
        if self.stock_location_id:
            return

        # Cari warehouse utama perusahaan project ini
        warehouse = self.env['stock.warehouse'].search([
            ('company_id', '=', self.company_id.id or self.env.company.id)
        ], limit=1)

        # Gunakan lot_stock_id (misal: WH/Stock) sebagai parent
        parent_location = warehouse.lot_stock_id if warehouse else self.env.ref('stock.stock_location_stock', raise_if_not_found=False)

        if not parent_location:
             parent_location = self.env['stock.location'].search([
                 ('usage', '=', 'internal'), 
                 ('company_id', '=', self.company_id.id or self.env.company.id)
             ], limit=1)

        if not parent_location:
            raise UserError(_("Cannot find a parent internal location for the project stock. Please ensure a Warehouse is configured."))

        location = self.env['stock.location'].create({
            'name': f"Project: {self.name}",
            'usage': 'internal',
            'location_id': parent_location.id,
            'company_id': self.company_id.id or self.env.company.id,
            'active': True,
        })
        self.sudo().write({'stock_location_id': location.id})

    def action_create_stock_location(self):
        """Manual action to create location for existing projects."""
        for rec in self:
            rec._create_stock_location()

    def action_open_project_inventory(self):
        self.ensure_one()
        if not self.stock_location_id:
            raise UserError(_("This project does not have an inventory location setup."))

        # Buka tampilan stock quant
        return {
            'name': _('Project Inventory'),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.quant',
            'view_mode': 'list,form',
            'domain': [('location_id', '=', self.stock_location_id.id)],
            'context': {
                'search_default_locationgroup': 1,
                'default_location_id': self.stock_location_id.id,
                'create': False, # User shouldn't create quants manually outside of wizard
            }
        }

    def action_init_stock_onsite(self):
        self.ensure_one()
        is_new_location = False
        if not self.stock_location_id:
            self._create_stock_location()
            is_new_location = True

        ctx = {
            'default_project_id': self.id,
        }

        # Jika ini adalah inisialisasi pertama (baru buat lokasi), 
        # coba tarik data qty_on_site dari master material/equipment sebagai saran awal.
        if is_new_location:
            lines_data = []
            for mat in self.material_master_ids.filtered(lambda m: m.qty_on_site > 0):
                lines_data.append((0, 0, {
                    'product_id': mat.product_id.id,
                    'quantity': mat.qty_on_site,
                }))
            
            for equip in self.equipment_master_ids.filtered(lambda e: e.qty_on_site > 0):
                lines_data.append((0, 0, {
                    'product_id': equip.product_id.id,
                    'quantity': equip.qty_on_site,
                }))
            
            if lines_data:
                ctx['default_line_ids'] = lines_data

        return {
            'name': _('Initialize Stock On Site'),
            'type': 'ir.actions.act_window',
            'res_model': 'project.stock.onsite.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': ctx,
        }
