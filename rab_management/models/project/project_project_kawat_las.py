from odoo import models, fields, api
import math


class ProjectProject(models.Model):
    _inherit = 'project.project'

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

    # Kebutuhan Kawat Las Fields
    kawat_las_product_id = fields.Many2one(
        'product.product',
        string='Product Kawat Las',
        domain=[('categ_id.name', '=', 'Material')]
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
        compute='_compute_kawat_las_values',
        store=True,
    )

    kawat_las_total_harga = fields.Monetary(
        string='Total Harga Kawat Las',
        currency_field='currency_id',
        compute='_compute_kawat_las_values',
        store=True
    )

    subtotal_estimasi_steelwork = fields.Monetary(
        string='Subtotal Estimasi',
        currency_field='currency_id',
        compute='_compute_kawat_las_values',
        store=True
    )

    rab_subtotal_steelwork = fields.Monetary(
        string='Subtotal RAB',
        currency_field='currency_id',
        compute='_compute_kawat_las_values',
        store=True
    )

    kawat_las_x2_length = fields.Boolean(
        string='Total panjang las x 2',
        default=True
    )

    # Rewelding Fields
    rewelding_product_id = fields.Many2one(
        'product.product',
        string='Product Kawat Las (Rewelding)',
        domain=[('categ_id.name', '=', 'Material')]
    )

    rewelding_tebal_material = fields.Float(
        string='Tebal Material (mm) (Rewelding)',
        default=0.0
    )

    rewelding_panjang_las = fields.Float(
        string='Panjang Las (Rewelding)',
        default=0.0
    )

    rewelding_luas_bevel = fields.Float(
        string='Luas Bevel (mm) (Rewelding)',
        default=0.0
    )

    rewelding_double_bevel = fields.Boolean(
        string='Double Bevel / x2 Volume (Rewelding)',
        default=True
    )

    rewelding_eff_kawat = fields.Float(
        string='Eff Kawat (%) (Rewelding)',
        default=60.0
    )

    rewelding_berat_massa_jenis = fields.Float(
        string='Berat Massa Jenis (gr/cm3) (Rewelding)',
        default=7.80
    )

    rewelding_volume = fields.Float(
        string='Volume (mm3) (Rewelding)',
        compute='_compute_rewelding_volume',
        store=True
    )

    rewelding_volume_cm3 = fields.Float(
        string='Volume (cm3) (Rewelding)',
        compute='_compute_rewelding_volume',
        store=True
    )

    rewelding_kebutuhan_kg = fields.Float(
        string='Kebutuhan (kg) (Rewelding)',
        compute='_compute_rewelding_kebutuhan',
        store=True
    )

    rewelding_berat_per_dus = fields.Float(
        string='Berat / Dus (kg) (Rewelding)',
        related='rewelding_product_id.weight',
        readonly=True
    )

    rewelding_stok_site = fields.Float(
        string='Stok On Site (Dus) (Rewelding)',
        default=0.0
    )

    rewelding_kebutuhan_dus = fields.Float(
        string='Kebutuhan Beli (Dus) (Rewelding)',
        compute='_compute_rewelding_kebutuhan',
        store=True
    )

    rewelding_harga_satuan = fields.Float(
        string='Harga Satuan (Rewelding)',
        compute='_compute_kawat_las_values',
        store=True,
    )

    rewelding_total_harga = fields.Monetary(
        string='Total Harga Rewelding',
        currency_field='currency_id',
        compute='_compute_kawat_las_values',
        store=True
    )

    subtotal_estimasi_rewelding = fields.Monetary(
        string='Subtotal Estimasi',
        currency_field='currency_id',
        compute='_compute_kawat_las_values',
        store=True
    )

    rab_subtotal_rewelding = fields.Monetary(
        string='Subtotal RAB',
        currency_field='currency_id',
        compute='_compute_kawat_las_values',
        store=True
    )

    @api.depends('task_ids.panjang_las', 'kawat_las_x2_length')
    def _compute_total_panjang_las(self):
        for rec in self:
            base = sum(rec.task_ids.mapped('panjang_las'))
            factor = 2 if rec.kawat_las_x2_length else 1
            rec.total_panjang_las = base * factor

    @api.depends('material_master_ids.total_weight',
                 'additional_material_ids.total_weight',
                 'additional_material_history_ids.total_weight')
    def _compute_total_weight(self):
        for rec in self:
            primary_weight = sum(rec.material_master_ids.mapped('total_weight'))
            additional_weight = sum(rec.additional_material_ids.mapped('total_weight'))
            history_weight = sum(rec.additional_material_history_ids.mapped('total_weight'))
            rec.total_weight = primary_weight + additional_weight + history_weight

    @api.depends('total_weight')
    def _compute_total_estimasi_replating(self):
        for rec in self:
            rec.total_estimasi_replating = rec.total_weight * 27000

    @api.depends('rewelding_tebal_material', 'rewelding_panjang_las', 'rewelding_luas_bevel', 'rewelding_double_bevel')
    def _compute_rewelding_volume(self):
        for rec in self:
            v_factor = 2 if rec.rewelding_double_bevel else 1
            rec.rewelding_volume = rec.rewelding_luas_bevel * rec.rewelding_tebal_material * rec.rewelding_panjang_las * v_factor
            rec.rewelding_volume_cm3 = rec.rewelding_volume / 1000.0

    @api.depends('rewelding_volume_cm3', 'rewelding_berat_massa_jenis', 'rewelding_eff_kawat', 'rewelding_berat_per_dus', 'rewelding_stok_site')
    def _compute_rewelding_kebutuhan(self):
        for rec in self:
            mass_pure_grams = rec.rewelding_volume_cm3 * rec.rewelding_berat_massa_jenis
            mass_pure_kg = mass_pure_grams / 1000.0
            efficiency_factor = rec.rewelding_eff_kawat / 100.0 if rec.rewelding_eff_kawat > 0 else 1.0

            if efficiency_factor > 0:
                rec.rewelding_kebutuhan_kg = mass_pure_kg / efficiency_factor
            else:
                rec.rewelding_kebutuhan_kg = 0.0

            if rec.rewelding_berat_per_dus > 0:
                total_dus = math.ceil(rec.rewelding_kebutuhan_kg / rec.rewelding_berat_per_dus)
                rec.rewelding_kebutuhan_dus = max(total_dus - rec.rewelding_stok_site, 0.0)
            else:
                rec.rewelding_kebutuhan_dus = 0.0

    @api.depends('kawat_las_tebal_material', 'total_panjang_las', 'kawat_las_luas_bevel', 'kawat_las_double_bevel')
    def _compute_kawat_las_volume(self):
        for rec in self:
            v_factor = 2 if rec.kawat_las_double_bevel else 1
            rec.kawat_las_volume = rec.kawat_las_luas_bevel * rec.kawat_las_tebal_material * rec.total_panjang_las * v_factor
            rec.kawat_las_volume_cm3 = rec.kawat_las_volume / 1000.0

    @api.depends('kawat_las_volume_cm3', 'kawat_las_berat_massa_jenis', 'kawat_las_eff_kawat', 'kawat_las_berat_per_dus', 'kawat_las_stok_site', 'kawat_las_x2_length')
    def _compute_kawat_las_kebutuhan(self):
        for rec in self:
            mass_pure_grams = rec.kawat_las_volume_cm3 * rec.kawat_las_berat_massa_jenis
            mass_pure_kg = mass_pure_grams / 1000.0
            efficiency_factor = rec.kawat_las_eff_kawat / 100.0 if rec.kawat_las_eff_kawat > 0 else 1.0

            if efficiency_factor > 0:
                rec.kawat_las_kebutuhan_kg = mass_pure_kg / efficiency_factor
            else:
                rec.kawat_las_kebutuhan_kg = 0.0

            if rec.kawat_las_berat_per_dus > 0:
                total_dus = math.ceil(rec.kawat_las_kebutuhan_kg / rec.kawat_las_berat_per_dus)
                rec.kawat_las_kebutuhan_dus = max(total_dus - rec.kawat_las_stok_site, 0.0)
            else:
                rec.kawat_las_kebutuhan_dus = 0.0

    @api.depends('rab_id', 'rab_id.line_ids.sale_price',
                 'kawat_las_product_id', 'rewelding_product_id',
                 'kawat_las_kebutuhan_kg', 'kawat_las_berat_per_dus',
                 'rewelding_kebutuhan_kg', 'rewelding_berat_per_dus')
    def _compute_kawat_las_values(self):
        for rec in self:
            rab = rec.rab_id

            # 1. Price and Total for Steelwork
            kawat_price = 0.0
            if rab and rec.kawat_las_product_id:
                line = rab.line_ids.filtered(lambda l: l.product_id.id == rec.kawat_las_product_id.id)[:1]
                kawat_price = line.sale_price if line else 0.0
            rec.kawat_las_harga_satuan = kawat_price

            # Use total required dus (ignoring stock) for summary price
            total_req_dus = math.ceil(rec.kawat_las_kebutuhan_kg / rec.kawat_las_berat_per_dus) if rec.kawat_las_berat_per_dus > 0 else 0.0
            rec.kawat_las_total_harga = total_req_dus * kawat_price
            rec.subtotal_estimasi_steelwork = rec.kawat_las_total_harga
            rec.rab_subtotal_steelwork = rec.kawat_las_kebutuhan_dus * kawat_price

            # 2. Price and Total for Rewelding
            rewelding_price = 0.0
            if rab and rec.rewelding_product_id:
                line = rab.line_ids.filtered(lambda l: l.product_id.id == rec.rewelding_product_id.id)[:1]
                rewelding_price = line.sale_price if line else 0.0
            rec.rewelding_harga_satuan = rewelding_price

            # Use total required dus (ignoring stock) for summary price
            total_req_rew_dus = math.ceil(rec.rewelding_kebutuhan_kg / rec.rewelding_berat_per_dus) if rec.rewelding_berat_per_dus > 0 else 0.0
            rec.rewelding_total_harga = total_req_rew_dus * rewelding_price
            rec.subtotal_estimasi_rewelding = rec.rewelding_total_harga
            rec.rab_subtotal_rewelding = rec.rewelding_kebutuhan_dus * rewelding_price
