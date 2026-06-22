/** @odoo-module **/

import { Component, onWillStart, onMounted, onWillUnmount, useState, useRef } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { loadJS } from "@web/core/assets";
import { registry } from "@web/core/registry";

const STATUS_COLORS = {
    ahead:    "#0F6E56",
    on_track: "#0F6E56",
    late:     "#BA7517",
    critical: "#CC3333",
};

export class SCurveDashboard extends Component {
    static template = "project_scurve.SCurveDashboard";
    static props = ["*"];

    setup() {
        this.rpc      = useService("rpc");
        this.action   = useService("action");
        this.chartRef = useRef("scurveChart");

        this.state = useState({
            loading:         true,
            error:           null,
            projectId:       null,
            projectName:     "",
            activePhaseId:   "all",
            kpis:            {},
            chartData:       { labels: [], plan: [], actual: [], forecast: [] },
            milestones:      [],
            infoExpanded:    false,
        });

        this._chart = null;

        onWillStart(async () => {
            // Load Chart.js — prefer Odoo's bundled copy, fall back to CDN
            try {
                await loadJS("/web/static/lib/Chart/Chart.bundle.min.js");
            } catch {
                await loadJS(
                    "https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"
                );
            }
            await this._resolveProject();
            if (this.state.projectId) {
                await this._loadData("all");
            }
        });

        onMounted(() => {
            if (!this.state.loading && this.state.projectId) {
                this._renderChart();
            }
        });

        onWillUnmount(() => {
            if (this._chart) {
                this._chart.destroy();
                this._chart = null;
            }
        });
    }

    // -----------------------------------------------------------------------
    // Data loading
    // -----------------------------------------------------------------------

    async _resolveProject() {
        // Project id can come from action context or URL
        const ctx = this.props.action?.context || {};
        let projectId = ctx.default_project_id || ctx.active_id || null;

        if (!projectId) {
            // Try to pick the first project the user can access
            try {
                const result = await this.rpc("/web/dataset/call_kw", {
                    model:  "project.project",
                    method: "search_read",
                    args:   [[], ["id", "name"]],
                    kwargs: { limit: 1, order: "id asc" },
                });
                if (result && result.length) {
                    projectId = result[0].id;
                    this.state.projectName = result[0].name;
                }
            } catch (e) {
                this.state.error = this.env._t("Could not load projects.");
                this.state.loading = false;
                return;
            }
        } else {
            // Fetch name
            try {
                const result = await this.rpc("/web/dataset/call_kw", {
                    model:  "project.project",
                    method: "read",
                    args:   [[projectId], ["name"]],
                    kwargs: {},
                });
                if (result && result.length) {
                    this.state.projectName = result[0].name;
                }
            } catch {
                // non-critical
            }
        }
        this.state.projectId = projectId;
    }

    async _loadData(milestoneFilter) {
        this.state.loading = true;
        this.state.error   = null;
        try {
            const result = await this.rpc("/web/dataset/call_kw", {
                model:  "project.scurve.dashboard",
                method: "get_scurve_data",
                args:   [this.state.projectId, milestoneFilter === "all" ? false : milestoneFilter],
                kwargs: {},
            });

            this.state.kpis       = result.kpis       || {};
            this.state.chartData  = result.chart_data || { labels: [], plan: [], actual: [], forecast: [] };
            this.state.milestones = result.milestones  || [];
        } catch (e) {
            this.state.error = this.env._t("Failed to load S-Curve data.");
            _logger.error("SCurveDashboard: RPC error", e);
        } finally {
            this.state.loading = false;
            // Re-render chart after state update
            setTimeout(() => this._renderChart(), 0);
        }
    }

    // -----------------------------------------------------------------------
    // Chart rendering
    // -----------------------------------------------------------------------

