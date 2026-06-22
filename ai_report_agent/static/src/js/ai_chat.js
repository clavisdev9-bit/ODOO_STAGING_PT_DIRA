/** @odoo-module **/

import { Component, useState, useRef, onPatched } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

const QUICK_PROMPTS = [
    "Laporan penjualan bulan ini",
    "Faktur belum dibayar bulan ini",
    "Stok menipis semua gudang",
    "Ringkasan bisnis bulan lalu",
    "Purchase order minggu ini",
    "10 produk terlaris kuartal ini",
];

export class AiChatAction extends Component {
    static template = "ai_report_agent.AiChatAction";
    static props = ["*"];

    setup() {
        this.notification = useService("notification");
        this.inputRef = useRef("chatInput");
        this.scrollRef = useRef("chatScroll");

        this.quickPrompts = QUICK_PROMPTS;

        this.state = useState({
            messages: [],     // { role: "user"|"ai", text, result, error, loading }
            input: "",
            loading: false,
            formatPdf: true,
            formatXlsx: true,
        });

        onPatched(() => this._scrollToBottom());
    }

    _scrollToBottom() {
        const el = this.scrollRef.el;
        if (el) el.scrollTop = el.scrollHeight;
    }

    setPrompt(prompt) {
        this.state.input = prompt;
        if (this.inputRef.el) this.inputRef.el.focus();
    }

    onKeydown(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.sendMessage();
        }
    }

    _getFormats() {
        const f = [];
        if (this.state.formatPdf) f.push("pdf");
        if (this.state.formatXlsx) f.push("xlsx");
        return f.length ? f : ["pdf"];
    }

    async sendMessage() {
        const text = this.state.input.trim();
        if (!text || this.state.loading) return;

        this.state.messages.push({ role: "user", text });
        this.state.input = "";
        this.state.loading = true;

        const aiMsg = { role: "ai", text: "", result: null, error: null, loading: true };
        this.state.messages.push(aiMsg);

        try {
            const response = await rpc("/ai/report", {
                message: text,
                session_id: `chat_${Date.now()}`,
                output_formats: this._getFormats(),
            });

            aiMsg.loading = false;

            if (response.status === "ok") {
                aiMsg.result = response;
                aiMsg.text = response.insight || "Laporan berhasil dibuat.";
                if (response.needs_clarification && response.clarification_question) {
                    aiMsg.clarification = response.clarification_question;
                }
            } else if (response.status === "queued") {
                aiMsg.result = response;
                aiMsg.text = "Dataset besar — laporan sedang diproses di background. Anda akan mendapat notifikasi saat selesai.";
                aiMsg.queued = true;
            } else {
                aiMsg.error = response.error || "Terjadi kesalahan.";
                aiMsg.text = aiMsg.error;
            }
        } catch (err) {
            aiMsg.loading = false;
            aiMsg.error = err.message || "Gagal menghubungi layanan AI.";
            aiMsg.text = aiMsg.error;
        } finally {
            this.state.loading = false;
        }
    }
}

registry.category("actions").add("ai_report_agent.ai_chat_action", AiChatAction);
