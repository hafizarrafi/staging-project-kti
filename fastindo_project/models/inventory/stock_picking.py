import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_round

_logger = logging.getLogger(__name__)

MIN_INNER_BOX = 7
MAX_INNER_BOX = 12


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    package_history_id = fields.Many2one(
        'stock.package.history', string="Package History", index='btree_not_null'
    )
    display_package_ids = fields.Many2many(
        'stock.package', compute='_compute_display_package_ids', string='Packages'
    )

    package_ids = fields.Many2many(
        'stock.package',
        string='List Packages'
    )

    shipping_weight = fields.Float(
        string='Total Berat (kg)',
        related='sale_id.total_weight',
        readonly=True,
        help='Total berat produk dari Sales Order.'
    )
    shipping_cost = fields.Monetary(
        string='Estimasi Ongkir',
        related='sale_id.estimated_shipping_cost',
        readonly=True,
        currency_field='company_currency_id',
        help='Estimasi biaya pengiriman dari Sales Order.'
    )

    company_currency_id = fields.Many2one(
        'res.currency', string='Currency', related='company_id.currency_id', readonly=True
    )

    packing_history = fields.Json(string="Packing History", default=[])
    packing_history_index = fields.Integer(string="Packing History Index", default=-1)

    packages_summary_html = fields.Html(
        string='Ringkasan Kemasan',
        compute='_compute_packages_summary_html',
        sanitize=False,
    )

    def _check_packing_modifiable(self):
        self.ensure_one()
        if self.state in ['done', 'cancel']:
            raise UserError(_("Tidak bisa mengubah packing pada transfer yang sudah Selesai atau Dibatalkan."))

    def _compute_packages_summary_html(self):
        for picking in self:
            if not picking.package_ids:
                picking.packages_summary_html = False
                continue
            
            # Data in Python, Rendering in QWeb
            picking.packages_summary_html = self.env['ir.qweb']._render(
                'fastindo_project.packing_dashboard',
                {'doc': picking}
            )


    @api.depends('move_line_ids.result_package_id')
    def _compute_display_package_ids(self):
        for picking in self:
            picking.display_package_ids = picking.move_line_ids.result_package_id

    # Helpers 

    def _create_package(self):
        """Buat outer box baru."""
        return self.env['stock.package'].create({
            'name': self.env['ir.sequence'].next_by_code('stock.package') or 'BOX',
        })

    def _assign_qty_to_package(self, pline, qty_to_take, package):
        """
        Alokasikan `qty_to_take` unit dari move line ke package.
        Jika hanya sebagian, move line di-split.

        pline keys: line (stock.move.line), remaining (float)
        """
        line = pline['line']
        rounding = line.product_uom_id.rounding

        qty_to_assign = float_round(min(qty_to_take, line.quantity), precision_rounding=rounding)
        remaining_after = float_round(line.quantity - qty_to_assign, precision_rounding=rounding)

        if remaining_after > rounding:
            # Split: buat move line baru untuk porsi ini, kurangi qty asal
            if qty_to_assign > 0:
                self.env['stock.move.line'].create({
                    'picking_id': line.picking_id.id,
                    'move_id': line.move_id.id,
                    'product_id': line.product_id.id,
                    'product_uom_id': line.product_uom_id.id,
                    'location_id': line.location_id.id,
                    'location_dest_id': line.location_dest_id.id,
                    'lot_id': line.lot_id.id if line.lot_id else False,
                    'package_id': line.package_id.id if line.package_id else False,
                    'result_package_id': package.id,
                    'quantity': qty_to_assign,
                    'picked': True,
                })
                line.quantity = remaining_after
        else:
            # Seluruh line masuk package ini
            line.write({'result_package_id': package.id, 'picked': True})

        pline['remaining'] = float_round(pline['remaining'] - qty_to_assign, precision_rounding=rounding)

    # Actions
    def action_reset_packing(self, block_history=False, spare_pack_ids=False):
        """
        Hapus semua alokasi package dan kembalikan move lines ke kondisi semula.
        Split lines (yang dibuat Smart Packing) digabung kembali ke line induknya.
        Package kosong yang dihasilkan Smart Packing juga dihapus.
        """
        self.ensure_one()

        if self.state == 'done':
            raise UserError(_("Tidak bisa reset packing pada transfer yang sudah Done."))

        packages_before = self.move_line_ids.result_package_id

        # Pisahkan: split lines vs main lines
        split_lines = self.env['stock.move.line']
        main_lines = self.env['stock.move.line']

        for line in self.move_line_ids:
            if not line.result_package_id:
                continue
            # Split line = ada sibling dengan move_id+product_id yang sama tapi tanpa package
            has_sibling = self.move_line_ids.filtered(
                lambda l: l.move_id == line.move_id
                and l.product_id == line.product_id
                and not l.result_package_id
                and l.id != line.id
            )
            if has_sibling:
                split_lines |= line
            else:
                main_lines |= line

        # Kembalikan qty split lines ke parent
        for split_line in split_lines:
            parent = self.move_line_ids.filtered(
                lambda l: l.move_id == split_line.move_id
                and l.product_id == split_line.product_id
                and not l.result_package_id
                and l.id != split_line.id
            )[:1]
            if parent:
                parent.quantity = float_round(
                    parent.quantity + split_line.quantity,
                    precision_rounding=split_line.product_uom_id.rounding,
                )
        split_lines.unlink()

        # Clear assignment dari main lines
        main_lines.write({'result_package_id': False, 'picked': False})

        # Hapus package kosong (Hanya jika bukan restorasi history yang butuh package ini tetap hidup)
        for pkg in packages_before:
            if not pkg.move_line_ids and not pkg.quant_ids:
                if spare_pack_ids and pkg.id in spare_pack_ids:
                    continue
                pkg.unlink()

        # Clear persistent list
        if not spare_pack_ids:
            self.package_ids = [(5, 0, 0)]
        else:
            self.package_ids = [(6, 0, spare_pack_ids)]
            
        if not block_history:
            self._save_packing_checkpoint()

        return True

    def action_generate_smart_packing(self):
        """
        Smart Packing Fastindo.

        Konsep:
          1 unit yang dipesan  =  1 Inner Box  (tanpa lookup faktor konversi).
          Outer Box berisi 7–12 inner box, boleh campur SKU.

        Algoritma dua fase:
          Fase 1 – Full Box per SKU
            Setiap SKU dengan qty >= MAX (12) → outer box mandiri isi MAX, berulang.
          Fase 2 – Mixed Box dari Sisa
            Sisa qty semua SKU (<12) digabung ke outer box campuran hingga MAX.
            Box terakhir boleh < MIN (edge case tak terhindarkan).

        Contoh  20 unit Baut  +  10 unit Washer  +  12 unit Mur:
          Fase 1 →  Box 1: 12 Baut    │  Box 2: 12 Mur
          Fase 2 →  Box 3:  8 Baut + 4 Washer   │  Box 4: 6 Washer
        """
        self.ensure_one()

        if self.picking_type_code != 'outgoing':
            return False

        if self.state not in ['assigned', 'confirmed']:
            raise UserError(_("Packing hanya bisa dilakukan pada transfer yang siap (Ready)."))
            

        self.write({
            'packing_history': False,
            'packing_history_index': -1,
        })

        # Reset dulu jika sudah ada package sebelumnya
        if self.move_line_ids.filtered(lambda l: l.result_package_id):
            self.action_reset_packing()

        # 1. Kumpulkan move lines
        unpackaged_lines = self.move_line_ids.filtered(
            lambda l: l.quantity > 0.0001 and not l.result_package_id
        )
        if not unpackaged_lines:
            raise UserError(_("Tidak ada barang yang belum dikemas."))

        # qty inner = qty unit yang dipesan (1 unit = 1 inner box)
        packing_lines = []
        for line in unpackaged_lines:
            qty = line.quantity
            packing_lines.append({
                'line': line,
                'name': line.product_id.display_name,
                'qty': qty,
                'remaining': qty,
            })

        total = sum(p['qty'] for p in packing_lines)
        _logger.info(
            "Smart Packing %s: total=%s inner box → %s",
            self.name, total,
            [(p['name'], p['qty']) for p in packing_lines],
        )

        # ── 2. Fase 1: Full boxes per SKU (Isi 12) ───────────────────────────────
        for pline in packing_lines:
            while pline['remaining'] >= MAX_INNER_BOX - 0.0001:
                pkg = self._create_package()
                self._assign_qty_to_package(pline, MAX_INNER_BOX, pkg)

        # ── 2.5 Fase 1.5: Solo remainders (Isi 7-11) ─────────────────────────────
        # Prioritaskan SKU yang punya sisa 7-11 untuk dapat box sendiri (Solo SKU)
        # agar tidak bercampur dengan SKU lain jika sudah memenuhi batas minimum.
        for pline in packing_lines:
            rem = pline['remaining']
            if MIN_INNER_BOX - 0.0001 <= rem < MAX_INNER_BOX:
                pkg = self._create_package()
                self._assign_qty_to_package(pline, rem, pkg)

        # ── 3. Fase 2: Mixed boxes dari sisa yang benar-benar kecil (< 7) ────────
        remainder_queue = [p for p in packing_lines if p['remaining'] > 0.0001]
        current_items = []
        current_fill = 0.0

        def flush_box(items):
            if not items:
                return
            pkg = self._create_package()
            for pl, qty in items:
                self._assign_qty_to_package(pl, qty, pkg)

        for pline in remainder_queue:
            rem = pline['remaining']
            while rem > 0.0001:
                space = MAX_INNER_BOX - current_fill
                take = float_round(min(rem, space), precision_rounding=pline['line'].product_uom_id.rounding)

                current_items.append((pline, take))
                current_fill = float_round(current_fill + take, precision_digits=6)
                rem = float_round(rem - take, precision_rounding=pline['line'].product_uom_id.rounding)

                if current_fill >= MAX_INNER_BOX - 0.0001:
                    flush_box(current_items)
                    current_items = []
                    current_fill = 0.0

        flush_box(current_items)  # box terakhir (partial)
        
        # Update package_ids persistent list
        self.write({
            'package_ids': [(6, 0, self.move_line_ids.mapped('result_package_id').ids)]
        })

        # Simpan hasil smart packing sebagai state awal history (Floor)
        self._save_packing_checkpoint()

        return True

    def _consolidate_package_lines(self, package, preferred_line=None):
        """
        Gabungkan move lines dengan produk yang sama dalam satu package.
        Ini menjaga tampilan board tetap ringkas.
        
        @param preferred_line: stock.move.line yang diutamakan tetap ada (tidak di-unlink).
        """
        self.ensure_one()
        if not package:
            return
            
        # Group semua lines di picking ini yang ada di package ini
        relevant_lines = self.move_line_ids.filtered(
            lambda l: l.result_package_id == package and l.quantity > 0
        )
        
        # Kelompokkan berdasarkan dimensi unik agar tidak salah merge (Product + Lot + Owner + Package Induk)
        # Note: Kita fokus ke produk utama, lot, dan owner.
        groups = {}
        for line in relevant_lines:
            key = (line.product_id.id, line.lot_id.id, line.owner_id.id, line.package_id.id)
            if key not in groups:
                groups[key] = self.env['stock.move.line']
            groups[key] |= line
            
        for key, p_lines in groups.items():
            if len(p_lines) > 1:
                # Pilih 'master' line. Jika preferred_line ada di daftar ini, pakai itu.
                if preferred_line and preferred_line in p_lines:
                    main_line = preferred_line
                else:
                    main_line = p_lines[0]
                
                other_lines = p_lines - main_line
                
                total_qty = sum(l.quantity for l in p_lines)
                product = main_line.product_id
                rounding = product.uom_id.rounding
                
                main_line.write({
                    'quantity': float_round(total_qty, precision_rounding=rounding)
                })
                # Hapus baris tambahan
                other_lines.unlink()

    # ── OWL Board RPC ────────────────────────────────────────────────────────────

    def _packing_board_data(self):
        """
        Return a JSON-serialisable dict describing the current packing state
        untuk dikonsumsi OWL PackingBoard widget.
        """
        self.ensure_one()
        
        # Group ALL move lines (including 'done') by package for this picking
        lines_by_pkg = {}
        for ml in self.move_line_ids:
            if not ml.result_package_id or ml.quantity <= 0.0001:
                continue
            pkg_id = ml.result_package_id.id
            if pkg_id not in lines_by_pkg:
                lines_by_pkg[pkg_id] = []
            lines_by_pkg[pkg_id].append({
                'id': ml.id,
                'product_name': ml.product_id.display_name,
                'qty': ml.quantity,
                'uom': ml.product_uom_id.name,
            })

        packages = self.package_ids.sorted(key=lambda p: p.name)
        boxes = []
        for pkg in packages:
            lines = lines_by_pkg.get(pkg.id, [])
            boxes.append({
                'id': pkg.id,
                'name': pkg.name,
                'total_qty': pkg.total_inner_qty,
                'total_weight': pkg.total_weight,
                'fill_status': pkg.fill_status,
                'lines': lines,
            })
            
        # Collect unplaced lines (staged lines)
        staged_lines = []
        unplaced_mls = self.move_line_ids.filtered(
            lambda l: not l.result_package_id and l.quantity > 0.0001
        )
        for ml in unplaced_mls:
            staged_lines.append({
                'id': ml.id,
                'product_name': ml.product_id.display_name,
                'qty': ml.quantity,
                'uom': ml.product_uom_id.name,
            })

        # Calculate estimated shipping cost based on total weight and carrier price
        estimated_shipping_cost = 0.0
        total_weight = sum(b['total_weight'] for b in boxes)
        if self.sale_id and self.sale_id.carrier_id:
            estimated_shipping_cost = total_weight * self.sale_id.carrier_id.shipping_price_per_kg

        return {
            'boxes': boxes,
            'staged_lines': staged_lines,
            'total_weight': total_weight,
            'estimated_shipping_cost': estimated_shipping_cost,
            'currency': {
                'symbol': self.company_currency_id.symbol,
                'position': self.company_currency_id.position,
                'decimal_places': self.company_currency_id.decimal_places,
            },
            'can_undo': self.packing_history_index > 0 and self.state not in ['done', 'cancel'],
            'can_redo': self.packing_history_index < len(self.packing_history or []) - 1 and self.state not in ['done', 'cancel'],
        }

    def action_get_packing_data(self):
        """Button/RPC entrypoint – muat data board."""
        self.ensure_one()
        return self._packing_board_data()

    def action_move_line_to_package(self, line_id, target_pkg_id):
        """
        Pindahkan seluruh move line ke package lain.
        Return updated board data.
        """
        self.ensure_one()
        self._check_packing_modifiable()
        line = self.env['stock.move.line'].browse(int(line_id))
        if line.picking_id != self:
            raise UserError(_("Line tidak berasal dari picking ini."))
        pkg = self.env['stock.package'].browse(int(target_pkg_id))
        if not pkg.exists():
            raise UserError(_("Package tujuan tidak ditemukan."))
        line.write({'result_package_id': pkg.id})
        self._consolidate_package_lines(pkg, preferred_line=line)
        self._save_packing_checkpoint()
        return self._packing_board_data()

    def action_split_and_stage(self, line_id, split_qty):
        """
        Split ``split_qty`` dari line ke move line baru (result_package_id=False =
        'staged / unplaced').  Line baru ini kemudian bisa di-drag ke box tujuan.
        Return updated board data + id baru yang bisa di-drag.
        """
        self.ensure_one()
        self._check_packing_modifiable()
        line = self.env['stock.move.line'].browse(int(line_id))
        if line.picking_id != self:
            raise UserError(_("Line tidak berasal dari picking ini."))

        rounding = line.product_uom_id.rounding
        split_qty = float_round(float(split_qty), precision_rounding=rounding)

        if split_qty <= 0 or split_qty >= line.quantity:
            raise UserError(_("Qty split harus antara 0 dan qty penuh item."))

        remaining = float_round(line.quantity - split_qty, precision_rounding=rounding)
        line.quantity = remaining

        new_line = self.env['stock.move.line'].create({
            'picking_id': line.picking_id.id,
            'move_id': line.move_id.id,
            'product_id': line.product_id.id,
            'product_uom_id': line.product_uom_id.id,
            'location_id': line.location_id.id,
            'location_dest_id': line.location_dest_id.id,
            'lot_id': line.lot_id.id if line.lot_id else False,
            'package_id': line.package_id.id if line.package_id else False,
            'result_package_id': False,   # staged – belum ada di box
            'quantity': split_qty,
            'picked': True,
        })
        
        # Konsolidasi origin package jika perlu
        if line.result_package_id:
            self._consolidate_package_lines(line.result_package_id, preferred_line=line)
            
        self._save_packing_checkpoint()
        return self._packing_board_data()

    def action_split_and_move(self, line_id, split_qty, target_pkg_id):
        """
        Pecah qty dan langsung pindahkan ke box tujuan dalam satu transaksi.
        """
        self.ensure_one()
        self._check_packing_modifiable()
        line = self.env['stock.move.line'].browse(int(line_id))
        if line.picking_id != self:
            raise UserError(_("Line tidak berasal dari picking ini."))

        rounding = line.product_uom_id.rounding
        split_qty = float_round(float(split_qty), precision_rounding=rounding)

        if split_qty <= 0 or split_qty >= line.quantity:
            raise UserError(_("Qty split harus antara 0 dan qty penuh item."))

        pkg = self.env['stock.package'].browse(int(target_pkg_id))
        if not pkg.exists():
            raise UserError(_("Package tujuan tidak ditemukan."))

        remaining = float_round(line.quantity - split_qty, precision_rounding=rounding)
        line.quantity = remaining

        new_line = self.env['stock.move.line'].create({
            'picking_id': line.picking_id.id,
            'move_id': line.move_id.id,
            'product_id': line.product_id.id,
            'product_uom_id': line.product_uom_id.id,
            'location_id': line.location_id.id,
            'location_dest_id': line.location_dest_id.id,
            'lot_id': line.lot_id.id if line.lot_id else False,
            'package_id': line.package_id.id if line.package_id else False,
            'result_package_id': pkg.id,
            'quantity': split_qty,
            'picked': True,
        })
        
        # Konsolidasi packages
        if line.result_package_id:
            self._consolidate_package_lines(line.result_package_id, preferred_line=line)
        self._consolidate_package_lines(pkg, preferred_line=new_line)
        
        self._save_packing_checkpoint()
        return self._packing_board_data()

    def action_remove_package(self, package_id):
        """Hapus package dari picking. Hanya jika kosong."""
        self.ensure_one()
        self._check_packing_modifiable()
        pkg = self.env['stock.package'].browse(package_id)
        if not pkg.exists():
            return self._packing_board_data()
            
        # Cek apakah ada barang
        if pkg.move_line_ids:
            raise UserError(_("Tidak bisa menghapus box yang masih berisi barang."))
            
        # Hapus dari picking
        self.package_ids = [(3, pkg.id)]
        # Hapus record record package nya juga supaya tidak menumpuk di system
        pkg.unlink()
        
        self._save_packing_checkpoint()
        return self._packing_board_data()

    def action_add_empty_package(self):
        """Tambah box kosong baru ke picking."""
        self.ensure_one()
        self._check_packing_modifiable()
        pkg = self._create_package()
        self.package_ids = [(4, pkg.id)]
        self._save_packing_checkpoint()
        return self._packing_board_data()

    # ── History Logic ────────────────────────────────────────────────────────────

    def _save_packing_checkpoint(self):
        """Capture current state of allocations."""
        self.ensure_one()
        snap = []
        for ml in self.move_line_ids:
            if ml.quantity <= 0.0001:
                continue
            snap.append({
                'move_id': ml.move_id.id,
                'product_id': ml.product_id.id,
                'lot_id': ml.lot_id.id if ml.lot_id else False,
                'qty': ml.quantity,
                'pkg_id': ml.result_package_id.id if ml.result_package_id else False,
            })
        
        history = (self.packing_history or [])
        idx = self.packing_history_index
        
        # 1. Jangan simpan history kosong jika history belum dimulai
        if not history and not snap and not self.package_ids:
            return

        # 2. Jangan simpan jika state sama dengan snapshot terakhir (Redundansi)
        if idx >= 0 and idx < len(history):
            last_snap = history[idx]
            if last_snap['snap'] == snap and set(last_snap['package_ids']) == set(self.package_ids.ids):
                return

        # Truncate forward history if we were in the middle of undo stack
        if idx < len(history) - 1:
            history = history[:idx + 1]
            
        history.append({
            'snap': snap,
            'package_ids': self.package_ids.ids,
        })
        
        if len(history) > 30:
            history = history[-30:]
        
        self.write({
            'packing_history': history,
            'packing_history_index': len(history) - 1,
        })

    def action_undo_packing(self):
        self.ensure_one()
        if self.packing_history_index <= 0:
            return self._packing_board_data()
            
        # No more tail-save here, as every action saves AFTER its result.
        
        self.write({'packing_history_index': self.packing_history_index - 1})
        
        # Ensure we don't go below index 0
        if self.packing_history_index < 0:
            self.write({'packing_history_index': 0})
            
        return self._apply_snapshot(self.packing_history_index)

    def action_redo_packing(self):
        self.ensure_one()
        if self.packing_history_index >= len(self.packing_history or []) - 1:
            return self._packing_board_data()
            
        self.write({'packing_history_index': self.packing_history_index + 1})
        return self._apply_snapshot(self.packing_history_index)

    def _apply_snapshot(self, index):
        self.ensure_one()
        state = self.packing_history[index]
        snap = state['snap']
        pkg_ids = state['package_ids']

        # Verify packages still exist (prevent crash if hard-deleted)
        existing_pkgs = self.env['stock.package'].search([('id', 'in', pkg_ids)])
        valid_pkg_ids = existing_pkgs.ids

        # 1. Clear everything (Fidelity is easier by unlinking move lines)
        self.move_line_ids.unlink()

        # 2. Restore Package list (only existing ones)
        self.package_ids = [(6, 0, valid_pkg_ids)]

        # 3. Re-create move lines from snapshot
        for entry in snap:
            move = self.env['stock.move'].browse(entry['move_id'])
            if not move.exists():
                continue
            
            # If box was deleted, item goes to staged area
            target_pkg_id = entry['pkg_id'] if entry['pkg_id'] in valid_pkg_ids else False
            
            self.env['stock.move.line'].create({
                'picking_id': self.id,
                'move_id': move.id,
                'product_id': entry['product_id'],
                'product_uom_id': move.product_uom.id,
                'location_id': self.location_id.id,
                'location_dest_id': self.location_dest_id.id,
                'lot_id': entry['lot_id'],
                'quantity': entry['qty'],
                'result_package_id': target_pkg_id,
                'picked': True if target_pkg_id else False,
            })
        
        return self._packing_board_data()
