from odoo import models, fields, api


class ProjectAdditionalPurchase(models.Model):
    _name = 'project.additional.purchase'
    _description = 'Project Additional Purchase'
    _order = 'item_type, product_id'

    project_id = fields.Many2one(
        'project.project',
        required=True,
        ondelete='cascade'
    )

    task_id = fields.Many2one(
        'project.task',
        string='Task Asal',
        ondelete='set null'
    )

    item_type = fields.Selection(
        [
            ('material', 'Material'),
            ('equipment', 'Peralatan'),
        ],
        string='Tipe',
        required=True,
        default='material'
    )

    source = fields.Selection(
        [
            ('manual', 'Manual'),
            ('task', 'Dari Task'),
        ],
        string='Sumber',
        default='manual',
        required=True
    )

    product_id = fields.Many2one(
        'product.product',
        string='Produk',
        required=True
    )

    total_weight = fields.Float(
        string='Volume Estimasi (kg)',
        digits=(16, 2)
    )

    product_weight = fields.Float(
        string='Berat / Satuan (kg)',
        related='product_id.weight',
        readonly=True
    )

    total_qty = fields.Float(
        string='Total Qty Dibutuhkan',
        compute='_compute_total_qty',
        store=True,
        digits=(16, 2)
    )

    @api.depends('total_weight', 'product_weight')
    def _compute_total_qty(self):
        import math
        for rec in self:
            if rec.total_weight and rec.product_weight:
                rec.total_qty = math.ceil(rec.total_weight / rec.product_weight)
            else:
                rec.total_qty = 0.0

    qty_on_site = fields.Float(
        string='Qty On Site',
        default=0.0
    )

    qty_beli = fields.Float(
        string='Qty Beli',
        compute='_compute_qty_beli',
        store=True
    )

    uom_id = fields.Many2one(
        related='product_id.uom_id',
        readonly=True,
        string='UOM'
    )

    unit_price = fields.Float(
        string='Harga Satuan',
        compute='_compute_unit_price',
        store=True,
        readonly=False,
    )

    create_date = fields.Datetime(string='Dibuat Pada', readonly=True)

    source_details = fields.Char(
        string='Detail Sumber',
        compute='_compute_source_details'
    )

    @api.depends('source', 'task_id', 'create_date')
    def _compute_source_details(self):
        from odoo.fields import Datetime
        for rec in self:
            if rec.source == 'task' and rec.task_id:
                rec.source_details = rec.task_id.name
            else:
                dt_str = ""
                if rec.create_date:
                    # Ambil timezone dari context user
                    user_tz = self.env.user.tz or 'UTC'
                    localized_dt = Datetime.context_timestamp(self.with_context(tz=user_tz), rec.create_date)
                    dt_str = f" [{localized_dt.strftime('%Y-%m-%d %H:%M')}]"
                rec.source_details = f"{dt_str}"

    subtotal = fields.Float(
        string='Subtotal RAB',
        compute='_compute_subtotal',
        store=True
    )

    subtotal_estimasi = fields.Float(
        string='Subtotal Estimasi',
        compute='_compute_subtotal',
        store=True
    )

    is_converted = fields.Boolean(
        string='RAB Terbuat',
        default=False,
        help="Jika dicentang, item ini telah dikonversi ke RAB."
    )

    rab_id = fields.Many2one(
        'rab.management',
        string='RAB Asal',
        readonly=True
    )

    @api.depends('product_id', 'project_id.rab_id', 'rab_id', 'is_converted',
                 'project_id.rab_id.line_ids.sale_price', 'rab_id.line_ids.sale_price')
    def _compute_unit_price(self):
        for rec in self:
            # 1. pengecekan pada rab yang ada pada project
            rab = rec.rab_id
            rab_line = False
            
            if rab and rec.product_id:
                rab_line = rab.line_ids.filtered(lambda l: l.product_id.id == rec.product_id.id)[:1]
            
            # 2. jika tidak ada, maka bisa membuat rab dengan item tersebut ( agar tidak double)
            if not rab_line and rec.project_id.rab_id and rec.product_id:
                rab_line = rec.project_id.rab_id.line_ids.filtered(
                    lambda l: l.product_id.id == rec.product_id.id
                )[:1]
            
            if rab_line:
                rec.unit_price = rab_line.sale_price
            elif rec.product_id:
                # Fallback ke harga pricelist
                rec.unit_price = rec.product_id.standard_price
            else:
                rec.unit_price = 0.0

    @api.onchange('product_id')
    def _onchange_product_id_price(self):
        # Trigger
        self._compute_unit_price()

    @api.depends('total_qty', 'qty_on_site')
    def _compute_qty_beli(self):
        for rec in self:
            rec.qty_beli = max(
                (rec.total_qty or 0.0) - (rec.qty_on_site or 0.0),
                0.0
            )

    @api.depends('qty_beli', 'total_qty', 'unit_price')
    def _compute_subtotal(self):
        for rec in self:
            rec.subtotal = (rec.qty_beli or 0.0) * (rec.unit_price or 0.0)
            rec.subtotal_estimasi = (rec.total_qty or 0.0) * (rec.unit_price or 0.0)
