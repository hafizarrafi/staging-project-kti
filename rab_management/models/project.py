from odoo import models, fields, api
from odoo.exceptions import UserError
import math




class ProjectProject(models.Model):
    _inherit = 'project.project'

    rab_id = fields.Many2one(
        'rab.management',
        string='RAB',
        tracking=True
    )
    
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Sales Order',
        tracking=True,
        readonly=True
    )
    
    # field akses untuk view RAB dan SO di form project
    can_access_rab = fields.Boolean(compute='_compute_can_access_documents')
    can_access_so = fields.Boolean(compute='_compute_can_access_documents')

    def _compute_can_access_documents(self):
        user = self.env.user
        is_manager = (
            user.has_group('sales_team.group_sale_manager') and
            user.has_group('purchase.group_purchase_manager') and
            user.has_group('account.group_account_manager')
        )
        for rec in self:
            rec.can_access_rab = is_manager
            rec.can_access_so = is_manager
    
    total_estimasi_replating = fields.Float(
        string='Total Estimasi Replating',
        compute='_compute_total_estimasi_replating',
        store=True
    )
    
    total_panjang_las = fields.Float(
        string='Total Panjang Las',
        compute='_compute_total_panjang_las',
        store=True
    )
    
    total_weight = fields.Float(
        string='Total Weight (kg)',     
        compute='_compute_total_weight',
        store=True
    )

    material_master_ids = fields.One2many(
        'project.material.master',
        'project_id',
        string='Material Project'
    )

    equipment_master_ids = fields.One2many(
        'project.equipment.master',
        'project_id',
        string='Equipment & Tools'
    )
    
    # Kebutuhan Kawat Las Fields
    kawat_las_product_id = fields.Many2one(
        'product.product',
        string='Product Kawat Las',
        domain=[('categ_id.name','=','Material')]
    )

    kawat_las_tebal_material = fields.Float(
        string='Tebal Material (mm)',
        default=0.0
    )

    kawat_las_berat_massa_jenis = fields.Float(
        string='Berat Massa Jenis (gr/cm3)',
        default=7.80
    )

    kawat_las_luas_bevel = fields.Float(
        string='Luas Bevel (mm)',
        default=0.0
    )
    
    kawat_las_double_bevel = fields.Boolean(
        string='Double Bevel / x2 Volume',
        default=True,
        help="Check this to multiply the volume by 2 (e.g. for double bevel)."
    )

    kawat_las_eff_kawat = fields.Float(
        string='Eff Kawat (%)',
        default=60.0
    )

    kawat_las_volume = fields.Float(
        string='Volume (mm3)',
        compute='_compute_kawat_las_volume',
        store=True
    )
    
    kawat_las_volume_cm3 = fields.Float(
        string='Volume (cm3)',
        compute='_compute_kawat_las_volume',
        store=True
    )

    kawat_las_kebutuhan_kg = fields.Float(
        string='Kebutuhan (kg)',
        compute='_compute_kawat_las_kebutuhan',
        store=True
    )

    kawat_las_berat_per_dus = fields.Float(
        string='Berat / Dus (kg)',
        related='kawat_las_product_id.weight',
        readonly=True
    )

    kawat_las_stok_site = fields.Float(
        string='Stok On Site (Dus)',
        default=0.0
    )

    kawat_las_kebutuhan_dus = fields.Float(
        string='Kebutuhan Beli (Dus)',
        compute='_compute_kawat_las_kebutuhan',
        store=True
    )

    kawat_las_harga_satuan = fields.Float(
        string='Harga Satuan',
        related='kawat_las_product_id.list_price',
        readonly=True
    )

    kawat_las_total_harga = fields.Monetary(
        string='Total Harga Kawat Las',
        currency_field='currency_id',
        compute='_compute_kawat_las_total',
        store=True
    )

    # Summary Cost Fields
    total_material = fields.Monetary(
        string='Material',
        compute='_compute_total_material',
        store=True,
        currency_field='currency_id'
    )
    
    total_equipment = fields.Monetary(
        string='Equipment & Tools',
        compute='_compute_total_equipment',
        store=True,
        currency_field='currency_id'
    )
    
    total_manpower = fields.Monetary(
        string='Man Power',
        currency_field='currency_id',
        default=0.0
    )
    
    total_operasional = fields.Monetary(
        string='Operasional',
        currency_field='currency_id',
        default=0.0
    )
    
    total_mobdemob = fields.Monetary(
        string='Mob Demob',
        currency_field='currency_id',
        default=0.0
    )
    
    total_kawat_las = fields.Monetary(
        string='Kawat las',
        currency_field='currency_id',
        compute='_compute_total_kawat_las',
        inverse='_inverse_total_kawat_las',
        store=True,
        default=0.0
    )
    
    total_oksigen = fields.Monetary(
        string='Oksigen',
        currency_field='currency_id',
        default=0.0
    )
    
    total_lpg = fields.Monetary(
        string='LPG',
        currency_field='currency_id',
        default=0.0
    )
    
    sub_total_summary = fields.Monetary(
        string='SUB TOTAL',
        compute='_compute_sub_total_summary',
        store=True,
        currency_field='currency_id'
    )

    project_sale_order_ids = fields.One2many(
        'sale.order',
        'project_id',
        string='All Project Sales Orders',
    )

    so_ditagihkan = fields.Monetary(
        string='SO Ditagihkan',
        compute='_compute_so_ditagihkan',
        store=True,
        currency_field='currency_id'
    )

    total_margin = fields.Float(
        string='Total Margin (%)',
        compute='_compute_total_margin',
        store=True
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )

    
    @api.depends('material_master_ids.rab_subtotal')
    def _compute_total_material(self):
        for rec in self:
            rec.total_material = sum(rec.material_master_ids.mapped('rab_subtotal'))
    
    @api.depends('equipment_master_ids.rab_subtotal')
    def _compute_total_equipment(self):
        for rec in self:
            rec.total_equipment = sum(rec.equipment_master_ids.mapped('rab_subtotal'))
    
    @api.depends('project_sale_order_ids.amount_total', 'project_sale_order_ids.state')
    def _compute_so_ditagihkan(self):
        for rec in self:
            confirmed = rec.project_sale_order_ids.filtered(
                lambda so: so.state in ('sale', 'done')
            )
            rec.so_ditagihkan = sum(confirmed.mapped('amount_total'))
    
    @api.depends('total_material', 'total_equipment', 'total_manpower', 'total_operasional',
                 'total_mobdemob', 'total_kawat_las', 'total_oksigen', 'total_lpg')
    def _compute_sub_total_summary(self):
        for rec in self:
            rec.sub_total_summary = (
                rec.total_material + rec.total_equipment + rec.total_manpower +
                rec.total_operasional + rec.total_mobdemob + rec.total_kawat_las +
                rec.total_oksigen + rec.total_lpg
            )

    @api.depends('so_ditagihkan', 'sub_total_summary')
    def _compute_total_margin(self):
        for rec in self:
            if rec.sub_total_summary > 0:
                rec.total_margin = ((rec.so_ditagihkan - rec.sub_total_summary) / rec.sub_total_summary) * 100
            else:
                rec.total_margin = 0.0

    @api.depends('task_ids.panjang_las')
    def _compute_total_panjang_las(self):
        for rec in self:
            rec.total_panjang_las = sum(rec.task_ids.mapped('panjang_las'))
    
    @api.depends('task_ids.weight')
    def _compute_total_weight(self):
        for rec in self:
            rec.total_weight = sum(rec.task_ids.mapped('weight'))
    
    @api.depends('total_weight')
    def _compute_total_estimasi_replating(self):
        for rec in self:
            rec.total_estimasi_replating = rec.total_weight * 27000

    @api.depends('kawat_las_total_harga')
    def _compute_total_kawat_las(self):
        for rec in self:
            rec.total_kawat_las = rec.kawat_las_total_harga

    def _inverse_total_kawat_las(self):
        pass  # allow manual override

    @api.depends('kawat_las_tebal_material', 'total_panjang_las', 'kawat_las_luas_bevel', 'kawat_las_double_bevel')
    def _compute_kawat_las_volume(self):
        for rec in self:
            factor = 2 if rec.kawat_las_double_bevel else 1
            rec.kawat_las_volume = rec.kawat_las_luas_bevel * rec.kawat_las_tebal_material * rec.total_panjang_las * factor
            rec.kawat_las_volume_cm3 = rec.kawat_las_volume / 1000.0

    @api.depends('kawat_las_volume_cm3', 'kawat_las_berat_massa_jenis', 'kawat_las_eff_kawat', 'kawat_las_berat_per_dus', 'kawat_las_stok_site')
    def _compute_kawat_las_kebutuhan(self):
        for rec in self:
            # Mass Pure (grams) = Volume (cm3) * Density (gr/cm3)
            mass_pure_grams = rec.kawat_las_volume_cm3 * rec.kawat_las_berat_massa_jenis
            # Mass Pure (kg)
            mass_pure_kg = mass_pure_grams / 1000.0
            
            efficiency_factor = rec.kawat_las_eff_kawat / 100.0 if rec.kawat_las_eff_kawat > 0 else 1.0
            
            if efficiency_factor > 0:
                rec.kawat_las_kebutuhan_kg = (mass_pure_kg / efficiency_factor) * 2
            else:
                rec.kawat_las_kebutuhan_kg = 0.0

            if rec.kawat_las_berat_per_dus > 0:
                total_dus = math.ceil(rec.kawat_las_kebutuhan_kg / rec.kawat_las_berat_per_dus)
                rec.kawat_las_kebutuhan_dus = max(total_dus - rec.kawat_las_stok_site, 0.0)
            else:
                rec.kawat_las_kebutuhan_dus = 0.0

    @api.depends('kawat_las_kebutuhan_dus', 'kawat_las_harga_satuan')
    def _compute_kawat_las_total(self):
        for rec in self:
            rec.kawat_las_total_harga = rec.kawat_las_kebutuhan_dus * rec.kawat_las_harga_satuan

    def action_sync_project_material(self):
        ProjectMaterial = self.env['project.material.master']

        for project in self:
            material_map = {}

            # 1. Aggregate dari task
            for task in project.task_ids:
                for mat in task.material_needed_ids:
                    product = mat.product_id
                    if not product:
                        continue

                    pid = product.id

                    material_map.setdefault(pid, {
                        'product_id': pid,
                        'total_weight': 0.0,
                    })

                    material_map[pid]['total_weight'] += mat.weight or 0.0

            # ambil existing records
            existing_materials = ProjectMaterial.search([
                ('project_id', '=', project.id)
            ])

            existing_map = {
                rec.product_id.id: rec
                for rec in existing_materials
            }

            processed_products = set()

            # 2. UPDATE atau CREATE
            for data in material_map.values():

                product = self.env['product.product'].browse(data['product_id'])

                unit_weight = product.weight or 0.0

                if unit_weight > 0:
                    qty_required = math.ceil(
                        data['total_weight'] / unit_weight
                    )
                else:
                    qty_required = 0

                if product.id in existing_map:

                    # UPDATE existing (preserve qty_on_site)
                    existing_map[product.id].with_context(from_sync=True).write({
                        'total_weight': data['total_weight'],
                        'total_qty': qty_required,
                        'is_manual': False,

                    })

                else:

                    # CREATE baru
                   ProjectMaterial.with_context(from_sync=True).create({
                        'project_id': project.id,
                        'product_id': product.id,
                        'total_weight': data['total_weight'],
                        'total_qty': qty_required,
                        'is_manual': False,
                    })

                processed_products.add(product.id)

            # 3. DELETE yang tidak ada lagi di task
            for product_id, rec in existing_map.items():
                # hanya hapus jika AUTO dan sudah tidak ada di task
                if product_id not in processed_products and not rec.is_manual:
                    rec.unlink()

            # 4. Recompute summary fields agar Summary tab langsung ter-update
            project._compute_total_material()
            project._compute_total_equipment()
            project._compute_sub_total_summary()


    def _is_rab_manager(self):
        user = self.env.user
        return (
            user.has_group('sales_team.group_sale_manager') and
            user.has_group('purchase.group_purchase_manager') and
            user.has_group('account.group_account_manager')
        )

    def action_create_rab_from_material(self):
        self.ensure_one()

        # RAB sudah ada
        if self.rab_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Info',
                    'message': 'Maaf RAB sudah dibuat sebelumnya.',
                    'type': 'warning',
                    'sticky': False,
                }
            }

        if not self.material_master_ids and not self.equipment_master_ids:
            raise UserError("Material Project dan Equipment masih kosong.")

        if not self.partner_id:
            raise UserError("Project harus memiliki Customer sebelum membuat RAB.")

        # Gunakan sudo() karena project user tidak punya create right pada rab.management
        RabSudo = self.env['rab.management'].sudo()
        RabLine = self.env['rab.management.line'].sudo()

        # Buat RAB HEADER
        rab = RabSudo.create({
            'customer_id': self.partner_id.id,
            'source_type': 'project',
            'project_id': self.id,
        })

        # Snapshot material → RAB line
        for mat in self.material_master_ids:
            if not mat.product_id or mat.qty_beli <= 0:
                continue
            RabLine.create({
                'rab_id': rab.id,
                'product_id': mat.product_id.id,
                'quantity': mat.qty_beli,
            })

        # Snapshot equipment → RAB line
        for equip in self.equipment_master_ids:
            if not equip.product_id or equip.qty_beli <= 0:
                continue
            RabLine.create({
                'rab_id': rab.id,
                'product_id': equip.product_id.id,
                'quantity': equip.qty_beli,
            })

        # Attach RAB ke project
        self.rab_id = rab.id

        # notification success
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': 'RAB berhasil dibuat.',
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }

    def action_create_sale_order(self):
        self.ensure_one()

        # SO sudah ada — buka form SO agar user bisa lihat/edit harga
        if self.sale_order_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'sale.order',
                'res_id': self.sale_order_id.id,
                'view_mode': 'form',
                'target': 'current',
            }

        if not self.partner_id:
            raise UserError("Project harus memiliki Customer sebelum membuat Sales Order.")

        # Gunakan sudo() karena project user mungkin tidak punya hak create pada sale.order
        SoSudo = self.env['sale.order'].sudo()
        SolSudo = self.env['sale.order.line'].sudo()

        # Hitung termin
        so_count = SoSudo.search_count([('project_id', '=', self.id)])
        termin_number = so_count + 1

        # Gunakan produk Project Service yang sudah didefinisikan sebagai data
        product_service = self.env.ref('rab_management.product_project_service')

        # Buat Sales Order
        sale_order = SoSudo.create({
            'partner_id': self.partner_id.id,
            'origin': self.name,
            'project_id': self.id,
        })

        # Buat SO Line dengan termin; price_unit=0 agar user bisa isi sendiri di form SO
        SolSudo.create({
            'order_id': sale_order.id,
            'product_id': product_service.id,
            'name': f"{self.name} - service termin {termin_number}",
            'product_uom_qty': 1,
            'price_unit': 0.0,
        })

        # Attach SO ke project
        self.sale_order_id = sale_order.id

        # Buka form SO agar semua role (termasuk project admin) bisa input harga
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': sale_order.id,
            'view_mode': 'form',
            'target': 'current',
        }
