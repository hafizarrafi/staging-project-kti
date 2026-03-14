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
    is_stock_initialized = fields.Boolean(
        string='Stock Initialized',
        default=False,
        copy=False,
        help="Flag to prevent duplicate initial stock recognition."
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

        if not warehouse:
             # Jika tidak ada warehouse, jangan crash, cukup log atau biarkan project tercipta tanpa lokasi
             return

        # Gunakan lot_stock_id (misal: WH/Stock) sebagai parent
        parent_location = warehouse.lot_stock_id

        if not parent_location:
             parent_location = self.env['stock.location'].search([
                 ('usage', '=', 'internal'), 
                 ('company_id', '=', self.company_id.id or self.env.company.id)
             ], limit=1)

        if not parent_location:
            return # Safety guard

        try:
            location = self.env['stock.location'].create({
                'name': f"Project: {self.name}",
                'usage': 'internal',
                'location_id': parent_location.id,
                'company_id': self.company_id.id or self.env.company.id,
                'active': True,
            })
            self.sudo().write({'stock_location_id': location.id})
        except Exception:
            # Jika gagal (misal data integrity), jangan hentikan pembuatan project
            pass

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
            'domain': [('location_id', 'child_of', self.stock_location_id.id)],
            'context': {
                'search_default_locationgroup': 1,
                'default_location_id': self.stock_location_id.id,
                'create': False, # User shouldn't create quants manually outside of wizard
            }
        }

    def action_init_stock_onsite(self):
        self.ensure_one()
        if self.is_stock_initialized:
            raise UserError(_("Stock for this project has already been initialized. Use the regular inventory adjustment or transfer for further changes."))
        
        is_new_location = False
        if not self.stock_location_id:
            self._create_stock_location()
            is_new_location = True

        # 1. Buat record Wizard terlebih dahulu di DB (Transient).
        # Ini lebih aman daripada lewat context jika datanya ratusan baris.
        wizard = self.env['project.stock.onsite.wizard'].create({
            'project_id': self.id,
        })

        # 2. Tarik data dari master material/equipment.
        product_qtys = {}
        for mat in self.material_master_ids:
            if not mat.product_id:
                continue
            pid = mat.product_id.id
            product_qtys[pid] = product_qtys.get(pid, 0.0) + mat.qty_on_site
        
        for equip in self.equipment_master_ids:
            if not equip.product_id:
                continue
            pid = equip.product_id.id
            product_qtys[pid] = product_qtys.get(pid, 0.0) + equip.qty_on_site
        
        # 3. Create lines secara batch langsung di database
        if product_qtys:
            lines_vals = []
            for pid, qty in product_qtys.items():
                lines_vals.append({
                    'wizard_id': wizard.id,
                    'product_id': pid,
                    'quantity': qty,
                })
            self.env['project.stock.onsite.line'].create(lines_vals)

        return {
            'name': _('Initialize Stock On Site'),
            'type': 'ir.actions.act_window',
            'res_model': 'project.stock.onsite.wizard',
            'view_mode': 'form',
            'res_id': wizard.id,
            'target': 'new',
            'context': {'default_project_id': self.id},
        }
