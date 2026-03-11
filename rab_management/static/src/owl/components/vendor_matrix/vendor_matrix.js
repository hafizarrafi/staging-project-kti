/** @odoo-module **/

import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { SelectCreateDialog } from "@web/views/view_dialogs/select_create_dialog";


export class VendorMatrix extends Component {
    setup() {
        this.state = useState({
            vendors: [],
            items: [],
            loading: true,

            newProduct: {
                query: "",
                results: [],
                open: false,
                highlightedIndex: -1,
                dropdownStyle: "",
            }
        });


        this.rabService = useService("rabService");
        this.orm = useService("orm");
        this.dialog = useService("dialog");

        onWillStart(async () => {
            await this.reloadMatrix();
            this.state.loading = false;
        });

        onMounted(async () => {
            await this.waitForDomStable();
            this.syncRowHeights();
            this.syncScrollX();
        
        });

    

    }

    async reloadMatrix() {
        const { lines, vendorLines } =
            await this.rabService.fetchVendorMatrix(this.props.rabId);

        this.buildMatrix(lines, vendorLines);

        // Tunggu render dan layout stabil
        await this.waitForDomStable();
        this.syncRowHeights();
        this.syncScrollX();
    }

    buildMatrix(lines, vendorLines) {
        const vendorMap = {};
        const itemMap = {};

        for (const line of lines) {
            itemMap[line.id] = {
                id: line.id,
                name: line.product_id[1],
                qty: line.quantity,
                prices: {},
                selectedVendorId: null,
                selectedVendorName: null,
                selectedPrice: null,
            };
        }

        for (const v of vendorLines) {
            const lineId = v.rab_line_id[0];
            const vendorId = v.vendor_id[0];

            vendorMap[vendorId] ??= {
                id: vendorId,
                name: v.vendor_id[1],
            };

            itemMap[lineId].prices[vendorId] = {
                id: v.id,
                vendor_id: vendorId,
                base: v.price,
                nego: v.negotiation_price,
                lastPurchase: v.last_purchase_price,
                vendor_state: v.vendor_state,
                has_so_confirmed: v.has_so_confirmed,
                isBest: false,
                isDimmed: false,
            };
        }

        for (const item of Object.values(itemMap)) {
            const prices = Object.values(item.prices);

            const finalLine = prices.find(p => p.vendor_state === "final");
            if (finalLine) {
                item.selectedVendorId = finalLine.vendor_id;
                item.selectedVendorName =
                    vendorMap[finalLine.vendor_id]?.name || "-";
                item.selectedPrice = finalLine.nego;
            }

           const candidates = prices.filter(
                p => p.vendor_state === "negotiation" && p.nego > 0
            );


            if (!candidates.length) continue;

            const bestValue = Math.min(...candidates.map(p => p.nego));

            for (const p of candidates) {
                p.isBest = p.nego === bestValue;
                p.isDimmed =
                    Boolean(finalLine) &&
                    !["final", "cancelled"].includes(p.vendor_state);


            }
        }

        this.state.vendors = Object.values(vendorMap);
        this.state.items = Object.values(itemMap);
    }

    // Tunggu DOM stabil untuk operasi async
    async waitForDomStable() {
        // 1 frame render
        await new Promise(resolve => requestAnimationFrame(resolve));
        // 2 frame layout
        await new Promise(resolve => requestAnimationFrame(resolve));
        // microtask queue (input/button render)
        await Promise.resolve();
    }

    // samakan tinggi baris antara sticky dan scrollable
    syncRowHeights() {
        this.syncSection(
            ".matrix-body-left tbody tr",
            ".matrix-body-right tbody tr"
        );

        this.syncSection(
            ".matrix-header-left tbody tr",
            ".matrix-header-right tbody tr"
        );
        }

    syncSection(leftSelector, rightSelector) {
        const leftRows = document.querySelectorAll(leftSelector);
        const rightRows = document.querySelectorAll(rightSelector);

        leftRows.forEach((leftRow, i) => {
            const rightRow = rightRows[i];
            if (!rightRow) return;

            // Reset tinggi dulu
            leftRow.style.minHeight = "";
            rightRow.style.minHeight = "";

            const h = Math.max(
                leftRow.offsetHeight,
                rightRow.offsetHeight
            );

            leftRow.style.minHeight = `${h}px`;
            rightRow.style.minHeight = `${h}px`;
        });
    }

    syncScrollX() {
        const headerScroll = document.querySelector(
            ".matrix-header .matrix-right-scroll"
        );
        const bodyScroll = document.querySelector(
            ".matrix-body .matrix-right-scroll"
        );

        if (!headerScroll || !bodyScroll) return;

        let isSyncingHeader = false;
        let isSyncingBody = false;

        headerScroll.addEventListener("scroll", () => {
            if (isSyncingHeader) return;
            isSyncingBody = true;
            bodyScroll.scrollLeft = headerScroll.scrollLeft;
            isSyncingBody = false;
        });

        bodyScroll.addEventListener("scroll", () => {
            if (isSyncingBody) return;
            isSyncingHeader = true;
            headerScroll.scrollLeft = bodyScroll.scrollLeft;
            isSyncingHeader = false;
        });
    }

    // action handlers
    async onChangeBasePrice(ev) {
        const id = Number(ev.target.dataset.id);
        const value = Number(ev.target.value);
        if (!id || isNaN(value)) return;

        await this.rabService.updateBasePrice(id, value);
        await this.reloadMatrix();
    }

