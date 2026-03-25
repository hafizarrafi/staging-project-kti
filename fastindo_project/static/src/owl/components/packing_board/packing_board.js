/** @odoo-module **/

import { Component, useState, onWillStart, onWillUpdateProps } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

/**
 * PackingBoard – OWL component for interactive smart-picking drag-and-drop.
 *
 * Props:
 *   pickingId  (Number)  – ID of the stock.picking record
 *   readonly   (Boolean) – if true, disables drag-drop and split (default false)
 *
 * Design decisions:
 *   - Visual drag feedback (drop-target highlight) uses direct DOM classList
 *     to avoid OWL reactive re-renders that break HTML5 drag events.
 *   - draggingLineId is stored as plain instance var (non-reactive) for the
 *     same reason.
 *   - Split dialog state IS reactive because it doesn't interfere with drag.
 */
export class PackingBoard extends Component {
    static defaultProps = { readonly: false };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");

        // ── Plain (non-reactive) drag state ───────────────────────────────────
        this._draggingLineId = null;  // set in onDragStart, cleared in onDragEnd/onDrop
        this._isProcessing = false;   // lock for async actions

        // ── Reactive UI state ─────────────────────────────────────────────────
        this.state = useState({
            boxes: [],
            loading: true,
            splitDialog: {
                open: false,
                lineId: null,
                productName: "",
                maxQty: 0,
                inputQty: "",
                showAdvanced: false,
                targetBoxId: null,
                // Draggable state
                pos: { x: 0, y: 0 },
                isDragging: false,
                canUndo: false,
                canRedo: false,
            },
            totalWeight: 0,
            estimatedShippingCost: 0,
            stagedLines: [],
            currency: {
                symbol: "",
                position: "before",
                decimal_places: 0,
            },
        });

        this._onKeyDown = this._onKeyDown.bind(this);
        onWillStart(() => {
            this.loadData();
            window.addEventListener("keydown", this._onKeyDown);
        });

        // Ensure listener is removed if component is destroyed (standard OWL)
        // But in Odoo 19 we might need to handle it in a specific hook if needed.
        // For simplicity and common patterns, we'll keep it simple for now.

