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

    rab_state = fields.Selection(
        related='rab_id.state',
        string='Status RAB',
        store=False
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

    material_master_ids = fields.One2many(
        'project.material.master',
        'project_id',
        string='Material Proyek'
    )

    equipment_master_ids = fields.One2many(
        'project.equipment.master',
        'project_id',
        string='Peralatan & Perkakas'
    )

    # Draft Additional
    additional_material_ids = fields.One2many(
        'project.additional.purchase',
        'project_id',
        string='Material Tambahan',
        domain=[('item_type', '=', 'material'), ('is_converted', '=', False)]
    )

    additional_equipment_ids = fields.One2many(
        'project.additional.purchase',
        'project_id',
        string='Peralatan Tambahan',
        domain=[('item_type', '=', 'equipment'), ('is_converted', '=', False)]
    )

    # History Additional
    additional_material_history_ids = fields.One2many(
        'project.additional.purchase',
        'project_id',
        string='Riwayat Material Tambahan',
        domain=[('item_type', '=', 'material'), ('is_converted', '=', True)]
    )

    additional_equipment_history_ids = fields.One2many(
        'project.additional.purchase',
        'project_id',
        string='Riwayat Peralatan Tambahan',
        domain=[('item_type', '=', 'equipment'), ('is_converted', '=', True)]
    )

    additional_rab_ids = fields.One2many(
        'rab.management',
        'project_id',
        string='Dokumen RAB Tambahan',
        domain=[('source_type', '=', 'additional')],
        context={'default_source_type': 'additional'}
    )

    all_rab_count = fields.Integer(
        string='Jumlah RAB',
        compute='_compute_all_rab_count'
    )

    project_sale_order_ids = fields.One2many(
        'sale.order',
        'project_id',
        string='Semua Sales Order Proyek',
    )

    purchase_order_ids = fields.One2many(
        'purchase.order',
        'project_id',
        string='Purchase Orders',
    )

    issue_ids = fields.One2many(
        'project.material.issue',
        'project_id',
        string='Material Issues'
    )

    consumption_ids = fields.One2many(
        'project.material.consumption',
        'project_id',
        string='Material Consumptions'
    )

    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )

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

    def _compute_all_rab_count(self):
        for rec in self:
            count = 0
            if rec.rab_id:
                count += 1
            count += self.env['rab.management'].search_count([
                ('project_id', '=', rec.id),
                ('source_type', '=', 'additional'),
            ])
            rec.all_rab_count = count

    def _is_rab_manager(self):
        user = self.env.user
        return (
            user.has_group('sales_team.group_sale_manager') and
            user.has_group('purchase.group_purchase_manager') and
            user.has_group('account.group_account_manager')
        )

    def action_view_all_rabs(self):
        self.ensure_one()
        rab_ids = []
        if self.rab_id:
            rab_ids.append(self.rab_id.id)
        additional = self.env['rab.management'].search([
            ('project_id', '=', self.id),
            ('source_type', '=', 'additional'),
        ])
        rab_ids += additional.ids

        if len(rab_ids) == 1:
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'rab.management',
                'res_id': rab_ids[0],
                'view_mode': 'form',
                'target': 'current',
            }
        return {
            'type': 'ir.actions.act_window',
            'name': 'RAB Project',
            'res_model': 'rab.management',
            'view_mode': 'list,form',
            'domain': [('id', 'in', rab_ids)],
            'target': 'current',
        }

    def action_view_material_issues(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Material Issues',
            'res_model': 'project.material.issue',
            'view_mode': 'list,form',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
            'target': 'current',
        }

    def action_open_issue_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Generate Material Issue',
            'res_model': 'project.material.issue.wizard',
            'view_mode': 'form',
            'context': {'default_project_id': self.id},
            'target': 'new',
        }

    def action_view_stock_management(self):
        self.ensure_one()
        # Find or create singleton dashboard for this project
        dashboard = self.env['project.material.consumption'].search([('project_id', '=', self.id)], limit=1)
        if not dashboard:
            dashboard = self.env['project.material.consumption'].create({'project_id': self.id})
        
        # Refresh lines to ensure they match task requirements
        dashboard.action_refresh_requirements()
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Stock Management',
            'res_model': 'project.material.consumption',
            'res_id': dashboard.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_sync_project_material(self):
        ProjectMaterial = self.env['project.material.master']
        AdditionalPurchase = self.env['project.additional.purchase']

        for project in self:
            primary_map = {}
            additional_map = {}

            # 1. Aggregate dari task
            for task in project.task_ids:
                job_type = task.job_type or 'primary'

                # 1a. Own task's product/weight
                if task.product_id:
                    pid = task.product_id.id
                    if job_type == 'primary':
                        primary_map.setdefault(pid, {'product_id': pid, 'total_weight': 0.0})
                        primary_map[pid]['total_weight'] += task.weight or 0.0
                    else:
                        key = (pid, task.id)
                        additional_map.setdefault(key, {
                            'product_id': pid,
                            'task_id': task.id,
                            'total_weight': 0.0
                        })
                        additional_map[key]['total_weight'] += task.weight or 0.0

                # 1b. Manual materials in this task
                for mat in task.material_needed_ids.filtered(lambda m: m.source == 'manual'):
                    product = mat.product_id
                    if not product:
                        continue

                    pid = product.id
                    if job_type == 'primary':
                        primary_map.setdefault(pid, {'product_id': pid, 'total_weight': 0.0})
                        primary_map[pid]['total_weight'] += mat.weight or 0.0
                    else:
                        key = (pid, task.id)
                        additional_map.setdefault(key, {
                            'product_id': pid,
                            'task_id': task.id,
                            'total_weight': 0.0
                        })
                        additional_map[key]['total_weight'] += mat.weight or 0.0

            # 2. Sync Primary to Material Master
            existing_primary = ProjectMaterial.search([
                ('project_id', '=', project.id),
                ('job_type', '=', 'primary')
            ])
            existing_p_map = {rec.product_id.id: rec for rec in existing_primary}
            processed_p = set()

            for pid, data in primary_map.items():
                product = self.env['product.product'].browse(pid)
                unit_weight = product.weight or 0.0
                qty_required = math.ceil(data['total_weight'] / unit_weight) if unit_weight > 0 else 0

                if pid in existing_p_map:
                    existing_p_map[pid].with_context(from_sync=True).write({
                        'total_weight': data['total_weight'],
                        'total_qty': qty_required,
                        'is_manual': False,
                    })
                else:
                    ProjectMaterial.with_context(from_sync=True).create({
                        'project_id': project.id,
                        'product_id': pid,
                        'job_type': 'primary',
                        'total_weight': data['total_weight'],
                        'total_qty': qty_required,
                        'is_manual': False,
                    })
                processed_p.add(pid)

            for pid, rec in existing_p_map.items():
                if pid not in processed_p and not rec.is_manual:
                    rec.unlink()

            ProjectMaterial.search([
                ('project_id', '=', project.id),
                ('job_type', '=', 'additional')
            ]).unlink()

            existing_additional_task = AdditionalPurchase.search([
                ('project_id', '=', project.id),
                ('source', '=', 'task'),
                ('item_type', '=', 'material'),
            ])
            existing_a_map = {(rec.product_id.id, rec.task_id.id): rec for rec in existing_additional_task}
            processed_a = set()

            for key, data in additional_map.items():
                product = self.env['product.product'].browse(data['product_id'])
                unit_weight = product.weight or 0.0
                qty_required = math.ceil(data['total_weight'] / unit_weight) if unit_weight > 0 else 0

                if key in existing_a_map:
                    rec = existing_a_map[key]
                    if not rec.is_converted:
                        rec.write({
                            'total_weight': data['total_weight'],
                            'total_qty': qty_required,
                        })
                else:
                    AdditionalPurchase.create({
                        'project_id': project.id,
                        'product_id': data['product_id'],
                        'task_id': data['task_id'],
                        'item_type': 'material',
                        'source': 'task',
                        'total_weight': data['total_weight'],
                        'total_qty': qty_required,
                    })
                processed_a.add(key)

            for key, rec in existing_a_map.items():
                if key not in processed_a:
                    rec.unlink()

            # 4. Recompute summary fields
            project._compute_total_material()
            project._compute_total_equipment()
            project._compute_sub_total_summary()

    def action_create_rab_from_material(self):
        self.ensure_one()

        # RAB sudah ada dan bukan draft
        if self.rab_id and self.rab_id.state != 'draft':
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Info',
                    'message': 'Maaf RAB sudah dikonfirmasi/negosiasi dan tidak dapat diubah dari sini.',
                    'type': 'warning',
                    'sticky': False,
                }
            }

        if not self.material_master_ids and not self.equipment_master_ids:
            raise UserError("Material Project dan Equipment masih kosong.")

        # VALIDATION: Check if material quantities match tasks
        ProjectMaterial = self.env['project.material.master']
        primary_map = {}
        for task in self.task_ids:
            job_type = task.job_type or 'primary'
            if job_type == 'primary':
                # 1a. Own task's product/weight
                if task.product_id:
                    pid = task.product_id.id
                    primary_map.setdefault(pid, 0.0)
                    primary_map[pid] += task.weight or 0.0

                # 1b. Manual materials in this task
                for mat in task.material_needed_ids.filtered(lambda m: m.source == 'manual'):
                    if mat.product_id:
                        pid = mat.product_id.id
                        primary_map.setdefault(pid, 0.0)
                        primary_map[pid] += mat.weight or 0.0

        # Get existing master primary materials
        existing_primary = ProjectMaterial.search([
            ('project_id', '=', self.id),
            ('job_type', '=', 'primary'),
            ('is_manual', '=', False)
        ])

        # 1. Check if all products from tasks are in master
        # Use a dictionary of product_id -> total_weight from master
        master_map = {rec.product_id.id: rec.total_weight for rec in existing_primary}

        mismatch_found = False
        # Check if everything in task is in master
        for pid, task_weight in primary_map.items():
            master_weight = master_map.get(pid, 0.0)
            if abs(task_weight - master_weight) > 0.01:
                mismatch_found = True
                break

        if not mismatch_found:
            # Check if everything in master (that's not manual) is in tasks
            for pid in master_map:
                if pid not in primary_map:
                    mismatch_found = True
                    break

        if mismatch_found:
            raise UserError("validasi jumlah material qty yang di \"project.task\" dan total qty material di tab \"material project\" Berbeda. Silahkan klik 'Hitung Ulang Material' terlebih dahulu.")

        if not self.partner_id:
            raise UserError("Project harus memiliki Customer sebelum membuat RAB.")

        RabSudo = self.env['rab.management'].sudo()
        RabLine = self.env['rab.management.line'].sudo()

        # Ambil atau buat RAB HEADER
        if self.rab_id:
            rab = self.rab_id
        else:
            rab = RabSudo.create({
                'customer_id': self.partner_id.id,
                'source_type': 'project',
                'project_id': self.id,
            })
            self.rab_id = rab.id

        # Aggregate all products and track managed products
        product_quantities = {}
        managed_products = set()

        # 1. Primary Material
        for mat in self.material_master_ids.filtered(lambda m: m.job_type == 'primary'):
            if mat.product_id:
                pid = mat.product_id.id
                managed_products.add(pid)
                product_quantities[pid] = product_quantities.get(pid, 0.0) + mat.qty_beli

        # 2. Primary Equipment
        for equip in self.equipment_master_ids.filtered(lambda e: e.job_type == 'primary'):
            if equip.product_id:
                pid = equip.product_id.id
                managed_products.add(pid)
                product_quantities[pid] = product_quantities.get(pid, 0.0) + equip.qty_beli

        # 3. Kawat Las Steelwork
        if self.kawat_las_product_id:
            pid = self.kawat_las_product_id.id
            managed_products.add(pid)
            product_quantities[pid] = product_quantities.get(pid, 0.0) + self.kawat_las_kebutuhan_dus

        # 4. Kawat Las Rewelding
        if self.rewelding_product_id:
            pid = self.rewelding_product_id.id
            managed_products.add(pid)
            product_quantities[pid] = product_quantities.get(pid, 0.0) + self.rewelding_kebutuhan_dus

        # 5. Overhead items (Man Power, Operasional, Mob Demob, Oksigen, LPG)
        overhead_prices = {}
        overhead_map = {
            'manpower': self.total_manpower,
            'operasional': self.total_operasional,
            'mobdemob': self.total_mobdemob,
            'oksigen': self.total_oksigen,
            'lpg': self.total_lpg,
        }
        for category, amount in overhead_map.items():
            if not amount:
                continue
            product = self.env['product.product'].search(
                [('category_project', '=', category)], limit=1)
            if not product:
                continue
            pid = product.id
            managed_products.add(pid)
            product_quantities[pid] = 1.0
            overhead_prices[pid] = amount

        # Update, Create or keep RAB lines
        for line in rab.line_ids:
            pid = line.product_id.id
            if pid in managed_products:
                # Update existing line quantity (using qty_beli, can be 0)
                quantity = product_quantities.get(pid, 0.0)
                update_vals = {'quantity': quantity}
                if pid in overhead_prices:
                    update_vals['purchase_price'] = overhead_prices[pid]
                line.write(update_vals)
                # Remove from dict so we don't create it again
                product_quantities.pop(pid, None)
                # DO NOT DELETE managed lines anymore

        # Create new RAB lines for remaining products in product_quantities
        for product_id, quantity in product_quantities.items():
            create_vals = {
                'rab_id': rab.id,
                'product_id': product_id,
                'quantity': quantity,
            }
            if product_id in overhead_prices:
                create_vals['purchase_price'] = overhead_prices[product_id]
            RabLine.create(create_vals)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Berhasil',
                'message': f'Data Proyek berhasil di-sync ke RAB {rab.name}.',
                'type': 'success',
                'sticky': False,
                'next': {'type': 'ir.actions.client', 'tag': 'reload'},
            }
        }

    def _create_material_consumption_picking(self, so):
        """Buat delivery order (outgoing) untuk konsumsi material proyek dari stok ke customer."""
        self.ensure_one()

        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'outgoing'),
            ('sequence_code', '=', 'OUT'),
            ('warehouse_id.company_id', '=', self.env.company.id),
        ], limit=1)

        if not picking_type:
            raise UserError("Tidak ada tipe Delivery Order (outgoing) yang tersedia di perusahaan ini.")

        # Kumpulkan semua material dari project, gabungkan duplikat
        move_map = {}  # product_id -> {product_id, qty, uom_id}

        def add_move(product, qty):
            if not product or qty <= 0:
                return
            if product.type == 'service':
                return
            pid = product.id
            if pid in move_map:
                move_map[pid]['qty'] += qty
            else:
                move_map[pid] = {
                    'product_id': pid,
                    'qty': qty,
                    'uom_id': product.uom_id.id,
                }

        # 1. Material Proyek (primary)
        for mat in self.material_master_ids.filtered(lambda m: m.job_type == 'primary'):
            add_move(mat.product_id, mat.qty_beli)

        # 2. Peralatan & Perkakas (primary)
        for equip in self.equipment_master_ids.filtered(lambda e: e.job_type == 'primary'):
            add_move(equip.product_id, equip.qty_beli)

        # 3. Steelwork (kawat las)
        add_move(self.kawat_las_product_id, self.kawat_las_kebutuhan_dus)

        # 4. Rewelding
        add_move(self.rewelding_product_id, self.rewelding_kebutuhan_dus)

        if not move_map:
            return

        src_location = picking_type.default_location_src_id
        dest_location = picking_type.default_location_dest_id

        company = self.env.company
        Product = self.env['product.product']

        move_vals_list = []
        for data in move_map.values():
            product = Product.browse(data['product_id'])
            move_vals_list.append({
                'description_picking': product.display_name,
                'product_id': data['product_id'],
                'product_uom_qty': data['qty'],
                'product_uom': data['uom_id'],
                'location_id': src_location.id,
                'location_dest_id': dest_location.id,
                'picking_type_id': picking_type.id,
                'company_id': company.id,
                'origin': so.name,
            })

        picking = self.env['stock.picking'].sudo().create({
            'picking_type_id': picking_type.id,
            'location_id': src_location.id,
            'location_dest_id': dest_location.id,
            'partner_id': self.partner_id.id,
            'company_id': company.id,
            'origin': so.name,
            'move_ids': [(0, 0, vals) for vals in move_vals_list],
        })

        picking.action_confirm()
        picking.action_assign()

        return picking

    def action_create_additional_rab(self):
        self.ensure_one()

        additional_items = (self.additional_material_ids + self.additional_equipment_ids).filtered(
            lambda r: not r.is_converted
        )

        if not additional_items:
            raise UserError("Tidak ada item additional yang belum diproses.")

        if not self.partner_id:
            raise UserError("Project harus memiliki Customer sebelum membuat RAB.")

        RabSudo = self.env['rab.management'].sudo()
        RabLine = self.env['rab.management.line'].sudo()

        rab = RabSudo.create({
            'customer_id': self.partner_id.id,
            'source_type': 'additional',
            'project_id': self.id,
        })

        for item in additional_items:
            RabLine.create({
                'rab_id': rab.id,
                'product_id': item.product_id.id,
                'quantity': item.qty_beli,
            })

        # Mark items as converted/linked
        additional_items.write({
            'is_converted': True,
            'rab_id': rab.id,
        })

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': f'RAB Additional berhasil dibuat: {rab.name}',
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
            'is_project_so': True,
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
