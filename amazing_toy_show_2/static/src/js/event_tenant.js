/** @odoo-module **/
import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.TenantHandover = publicWidget.Widget.extend({
    selector: '.container',
    events: {
        'click .item-row': '_onItemClick',
        'click #btn_complete_handover': '_onCompleteHandover',
    },

    _onItemClick: function (ev) {
        const row = ev.currentTarget;
        const circle = row.querySelector('.check-circle');
        const icon = circle.querySelector('i');
        circle.classList.toggle('checked');

        if (circle.classList.contains('checked')) {
            circle.style.backgroundColor = '#28a745';
            circle.style.borderColor = '#28a745';
            icon.classList.remove('d-none');
        } else {
            circle.style.backgroundColor = 'transparent';
            circle.style.borderColor = '#dee2e6';
            icon.classList.add('d-none');
        }
        this._updateUI();
    },

    _updateUI: function () {
        const itemRows = document.querySelectorAll('.item-row');
        const checked = document.querySelectorAll('.check-circle.checked').length;
        const total = itemRows.length;
        const progress = (checked / total) * 100;
        const progressBar = document.querySelector('.progress-bar');
        if (progressBar) progressBar.style.width = progress + '%';

        const badgeCounter = document.querySelector('.badge');
        if (badgeCounter) badgeCounter.innerText = `${checked} / ${total} ✓`;

        const btnComplete = document.getElementById('btn_complete_handover');
        const msg = document.getElementById('handover_status_msg');

        if (checked === total) {
            btnComplete.disabled = false;
            btnComplete.classList.replace('btn-light', 'btn-danger');
            btnComplete.classList.remove('text-muted');
            if (msg) msg.innerText = "All items checked ✓";
        } else {
            btnComplete.disabled = true;
            btnComplete.classList.replace('btn-danger', 'btn-light');
            btnComplete.classList.add('text-muted');
            if (msg) msg.innerText = "Check all items to unlock";
        }
    },

    _onCompleteHandover: function (ev) {
        const $btn = $(ev.currentTarget);
        $btn.prop('disabled', true);
        const lineIds = Array.from(document.querySelectorAll('.item-row')).map(
            row => parseInt(row.dataset.lineId)
        );

        $.ajax({
            url: '/tenant/order/complete',
            type: 'POST',
            dataType: 'json',
            contentType: 'application/json',
            data: JSON.stringify({
                jsonrpc: "2.0",
                params: {
                    line_ids: lineIds,
                    csrf_token: odoo.csrf_token,
                }
            }),
            success: (response) => {
                const data = response.result;

                if (data && data.status === 'success') {
                    window.location.href = '/tenant/orders?filter=done';
                } else {
                    alert(data ? data.message : "Failed");
                    $btn.prop('disabled', false);
                }
            },
            error: (err) => {
                console.error("AJAX Error:", err);
                alert("Failed connect to server.");
                $btn.prop('disabled', false);
            }
        });
    },
});

publicWidget.registry.TenantScanner = publicWidget.Widget.extend({
    selector: '#wrapwrap',
    events: {},

    init: function () {
        this._super.apply(this, arguments);
        this.html5QrCode = null;
    },

    start: function () {
        const self = this;
        $('#modalScanner').on('shown.bs.modal', function () {
            self._startScanner();
        });

        $('#modalScanner').on('hidden.bs.modal', function () {
            self._stopScanner();
        });
        return this._super.apply(this, arguments);
    },

    _startScanner: async function () {
        this.html5QrCode = new Html5Qrcode("reader");
        try {
            await this.html5QrCode.start(
                { facingMode: "environment" },
                { fps: 10, qrbox: { width: 250, height: 250 } },
                (decodedText) => {
                    this._processScan(decodedText);
                    $('#modalScanner').modal('hide');
                }
            );
        } catch (err) {
            console.error("Camera error:", err);
            alert("Can not access the camera");
        }
    },


    _processScan: async function (barcodeData) {
        try {
            const response = await fetch('/tenant/order/search_by_name', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    jsonrpc: "2.0",
                    params: { name: barcodeData }
                })
            });
            const data = await response.json();
            if (data.result && data.result.status === 'success') {
                window.location.href = data.result.redirect_url;
            } else {
                alert(data.result ? data.result.message : "Order not found");
            }
        } catch (error) {
            console.error("Fetch error:", error);
        }
    },

    _stopScanner: function () {
        if (this.html5QrCode && this.html5QrCode.isScanning) {
            this.html5QrCode.stop().then(() => this.html5QrCode.clear());
        }
    }
});