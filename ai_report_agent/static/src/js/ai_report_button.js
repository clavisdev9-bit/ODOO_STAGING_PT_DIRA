/** @odoo-module **/

import { Component, useState, useRef, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

const QUICK_PROMPTS = [
    "Unpaid invoices this month",
    "Top 10 best-selling products this quarter",
    "Low stock alerts",
    "Business summary last month",
    "Overdue invoices",
    "Purchase orders this week",
];

// ============================================================
// AIReportPanel — the main interactive panel component
// ============================================================

export class AIReportPanel extends Component {
    static template = "ai_report_agent.AIReportPanel";
    static props = {
        onClose: { type: Function, optional: true },
    };

    setup() {
        this.notification = useService("notification");
        this.messageInput = useRef("messageInput");

        this.quickPrompts = QUICK_PROMPTS;

        this.state = useState({
            message: "",
            loading: false,
            formatPdf: true,
            formatXlsx: true,
            result: null,
            error: null,
            clarification: null,
            queued: false,
        });

        onMounted(() => {
            if (this.messageInput.el) {
                this.messageInput.el.focus();
            }
        });
    }

    /**
     * Set a quick-prompt text into the message input.
     * @param {string} prompt
     */
    setPrompt(prompt) {
        this.state.message = prompt;
        if (this.messageInput.el) {
            this.messageInput.el.focus();
        }
    }

    /**
     * Handle Ctrl+Enter to submit.
     * @param {KeyboardEvent} ev
     */
    onKeydown(ev) {
        if (ev.ctrlKey && ev.key === "Enter") {
            this.generateReport();
        }
    }

    /**
     * Build selected output formats list.
     * @returns {string[]}
     */
    _getOutputFormats() {
        const formats = [];
        if (this.state.formatPdf) formats.push("pdf");
        if (this.state.formatXlsx) formats.push("xlsx");
        return formats.length ? formats : ["pdf"];
    }

    /**
     * Call POST /ai/report and update state with result.
     */
    async generateReport() {
        const message = this.state.message.trim();
        if (!message) return;

        // Reset state
        this.state.loading = true;
        this.state.result = null;
        this.state.error = null;
        this.state.clarification = null;
        this.state.queued = false;

        try {
            const sessionId = `discuss_${Date.now()}`;
            const response = await rpc("/ai/report", {
                message,
                session_id: sessionId,
                output_formats: this._getOutputFormats(),
            });

            if (response.status === "ok") {
                this.state.result = response;
                if (response.needs_clarification && response.clarification_question) {
                    this.state.clarification = response.clarification_question;
                }
                this.notification.add("Report generated successfully!", {
                    type: "success",
                    sticky: false,
                });
            } else if (response.status === "queued") {
                this.state.queued = true;
                this.state.result = response;
                this.notification.add(
                    "Large dataset — report is being processed in the background.",
                    { type: "info", sticky: false }
                );
            } else {
                this.state.error = response.error || "An unexpected error occurred.";
            }
        } catch (err) {
            console.error("AI Report error:", err);
            this.state.error =
                err.message || "Failed to connect to the AI Report service.";
        } finally {
            this.state.loading = false;
        }
    }
}

// ============================================================
// AIReportButton — toggle button injected into Discuss bar
// ============================================================

export class AIReportButton extends Component {
    static template = "ai_report_agent.AIReportButton";
    static props = {};
    static components = { AIReportPanel };

    setup() {
        this.state = useState({ panelOpen: false });
    }

    togglePanel() {
        this.state.panelOpen = !this.state.panelOpen;
    }
}

// ============================================================
// Register in the discuss action bar (Odoo 18 OWL 2 pattern)
// ============================================================

registry.category("discuss.action_panel_buttons").add("ai_report_button", {
    Component: AIReportButton,
    props: {},
    sequence: 100,
});

// ============================================================
// Standalone widget for embedding the panel in Discuss thread
// ============================================================

export class AIReportThreadWidget extends Component {
    static template = "ai_report_agent.AIReportPanel";
    static components = {};

    setup() {
        this.notification = useService("notification");
        this.messageInput = useRef("messageInput");

        this.quickPrompts = QUICK_PROMPTS;

        this.state = useState({
            message: "",
            loading: false,
            formatPdf: true,
            formatXlsx: true,
            result: null,
            error: null,
            clarification: null,
            queued: false,
        });
    }

    setPrompt(prompt) {
        this.state.message = prompt;
    }

    onKeydown(ev) {
        if (ev.ctrlKey && ev.key === "Enter") {
            this.generateReport();
        }
    }

    _getOutputFormats() {
        const formats = [];
        if (this.state.formatPdf) formats.push("pdf");
        if (this.state.formatXlsx) formats.push("xlsx");
        return formats.length ? formats : ["pdf"];
    }

    async generateReport() {
        const message = this.state.message.trim();
        if (!message) return;

        this.state.loading = true;
        this.state.result = null;
        this.state.error = null;
        this.state.clarification = null;
        this.state.queued = false;

        try {
            const response = await rpc("/ai/report", {
                message,
                session_id: `thread_${Date.now()}`,
                output_formats: this._getOutputFormats(),
            });

            if (response.status === "ok") {
                this.state.result = response;
                if (response.needs_clarification && response.clarification_question) {
                    this.state.clarification = response.clarification_question;
                }
            } else if (response.status === "queued") {
                this.state.queued = true;
                this.state.result = response;
            } else {
                this.state.error = response.error || "An unexpected error occurred.";
            }
        } catch (err) {
            this.state.error = err.message || "Connection failed.";
        } finally {
            this.state.loading = false;
        }
    }
}

registry.category("view_widgets").add("ai_report_panel", {
    component: AIReportThreadWidget,
});
