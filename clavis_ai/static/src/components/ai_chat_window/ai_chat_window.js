/** @odoo-module **/

import { Component, useState, useRef, onMounted, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";
import { formatMonetary } from "@web/views/fields/formatters";

const TOOLS = [
    { icon: "📥", name: "get_customer_info", desc: "Fetch partner data from Odoo" },
    { icon: "📝", name: "request_create_sale_order", desc: "Draft a new quotation" },
    { icon: "📋", name: "get_sale_orders", desc: "List orders by state" },
    { icon: "🔍", name: "search_products", desc: "Query product catalog" },
    { icon: "✏️", name: "update_partner", desc: "Modify partner record" },
];

const TABS = [
    { id: "chat", label: "Chat" },
    { id: "dashboard", label: "Dashboard" },
    { id: "logs", label: "Audit Logs" },
];

export class ClavisAIChatAction extends Component {
    static template = "clavis_ai.ClavisAIChatAction";
    static props = ["*"];

    setup() {
        this.notification = useService("notification");
        this.chatAreaRef = useRef("chatArea");
        this.inputRef = useRef("chatInput");

        const storedSession = this._getOrCreateSession();

        this.state = useState({
            messages: [],
            inputText: "",
            isTyping: false,
            sessionId: storedSession,
            activeContext: [],
            panelMode: "metrics",
            activeTab: "chat",
            metrics: {
                open_orders: 0,
                customers: 0,
                revenue_mtd: 0,
                ai_requests: 0,
            },
            auditLogs: [],
            tools: TOOLS,
        });

        this._pollTimer = null;

        onMounted(async () => {
            await this._loadHistory();
            await this._loadMetrics();
            await this._loadAuditLogs();
            this._scrollToBottom();
        });

        onWillUnmount(() => {
            if (this._pollTimer) {
                clearTimeout(this._pollTimer);
            }
        });
    }

    // ── Session ────────────────────────────────────────────────────────────

    _getOrCreateSession() {
        const key = `clavis_ai_session_${odoo.session_info?.uid || "anon"}`;
        let sid = sessionStorage.getItem(key);
        if (!sid) {
            sid = `sess_${Math.random().toString(36).substr(2, 8)}`;
            sessionStorage.setItem(key, sid);
        }
        return sid;
    }

    // ── Tab & Panel Switching ─────────────────────────────────────────────

    switchTab(tabId) {
        this.state.activeTab = tabId;
    }

    switchPanel(mode) {
        this.state.panelMode = mode;
        if (mode === "metrics") {
            this._loadMetrics();
        } else if (mode === "log") {
            this._loadAuditLogs();
        }
    }

    // ── Context Injection ─────────────────────────────────────────────────

    injectContext(ctx) {
        if (!this.state.activeContext.includes(ctx)) {
            this.state.activeContext = [...this.state.activeContext, ctx];
        }
    }

    // ── Messaging ─────────────────────────────────────────────────────────

    async sendMessage() {
        const text = this.state.inputText.trim();
        if (!text || this.state.isTyping) return;

        this.state.inputText = "";
        this.state.messages = [
            ...this.state.messages,
            { id: null, role: "user", text },
        ];
        this.state.isTyping = true;
        this._scrollToBottom();

        const contextPayload = {};
        for (const ctx of this.state.activeContext) {
            contextPayload[ctx] = true;
        }

        try {
            const res = await rpc("/clavis/chat/send", {
                message: text,
                session_id: this.state.sessionId,
                context: contextPayload,
            });
            this._pollForResult(res.request_id);
        } catch (e) {
            this.state.isTyping = false;
            this._appendAiMessage({
                status: "error",
                response: `Connection error: ${e.message || "unknown"}`,
                tool_called: null,
                action_required: false,
                action_details: null,
            });
        }
    }

    _pollForResult(requestId, attempt = 0) {
        if (attempt > 60) {
            this.state.isTyping = false;
            this._appendAiMessage({
                id: requestId,
                status: "error",
                response: "Request timed out. The AI service may be busy.",
                tool_called: null,
                action_required: false,
                action_details: null,
            });
            return;
        }
        this._pollTimer = setTimeout(async () => {
            try {
                const data = await rpc(`/clavis/chat/status/${requestId}`, {});
                if (data.status === "pending") {
                    this._pollForResult(requestId, attempt + 1);
                } else {
                    this.state.isTyping = false;
                    this._appendAiMessage({ id: requestId, ...data });
                    this._loadAuditLogs();
                    this._loadMetrics();
                }
            } catch (e) {
                this.state.isTyping = false;
                this._appendAiMessage({
                    status: "error",
                    response: `Polling error: ${e.message || "unknown"}`,
                });
            }
        }, 1500);
    }

    _appendAiMessage(data) {
        const card = this._buildCard(data);
        this.state.messages = [
            ...this.state.messages,
            {
                id: data.id || null,
                role: "ai",
                text: data.response || data.error_message || "No response received.",
                tool: data.tool_called || null,
                card,
                status: data.status,
                logId: data.id || null,
            },
        ];
        this._scrollToBottom();
    }

    _buildCard(data) {
        if (!data.action_details) return null;
        const d = data.action_details;
        const displayEntries = Object.entries(d.display || {});
        return {
            type: d.type || (data.action_required ? "action" : "info"),
            displayEntries,
            items: d.items || [],
            logId: data.id,
            actionRequired: data.action_required,
        };
    }

    async _loadHistory() {
        try {
            const history = await rpc("/clavis/chat/history", {
                session_id: this.state.sessionId,
            });
            const msgs = [];
            for (const entry of history) {
                msgs.push({ id: null, role: "user", text: entry.message });
                if (entry.response) {
                    const card = this._buildCard(entry);
                    msgs.push({
                        id: entry.id,
                        role: "ai",
                        text: entry.response,
                        tool: entry.tool_called || null,
                        card,
                        status: entry.status,
                        logId: entry.id,
                    });
                }
            }
            this.state.messages = msgs;
        } catch (e) {
            // History loading is best-effort; don't block the UI
        }
    }

    // ── Action Confirmation ───────────────────────────────────────────────

    async confirmAction(logId) {
        try {
            const res = await rpc("/clavis/action/confirm", { log_id: logId });
            if (res.success) {
                const name = res.result?.name || "record";
                this._appendAiMessage({
                    status: "done",
                    response: `✓ **${name}** created successfully in Odoo.`,
                    tool_called: null,
                    action_required: false,
                    action_details: null,
                });
                // Disable card on the original message
                this._disableCard(logId);
            } else {
                this.notification.add(res.message || "Action failed.", { type: "danger" });
            }
        } catch (e) {
            this.notification.add(`Error: ${e.message}`, { type: "danger" });
        }
    }

    cancelAction(logId) {
        this._disableCard(logId);
    }

    _disableCard(logId) {
        this.state.messages = this.state.messages.map((m) => {
            if (m.logId === logId && m.card) {
                return { ...m, card: { ...m.card, actionRequired: false, disabled: true } };
            }
            return m;
        });
    }

    // ── Metrics & Logs ────────────────────────────────────────────────────

    async _loadMetrics() {
        try {
            const m = await rpc("/clavis/metrics", {});
            this.state.metrics = m;
        } catch (e) {
            // Best-effort
        }
    }

    async _loadAuditLogs() {
        try {
            const logs = await rpc("/clavis/recent_logs", { limit: 10 });
            this.state.auditLogs = logs;
        } catch (e) {
            // Best-effort
        }
    }

    // ── Helpers ───────────────────────────────────────────────────────────

    formatRevenue(amount) {
        if (!amount) return "$0";
        if (amount >= 1000) return `$${(amount / 1000).toFixed(1)}k`;
        return `$${amount.toFixed(0)}`;
    }

    _scrollToBottom() {
        // Use a microtask so the DOM has updated
        Promise.resolve().then(() => {
            const el = this.chatAreaRef.el;
            if (el) el.scrollTop = el.scrollHeight;
        });
    }

    onKeydown(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.sendMessage();
        }
    }

    renderMarkdown(text) {
        if (!text) return "";
        return text
            .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
            .replace(/\*(.*?)\*/g, "<em>$1</em>")
            .replace(/\n/g, "<br/>");
    }

    get tabs() {
        return TABS;
    }

    get shortSessionId() {
        return this.state.sessionId.replace("sess_", "");
    }
}

registry.category("actions").add("clavis_ai.chat_client_action", ClavisAIChatAction);
