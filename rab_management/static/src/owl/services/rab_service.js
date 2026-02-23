/** @odoo-module */

import { registry } from "@web/core/registry";

export const rabService = {
    dependencies: ["orm"],

    start(env, { orm }) {
        return {
            // Ambil data matrix vendor untuk satu RAB
            async fetchVendorMatrix(rabId) {
                const lines = await orm.searchRead(
                    "rab.management.line",
                    [["rab_id", "=", rabId]],
                    ["id", "product_id", "quantity"]
                );

                const lineIds = lines.map(l => l.id);

                const vendorLines = await orm.searchRead(
                    "rab.vendor.comparison",
                    [["rab_line_id", "in", lineIds]],
                    [
                        "id",
                        "rab_line_id",
                        "vendor_id",
                        "price",
                        "negotiation_price",
                        "vendor_state",
                        "last_purchase_price",
                        "has_so_confirmed",
                    ]
                );

                return { lines, vendorLines };
            },

            // Ubah status draft ke negotiation
            async setNegotiation(id) {
                return orm.call(
                    "rab.vendor.comparison",
                    "action_set_negotiation",
                    [[id]]
                );
            },

            // Ubah status negotiation ke final
            async setFinalVendor(id) {
                return orm.call(
                    "rab.vendor.comparison",
                    "action_set_final",
                    [[id]]
                );
            },

            // Reset vendor final
            async resetFinal(id) {
                return orm.call(
                    "rab.vendor.comparison",
                    "action_reset_final",
                    [[id]]
                );
            },

            // Update harga awal
            async updateBasePrice(id, price) {
                return orm.write(
                    "rab.vendor.comparison",
                    [id],
                    { price }
                );
            },

            // Update harga negosiasi
            async updateNegotiationPrice(id, price) {
                return orm.write(
                    "rab.vendor.comparison",
                    [id],
                    { negotiation_price: price }
                );
            },

            async createVendorLine(vals) {
                return orm.create(
                    "rab.vendor.comparison",
                    [vals]
                );
            },

            async updateRabLine(id, vals) {
                return orm.write(
                    "rab.management.line",
                    [id],
                    vals
                );
            },

            async createRabLine(vals) {
                return orm.create(
                    "rab.management.line",
                    [vals]
                );
            }




        };
    },
};

registry.category("services").add("rabService", rabService);