    async onChangeNegotiationPrice(ev) {
        const id = Number(ev.target.dataset.id);
        const value = Number(ev.target.value);
        if (!id || isNaN(value)) return;

        // Validasi: harga nego tidak boleh lebih tinggi dari harga quotation
        const basePrice = Number(ev.target.dataset.basePrice);
        if (basePrice > 0 && value > basePrice) {
            alert('Harga negosiasi tidak boleh lebih tinggi dari harga quotation!');
            ev.target.value = basePrice; // Reset ke harga quotation
            return;
        }

        await this.rabService.updateNegotiationPrice(id, value);
        await this.reloadMatrix();
    }

    async onSetNegotiation(ev) {
        const id = Number(ev.currentTarget.dataset.id);
        if (!id) return;

        // Cek apakah sales order sudah confirmed
        const priceLine = this.findPriceLineById(id);
        if (!priceLine) {
            alert('Data tidak ditemukan!');
            return;
        }

        if (!priceLine.has_so_confirmed) {
            alert('Tidak dapat memulai negosiasi! Sales Order belum dikonfirmasi.');
            return;
        }

        await this.rabService.setNegotiation(id);
        await this.reloadMatrix();
    }

    async onSelectVendor(ev) {
        const id = Number(ev.currentTarget.dataset.id);
        if (!id) return;

        await this.rabService.setFinalVendor(id);
        await this.reloadMatrix();
    }

    async onResetFinal(ev) {
        const id = Number(ev.currentTarget.dataset.id);
        if (!id) return;

        await this.rabService.resetFinal(id);
        await this.reloadMatrix();
    }

    findPriceLineById(id) {
        for (const item of this.state.items) {
            for (const priceLine of Object.values(item.prices)) {
                if (priceLine.id === id) {
                    return priceLine;
                }
            }
        }
        return null;
    }

    formatPrice(value) {
        return value ? value.toLocaleString("id-ID") : "-";
    }

    async onAddVendorLine(ev) {
        const lineId = Number(ev.currentTarget.dataset.lineId);
        const vendorId = Number(ev.currentTarget.dataset.vendorId);

        if (!lineId || !vendorId) return;

        await this.rabService.createVendorLine({
            rab_line_id: lineId,
            vendor_id: vendorId,
            price: 0,
        });

        await this.reloadMatrix();
    }


    async onChangeQty(ev) {
        const lineId = Number(ev.target.dataset.id);
        const value = Number(ev.target.value);

        if (!lineId || isNaN(value)) return;

        await this.rabService.updateRabLine(lineId, {
            quantity: value,
        });

        await this.reloadMatrix();
    }
    
    async onAddProduct() {
        if (!this.props.rabId) return;

        const productId = await this.selectProduct();
        if (!productId) return;

        await this.rabService.createRabLine({
            rab_id: this.props.rabId,
            product_id: productId,
            quantity: 1,
        });

        await this.reloadMatrix();
    }


    async onSelectProduct(productId) {
        if (!productId || !this.props?.rabId) return;

        await this.rabService.createRabLine({
            rab_id: this.props.rabId,
            product_id: productId,
            quantity: 0,
        });

        this.state.newProduct.query = "";
        this.state.newProduct.results = [];
        this.state.newProduct.open = false;
        this.state.newProduct.highlightedIndex = -1;

        await this.reloadMatrix();

    }


    async onSearchProduct(ev) {
        const value = ev.target.value;

        this.state.newProduct.query = value;

        if (!value || value.length < 1) {
            this.state.newProduct.results = [];
            this.state.newProduct.open = false;
            return;
        }

        const rect = ev.target.getBoundingClientRect();

        this.state.newProduct.dropdownStyle =
            `position:fixed;
            top:${rect.bottom}px;
            left:${rect.left}px;
            width:${rect.width}px;
            z-index:99999;`;

        const results = await this.orm.call(
            "product.product",
            "name_search",
            [value],
            { limit: 10 }
        );

        this.state.newProduct.results = results;
        this.state.newProduct.open = true;
        this.state.newProduct.highlightedIndex = results.length ? 0 : -1;
    }


    onProductKeydown(ev) {
        const np = this.state.newProduct;

        if (!np.open) return;

        if (ev.key === "ArrowDown") {
            ev.preventDefault();
            ev.stopPropagation();

            const max = np.results.length - 1;
            np.highlightedIndex =
                np.highlightedIndex < max
                    ? np.highlightedIndex + 1
                    : 0;

                            console.log("highlight:", np.highlightedIndex); // ⬅️ DI SINI
        }

        if (ev.key === "ArrowUp") {
            ev.preventDefault();
            ev.stopPropagation();

            const max = np.results.length - 1;
            np.highlightedIndex =
                np.highlightedIndex > 0
                    ? np.highlightedIndex - 1
                    : max;

                            console.log("highlight:", np.highlightedIndex); // ⬅️ DI SINI
        }

        if (ev.key === "Enter") {
            ev.preventDefault();
            ev.stopPropagation();

            if (np.highlightedIndex >= 0) {
                const prod = np.results[np.highlightedIndex];
                this.onSelectProduct(prod[0]);
            }
        }

        if (ev.key === "Escape") {
            np.open = false;
        }
    }

}

VendorMatrix.template = "rab_management.VendorMatrix";
