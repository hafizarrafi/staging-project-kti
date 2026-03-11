/** @odoo-module **/

/**
 * PackingBoardWidget – Odoo form field widget wrapper around PackingBoard.
 *
 * Usage in view XML:
 *   <field name="id" widget="packing_board_widget" nolabel="1" readonly="0"/>
 *
 * We use the record `id` (picking id) as the prop source because the board
 * only needs it to call the RPC methods.
 */

import { Component, onWillStart, onWillUpdateProps, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { PackingBoard } from "../components/packing_board/packing_board";

export class PackingBoardWidget extends Component {
    static components = { PackingBoard };
    static props = {
        ...standardFieldProps,
    };

    setup() {
        this.state = useState({ pickingId: null });

        const setId = (props) => {
            // value of the 'id' field is the picking ID
            this.state.pickingId = props.record.resId || null;
        };

        onWillStart(() => setId(this.props));
        onWillUpdateProps((nextProps) => setId(nextProps));
    }

    get isBoardReadonly() {
        // 'id' field is naturally readonly=true in Odoo.
        // We want the board to be editable if picking state is NOT 'done' or 'cancel'.
        const state = this.props.record.data.state;
        return ["done", "cancel"].includes(state);
    }
}

PackingBoardWidget.template = "fastindo_project.PackingBoardWidget";

registry.category("fields").add("packing_board_widget", {
    component: PackingBoardWidget,
    supportedTypes: ["integer"],   // used on the 'id' integer field
});
