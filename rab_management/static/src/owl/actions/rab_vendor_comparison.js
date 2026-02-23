/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { VendorMatrix } from "../components/vendor_matrix/vendor_matrix";

export class RabVendorComparisonAction extends Component {
    setup() {
        this.actionService = useService("action");
        this.notification = useService("notification");

        // RAB aktif dari action context
        this.rabId = this.props?.action?.context?.active_id;

        if (!this.rabId) {
            this.notification.add(
                "RAB ID tidak ditemukan.",
                { type: "danger" }
            );
        }

        
    }

    closeAndBack() {
        if (!this.rabId) {
            this.notification.add(
                "Tidak bisa kembali, RAB ID tidak valid.",
                { type: "danger" }
            );
            return;
        }

        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "RAB",
            res_model: "rab.management",
            res_id: this.rabId,
            views: [[false, "form"]],
            target: "current",
        });
    }

}

RabVendorComparisonAction.template =
    "rab_management.RabVendorComparisonAction";

RabVendorComparisonAction.components = {
    VendorMatrix,
};

registry.category("actions").add(
    "rab_vendor_comparison_action",
    RabVendorComparisonAction
);
