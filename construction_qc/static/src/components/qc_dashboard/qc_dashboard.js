/** @odoo-module **/

import { Component, useState, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { registry } from "@web/core/registry";

export class QcDashboard extends Component {
    static template = "construction_qc.QcDashboard";

    setup() {
        this.orm = useService("orm");
        this.actionService = useService("action");
        this.state = useState({
            loading: true,
            total: 0,
            approved: 0,
            rejected: 0,
            pending: 0,
            closed: 0,
            recent: [],
        });
        onMounted(() => this._loadData());
    }

    async _loadData() {
        try {
            const result = await this.orm.call(
                "qc.inspection",
                "get_dashboard_data",
                [],
                {}
            );
            Object.assign(this.state, result, { loading: false });
        } catch {
            this.state.loading = false;
        }
    }

    openInspections(state) {
        const domain = state ? [["state", "=", state]] : [];
        this.actionService.doAction({
            type: "ir.actions.act_window",
            name: "QC Inspections",
            res_model: "qc.inspection",
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
            domain,
        });
    }

    openRecord(id) {
        this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "qc.inspection",
            res_id: id,
            view_mode: "form",
            views: [[false, "form"]],
        });
    }
}

registry.category("actions").add("construction_qc.qc_dashboard", QcDashboard);
