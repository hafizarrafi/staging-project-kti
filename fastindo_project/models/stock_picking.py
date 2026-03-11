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
        string='List Packages',
        compute='_compute_package_ids'
    )

    packages_summary_html = fields.Html(
        string='Ringkasan Kemasan',
        compute='_compute_packages_summary_html',
        sanitize=False,
    )

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
    def _compute_package_ids(self):
        for picking in self:
            picking.package_ids = picking.move_line_ids.mapped('result_package_id')

    @api.depends('move_line_ids.result_package_id')
    def _compute_display_package_ids(self):
        for picking in self:
            picking.display_package_ids = picking.move_line_ids.result_package_id

    # ── Helpers ─────────────────────────────────────────────────────────────────

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

    # ── Actions ─────────────────────────────────────────────────────────────────

    def action_reset_packing(self):
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

        # Hapus package kosong
        for pkg in packages_before:
            if not pkg.move_line_ids and not pkg.quant_ids:
                pkg.unlink()

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

        # Reset dulu jika sudah ada package sebelumnya
        if self.move_line_ids.filtered(lambda l: l.result_package_id):
            self.action_reset_packing()

        # ── 1. Kumpulkan move lines ──────────────────────────────────────────────
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

        return True
