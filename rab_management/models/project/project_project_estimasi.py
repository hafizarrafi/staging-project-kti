from odoo import models, fields, api


class ProjectProject(models.Model):
    _inherit = 'project.project'

    total_additional_material = fields.Monetary(
        string='Material Tambahan',
        compute='_compute_total_additional',
        store=True,
        currency_field='currency_id'
    )

    total_additional_equipment = fields.Monetary(
        string='Peralatan Tambahan',
        compute='_compute_total_additional',
        store=True,
        currency_field='currency_id'
    )

    # Summary Cost Fields
    total_material = fields.Monetary(
        string='Material',
        compute='_compute_total_material',
        store=True,
        currency_field='currency_id'
    )

    total_equipment = fields.Monetary(
        string='Peralatan & Perkakas',
        compute='_compute_total_equipment',
        store=True,
        currency_field='currency_id'
    )

    total_manpower = fields.Monetary(
        string='Tenaga Kerja',
        currency_field='currency_id',
        default=0.0
    )

    total_operasional = fields.Monetary(
        string='Operasional',
        currency_field='currency_id',
        default=0.0
    )

    total_mobdemob = fields.Monetary(
        string='Mobilisasi Demobilisasi',
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

    total_kawat_las_dus = fields.Float(
        string='Total Dus Kawat Las',
        compute='_compute_total_kawat_las',
        store=True
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

    # Master totals (draft additional)
    material_total_rab = fields.Monetary(
        string='Total RAB (Material)',
        compute='_compute_master_totals',
        store=True,
        currency_field='currency_id'
    )
    material_total_estimasi = fields.Monetary(
        string='Total Estimasi (Material)',
        compute='_compute_master_totals',
        store=True,
        currency_field='currency_id'
    )
    equipment_total_rab = fields.Monetary(
        string='Total RAB (Equipment)',
        compute='_compute_master_totals',
        store=True,
        currency_field='currency_id'
    )
    equipment_total_estimasi = fields.Monetary(
        string='Total Estimasi (Equipment)',
        compute='_compute_master_totals',
        store=True,
        currency_field='currency_id'
    )

    add_material_total_rab = fields.Monetary(
        string='Total RAB (Add. Material)',
        compute='_compute_master_totals',
        store=True,
        currency_field='currency_id'
    )
    add_material_total_estimasi = fields.Monetary(
        string='Total Estimasi (Add. Material)',
        compute='_compute_master_totals',
        store=True,
        currency_field='currency_id'
    )
    add_equipment_total_rab = fields.Monetary(
        string='Total RAB (Add. Equipment)',
        compute='_compute_master_totals',
        store=True,
        currency_field='currency_id'
    )
    add_equipment_total_estimasi = fields.Monetary(
        string='Total Estimasi (Add. Equipment)',
        compute='_compute_master_totals',
        store=True,
        currency_field='currency_id'
    )

    # History totals (converted additional)
    material_add_total_rab = fields.Monetary(
        string='Total RAB (Add. Material)',
        compute='_compute_history_totals',
        store=True,
        currency_field='currency_id'
    )
    material_add_total_estimasi = fields.Monetary(
        string='Total Estimasi (Add. Material)',
        compute='_compute_history_totals',
        store=True,
        currency_field='currency_id'
    )
    equipment_add_total_rab = fields.Monetary(
        string='Total RAB (Add. Equipment)',
        compute='_compute_history_totals',
        store=True,
        currency_field='currency_id'
    )
    equipment_add_total_estimasi = fields.Monetary(
        string='Total Estimasi (Add. Equipment)',
        compute='_compute_history_totals',
        store=True,
        currency_field='currency_id'
    )

    @api.depends('material_master_ids.rab_total_subtotal', 'material_master_ids.rab_subtotal',
                 'equipment_master_ids.rab_total_subtotal', 'equipment_master_ids.rab_subtotal',
                 'additional_material_ids.subtotal', 'additional_material_ids.subtotal_estimasi',
                 'additional_equipment_ids.subtotal', 'additional_equipment_ids.subtotal_estimasi')
    def _compute_master_totals(self):
        for rec in self:
            rec.material_total_rab = sum(rec.material_master_ids.mapped('rab_subtotal'))
            rec.material_total_estimasi = sum(rec.material_master_ids.mapped('subtotal_estimasi'))
            rec.equipment_total_rab = sum(rec.equipment_master_ids.mapped('rab_subtotal'))
            rec.equipment_total_estimasi = sum(rec.equipment_master_ids.mapped('subtotal_estimasi'))

            rec.add_material_total_rab = sum(rec.additional_material_ids.mapped('subtotal'))
            rec.add_material_total_estimasi = sum(rec.additional_material_ids.mapped('subtotal_estimasi'))
            rec.add_equipment_total_rab = sum(rec.additional_equipment_ids.mapped('subtotal'))
            rec.add_equipment_total_estimasi = sum(rec.additional_equipment_ids.mapped('subtotal_estimasi'))

    @api.depends('additional_material_history_ids.subtotal', 'additional_material_history_ids.subtotal_estimasi',
                 'additional_equipment_history_ids.subtotal', 'additional_equipment_history_ids.subtotal_estimasi')
    def _compute_history_totals(self):
        for rec in self:
            rec.material_add_total_rab = sum(rec.additional_material_history_ids.mapped('subtotal'))
            rec.material_add_total_estimasi = sum(rec.additional_material_history_ids.mapped('subtotal_estimasi'))
            rec.equipment_add_total_rab = sum(rec.additional_equipment_history_ids.mapped('subtotal'))
            rec.equipment_add_total_estimasi = sum(rec.additional_equipment_history_ids.mapped('subtotal_estimasi'))

    @api.depends('additional_material_ids.subtotal', 'additional_equipment_ids.subtotal',
                 'additional_material_history_ids.subtotal', 'additional_equipment_history_ids.subtotal')
    def _compute_total_additional(self):
        for rec in self:
            rec.total_additional_material = sum(rec.additional_material_ids.mapped('subtotal')) + \
                                            sum(rec.additional_material_history_ids.mapped('subtotal'))
            rec.total_additional_equipment = sum(rec.additional_equipment_ids.mapped('subtotal')) + \
                                             sum(rec.additional_equipment_history_ids.mapped('subtotal'))

    @api.depends('material_master_ids.rab_total_subtotal', 'total_additional_material')
    def _compute_total_material(self):
        for rec in self:
            primary = sum(rec.material_master_ids.mapped('rab_total_subtotal'))
            rec.total_material = primary + rec.total_additional_material

    @api.depends('equipment_master_ids.rab_total_subtotal', 'total_additional_equipment')
    def _compute_total_equipment(self):
        for rec in self:
            primary = sum(rec.equipment_master_ids.mapped('rab_total_subtotal'))
            rec.total_equipment = primary + rec.total_additional_equipment

    @api.depends('kawat_las_total_harga', 'rewelding_total_harga', 'kawat_las_kebutuhan_dus', 'rewelding_kebutuhan_dus')
    def _compute_total_kawat_las(self):
        for rec in self:
            rec.total_kawat_las = rec.kawat_las_total_harga + rec.rewelding_total_harga
            rec.total_kawat_las_dus = rec.kawat_las_kebutuhan_dus + rec.rewelding_kebutuhan_dus

    def _inverse_total_kawat_las(self):
        pass  # allow manual override

    @api.depends('total_material', 'total_equipment', 'total_manpower', 'total_operasional',
                 'total_mobdemob', 'total_kawat_las', 'total_oksigen', 'total_lpg')
    def _compute_sub_total_summary(self):
        for rec in self:
            rec.sub_total_summary = (
                rec.total_material + rec.total_equipment + rec.total_manpower +
                rec.total_operasional + rec.total_mobdemob + rec.total_kawat_las +
                rec.total_oksigen + rec.total_lpg
            )