    _renderChart() {
        const canvas = this.chartRef.el;
        if (!canvas) return;
        if (typeof Chart === "undefined") return;

        const { labels, plan, actual, forecast } = this.state.chartData;
        if (!labels || !labels.length) return;

        if (this._chart) {
            this._chart.destroy();
            this._chart = null;
        }

        const ctx = canvas.getContext("2d");

        this._chart = new Chart(ctx, {
            type: "line",
            data: {
                labels,
                datasets: [
                    {
                        label: this.env._t("Rencana (Plan)"),
                        data:  plan,
                        borderColor:     "#185FA5",
                        backgroundColor: "rgba(24,95,165,0.08)",
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4,
                        pointRadius: 3,
                        pointHoverRadius: 5,
                        pointBackgroundColor: "#185FA5",
                        spanGaps: true,
                    },
                    {
                        label: this.env._t("Realisasi (Actual)"),
                        data:  actual,
                        borderColor:     "#0F6E56",
                        backgroundColor: "rgba(15,110,86,0.08)",
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4,
                        pointRadius: 4,
                        pointHoverRadius: 6,
                        pointBackgroundColor: "#0F6E56",
                        spanGaps: false,
                    },
                    {
                        label: this.env._t("Proyeksi (Forecast)"),
                        data:  forecast,
                        borderColor: "#BA7517",
                        borderDash:  [5, 4],
                        borderWidth: 1.5,
                        fill: false,
                        tension: 0.4,
                        pointRadius: 2,
                        pointHoverRadius: 4,
                        pointBackgroundColor: "#BA7517",
                        spanGaps: false,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: "index", intersect: false },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) =>
                                ctx.dataset.label + ": " +
                                (ctx.parsed.y !== null && ctx.parsed.y !== undefined
                                    ? ctx.parsed.y.toFixed(2) + "%"
                                    : "—"),
                        },
                    },
                },
                scales: {
                    x: {
                        grid:  { color: "rgba(128,128,128,0.1)", lineWidth: 0.5 },
                        ticks: { font: { size: 11 }, color: "#888" },
                    },
                    y: {
                        min: 0,
                        max: 100,
                        grid:  { color: "rgba(128,128,128,0.1)", lineWidth: 0.5 },
                        ticks: {
                            font:     { size: 11 },
                            color:    "#888",
                            callback: (v) => v + "%",
                            stepSize: 20,
                        },
                        title: {
                            display: true,
                            text:    this.env._t("Cumulative Weight (%)"),
                            font:    { size: 11 },
                            color:   "#888",
                        },
                    },
                },
            },
        });
    }

    // -----------------------------------------------------------------------
    // UI event handlers
    // -----------------------------------------------------------------------

    async setPhase(phaseId) {
        this.state.activePhaseId = phaseId;
        await this._loadData(phaseId);
    }

    toggleInfo() {
        this.state.infoExpanded = !this.state.infoExpanded;
    }

    // -----------------------------------------------------------------------
    // Computed display helpers
    // -----------------------------------------------------------------------

    get deviationClass() {
        const d = this.state.kpis.deviation;
        if (d === undefined || d === null) return "";
        if (d > 0)   return "scurve-value--success";
        if (d > -5)  return "scurve-value--success";
        if (d > -15) return "scurve-value--warning";
        return "scurve-value--danger";
    }

    get forecastClass() {
        const w = this.state.kpis.forecast_additional_weeks;
        if (!w || w <= 0) return "scurve-value--success";
        if (w <= 3)       return "scurve-value--warning";
        return "scurve-value--danger";
    }

    get forecastText() {
        const w = this.state.kpis.forecast_additional_weeks;
        if (!w || w <= 0) return this.env._t("On time");
        return `+${w} ${this.env._t("week")}${w > 1 ? "s" : ""}`;
    }

    get hasData() {
        return (
            !this.state.loading &&
            !this.state.error &&
            this.state.chartData.labels &&
            this.state.chartData.labels.length > 0
        );
    }

    statusBadgeClass(status) {
        return `scurve-badge scurve-badge--${status || "on_track"}`;
    }

    statusIcon(status) {
        const icons = {
            ahead:    "✅",
            on_track: "✅",
            late:     "⚠️",
            critical: "🔴",
        };
        return icons[status] || "—";
    }

    formatPct(val) {
        if (val === null || val === undefined) return "—";
        return val.toFixed(2) + "%";
    }
}

const _logger = { error: console.error };

registry.category("actions").add("project_scurve.SCurveDashboard", SCurveDashboard);