        onWillUpdateProps((nextProps) => {
            if (nextProps.pickingId !== this.props.pickingId) {
                this.state.loading = true;
                this.state.stagedLines = [];
                this.loadData();
            }
        });
    }

    formatCurrency(amount) {
        const { symbol, position, decimal_places } = this.state.currency;
        const formatted = (amount || 0).toLocaleString("en-US", {
            minimumFractionDigits: decimal_places,
            maximumFractionDigits: decimal_places,
        });
        return position === "before" ? `${symbol}${formatted}` : `${formatted}${symbol}`;
    }

    // ── Data ──────────────────────────────────────────────────────────────────

    async loadData() {
        if (!this.props.pickingId) {
            this.state.loading = false;
            return;
        }
        try {
            const data = await this.orm.call(
                "stock.picking",
                "action_get_packing_data",
                [[this.props.pickingId]]
            );
            this.state.boxes = data.boxes || [];
            this.state.stagedLines = data.staged_lines || [];
            this.state.totalWeight = data.total_weight || 0;
            this.state.estimatedShippingCost = data.estimated_shipping_cost || 0;
            this.state.currency = data.currency || this.state.currency;
            this.state.splitDialog.canUndo = data.can_undo || false;
            this.state.splitDialog.canRedo = data.can_redo || false;
        } catch (e) {
            this.notification.add("Gagal memuat data packing.", { type: "danger" });
        }
        this.state.loading = false;
    }

    // ── Drag-and-drop helpers ─────────────────────────────────────────────────

    /** Called on draggable item rows AND the staged item. */
    onDragStart(ev, lineId) {
        if (this.props.readonly) { ev.preventDefault(); return; }
        this._draggingLineId = lineId;
        ev.dataTransfer.effectAllowed = "move";
        ev.dataTransfer.setData("text/plain", String(lineId));
        ev.currentTarget.classList.add("is-dragging");
    }

    onDragEnd(ev) {
        this._draggingLineId = null;
        ev.currentTarget.classList.remove("is-dragging");
        // clean up any lingering drop-target highlights
        document.querySelectorAll(".fp-box-card.is-drop-target").forEach(el =>
            el.classList.remove("is-drop-target")
        );
    }

    /** Highlight the box being hovered – direct DOM, no state. */
    onDragOver(ev, _boxId) {
        ev.preventDefault();
        ev.dataTransfer.dropEffect = "move";
        const card = ev.currentTarget;
        if (!card.classList.contains("is-drop-target")) {
            document.querySelectorAll(".fp-box-card.is-drop-target").forEach(el =>
                el.classList.remove("is-drop-target")
            );
            card.classList.add("is-drop-target");
        }
    }

    onDragLeave(ev) {
        // Only remove if truly leaving the card (not entering a child)
        if (ev.currentTarget && !ev.currentTarget.contains(ev.relatedTarget)) {
            ev.currentTarget.classList.remove("is-drop-target");
        }
    }

    async onDrop(ev, targetBoxId) {
        ev.preventDefault();
        ev.stopPropagation();

        // Clear visual feedback immediately
        document.querySelectorAll(".fp-box-card.is-drop-target").forEach(el =>
            el.classList.remove("is-drop-target")
        );

        const lineId = this._draggingLineId
            || Number(ev.dataTransfer.getData("text/plain"));
        this._draggingLineId = null;

        if (!lineId || !targetBoxId || this._isProcessing) return;
        this._isProcessing = true;

        // Skip if already in target box
        const targetBox = this.state.boxes.find(b => b.id === targetBoxId);
        if (targetBox && targetBox.lines.some(l => l.id === lineId)) {
            this._isProcessing = false;
            return;
        }

        try {
            const data = await this.orm.call(
                "stock.picking",
                "action_move_line_to_package",
                [[this.props.pickingId], lineId, targetBoxId]
            );
            this.state.boxes = data.boxes || [];
            this.state.stagedLines = data.staged_lines || [];
            this.state.totalWeight = data.total_weight || 0;
            this.state.estimatedShippingCost = data.estimated_shipping_cost || 0;
            this.state.currency = data.currency || this.state.currency;
            this.state.splitDialog.canUndo = data.can_undo || false;
            this.state.splitDialog.canRedo = data.can_redo || false;
        } catch (e) {
            console.error("Drop error:", e);
            const msg = (e.data && e.data.message) || e.message;
            if (msg) {
                this.notification.add(msg, { type: "danger" });
            }
        } finally {
            this._isProcessing = false;
        }
    }

    // ── Staged line (post-split) ──────────────────────────────────────────────

    onStagedDragStart(ev, lineId) {
        this.onDragStart(ev, lineId);
    }

    // ── Package Removal ───────────────────────────────────────────────────────

    async removeEmptyPackage(ev, packageId) {
        ev.stopPropagation();
        if (this._isProcessing || !confirm("Hapus box kosong ini?")) return;
        this._isProcessing = true;

        try {
            const data = await this.orm.call(
                "stock.picking",
                "action_remove_package",
                [[this.props.pickingId], packageId]
            );
            this.state.boxes = data.boxes || [];
            this.state.stagedLines = data.staged_lines || [];
            this.state.totalWeight = data.total_weight || 0;
            this.state.estimatedShippingCost = data.estimated_shipping_cost || 0;
            this.state.currency = data.currency || this.state.currency;
            this.state.splitDialog.canUndo = data.can_undo || false;
            this.state.splitDialog.canRedo = data.can_redo || false;
            this.notification.add("Box dihapus.", { type: "success" });
        } catch (e) {
            console.error("Remove package error:", e);
            const msg = (e.data && e.data.message) || e.message;
            if (msg) {
                this.notification.add(msg, { type: "danger" });
            }
        } finally {
            this._isProcessing = false;
        }
    }

    async addEmptyPackage() {
        if (this._isProcessing || this.props.readonly) return;
        this._isProcessing = true;

        try {
            const data = await this.orm.call(
                "stock.picking",
                "action_add_empty_package",
                [[this.props.pickingId]]
            );
            this.state.boxes = data.boxes || [];
            this.state.stagedLines = data.staged_lines || [];
            this.state.totalWeight = data.total_weight || 0;
            this.state.estimatedShippingCost = data.estimated_shipping_cost || 0;
            this.state.currency = data.currency || this.state.currency;
            this.state.splitDialog.canUndo = data.can_undo || false;
            this.state.splitDialog.canRedo = data.can_redo || false;
            this.notification.add("Box baru ditambahkan.", { type: "success" });
        } catch (e) {
            console.error("Add package error:", e);
            const msg = (e.data && e.data.message) || e.message;
            if (msg) {
                this.notification.add(msg, { type: "danger" });
            }
        } finally {
            this._isProcessing = false;
        }
    }

    // ── Split dialog ──────────────────────────────────────────────────────────

    /** Utility: stop event propagation (used by scissors button mousedown). */
    onStopProp(ev) {
        ev.stopPropagation();
    }

    /** Called by the scissors button (NOT the draggable row). */
    openSplitDialog(ev, line) {
        ev.stopPropagation();   // don't bubble to the draggable row
        ev.preventDefault();
        if (this.props.readonly) return;
        Object.assign(this.state.splitDialog, {
            open: true,
            lineId: line.id,
            productName: line.product_name,
            maxQty: line.qty,
            inputQty: "",
            showAdvanced: false,
            targetBoxId: this.state.boxes.length > 0 ? this.state.boxes[0].id : null,
            pos: { x: 0, y: 0 }, // reset to center/default
            isDragging: false,
        });
    }

    // ── Draggable Dialog Logic ──────────────────────────────────────────────

    onDialogPointerDown(ev) {
        // Only drag from header, ignore buttons/inputs
        if (ev.target.closest("button") || ev.target.closest("input") || ev.target.closest("a") || ev.target.closest("select")) {
            return;
        }

        const dialog = ev.currentTarget.closest(".fp-dialog");
        const rect = dialog.getBoundingClientRect();

        // Store initial offset from top-left of dialog
        this._dragOffset = {
            x: ev.clientX - rect.left,
            y: ev.clientY - rect.top,
        };

        this.state.splitDialog.isDragging = true;

        // Capture pointer events to global window to handle mouse moving outside dialog
        ev.currentTarget.setPointerCapture(ev.pointerId);
    }

    onDialogPointerMove(ev) {
        if (!this.state.splitDialog.isDragging) return;

        // Update position based on pointer and initial offset
        this.state.splitDialog.pos = {
            x: ev.clientX - this._dragOffset.x,
            y: ev.clientY - this._dragOffset.y,
        };
    }

    onDialogPointerUp(ev) {
        if (this.state.splitDialog.isDragging) {
            this.state.splitDialog.isDragging = false;
            ev.currentTarget.releasePointerCapture(ev.pointerId);
        }
    }

    toggleAdvanced() {
        this.state.splitDialog.showAdvanced = !this.state.splitDialog.showAdvanced;
    }

    onTargetBoxChange(ev) {
        this.state.splitDialog.targetBoxId = parseInt(ev.target.value);
    }

    closeSplitDialog() {
        this.state.splitDialog.open = false;
    }

    onSplitQtyInput(ev) {
        this.state.splitDialog.inputQty = ev.target.value;
    }

    async doSplitHalf() {
        const d = this.state.splitDialog;
        await this._execSplit(d.lineId, d.maxQty / 2);
    }

    async doSplitCustom() {
        const d = this.state.splitDialog;
        const qty = parseFloat(d.inputQty);

        if (isNaN(qty) || qty <= 0 || qty >= d.maxQty) {
            this.notification.add(`Qty harus antara 0 dan ${d.maxQty}`, { type: "warning" });
            return;
        }

        // Prevent fractional split
        if (!Number.isInteger(qty)) {
            this.notification.add("Jumlah pecah harus berupa angka bulat (bukan desimal).", { type: "warning" });
            return;
        }

        await this._execSplit(d.lineId, qty);
    }

    async undo() {
        if (this._isProcessing || !this.state.splitDialog.canUndo) return;
        this._isProcessing = true;
        try {
            const data = await this.orm.call("stock.picking", "action_undo_packing", [[this.props.pickingId]]);
            this.state.boxes = data.boxes || [];
            this.state.stagedLines = data.staged_lines || [];
            this.state.totalWeight = data.total_weight || 0;
            this.state.estimatedShippingCost = data.estimated_shipping_cost || 0;
            this.state.currency = data.currency || this.state.currency;
            this.state.splitDialog.canUndo = data.can_undo || false;
            this.state.splitDialog.canRedo = data.can_redo || false;
        } catch (e) {
            console.error("Undo error:", e);
            // Only notify if it's a real error message from server
            const msg = (e.data && e.data.message) || e.message;
            if (msg) {
                this.notification.add(msg, { type: "danger" });
            }
        } finally {
            this._isProcessing = false;
        }
    }

    async redo() {
        if (this._isProcessing || !this.state.splitDialog.canRedo) return;
        this._isProcessing = true;
        try {
            const data = await this.orm.call("stock.picking", "action_redo_packing", [[this.props.pickingId]]);
            this.state.boxes = data.boxes || [];
            this.state.stagedLines = data.staged_lines || [];
            this.state.totalWeight = data.total_weight || 0;
            this.state.estimatedShippingCost = data.estimated_shipping_cost || 0;
            this.state.currency = data.currency || this.state.currency;
            this.state.splitDialog.canUndo = data.can_undo || false;
            this.state.splitDialog.canRedo = data.can_redo || false;
        } catch (e) {
            console.error("Redo error:", e);
            const msg = (e.data && e.data.message) || e.message;
            if (msg) {
                this.notification.add(msg, { type: "danger" });
            }
        } finally {
            this._isProcessing = false;
        }
    }

    _onKeyDown(ev) {
        if (ev.ctrlKey && ev.key.toLowerCase() === "z") {
            ev.preventDefault();
            this.undo();
        } else if (ev.ctrlKey && ev.key.toLowerCase() === "y") {
            ev.preventDefault();
            this.redo();
        }
    }

    async _execSplit(lineId, qty) {
        if (this._isProcessing) return;
        this._isProcessing = true;

        const d = this.state.splitDialog;
        const useMove = d.showAdvanced && d.targetBoxId;
        const rpcMethod = useMove ? "action_split_and_move" : "action_split_and_stage";
        const rpcArgs = useMove
            ? [[this.props.pickingId], lineId, qty, d.targetBoxId]
            : [[this.props.pickingId], lineId, qty];

        try {
            const data = await this.orm.call("stock.picking", rpcMethod, rpcArgs);
            this.state.boxes = data.boxes || [];
            this.state.stagedLines = data.staged_lines || [];
            this.state.totalWeight = data.total_weight || 0;
            this.state.estimatedShippingCost = data.estimated_shipping_cost || 0;
            this.state.currency = data.currency || this.state.currency;
            this.state.splitDialog.canUndo = data.can_undo || false;
            this.state.splitDialog.canRedo = data.can_redo || false;
            this.state.splitDialog.open = false;

            const msg = useMove
                ? "Item dipecah dan dipindahkan."
                : "Item dipecah — seret item kuning ke box tujuan.";
            this.notification.add(msg, { type: "success" });
        } catch (e) {
            console.error("Split error:", e);
            const msg = (e.data && e.data.message) || e.message;
            if (msg) {
                this.notification.add(msg, { type: "danger" });
            }
        } finally {
            this._isProcessing = false;
        }
    }

    // ── Helpers ───────────────────────────────────────────────────────────────

    get hasBoxes() { return this.state.boxes.length > 0; }

    isOdd(val) {
        return val % 2 !== 0;
    }

    formatQty(qty) {
        return parseFloat(qty.toFixed(4)).toString();
    }
}

PackingBoard.template = "fastindo_project.PackingBoard";
