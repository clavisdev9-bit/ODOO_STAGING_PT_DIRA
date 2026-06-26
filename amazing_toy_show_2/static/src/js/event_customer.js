/** @odoo-module **/

const formatIDR = (amount) => {
    return new Intl.NumberFormat('id-ID').format(amount);
};

// product_detail_page
(function() {
    const setupProductDetail = () => {
        const btnMinus = document.getElementById('btn-minus');
        const btnPlus = document.getElementById('btn-plus');
        const qtyInput = document.getElementById('qty-input');
        const addBtn = document.querySelector('.add-to-cart-btn');
        const cartBadge = document.getElementById('cart-qty');

        if (!btnMinus || !btnPlus || !addBtn) return false;

        btnPlus.onclick = () => {
            const currentQty = parseInt(qtyInput.value);
            const maxStock = parseInt(qtyInput.getAttribute('data-max') || 0);

            if (currentQty < maxStock) {
                qtyInput.value = currentQty + 1;
            } else {
                $('#modalStockAlert').modal('show');
            }
        };

        btnMinus.onclick = () => {
            const val = parseInt(qtyInput.value);
            if (val > 1) qtyInput.value = val - 1;
        };

        // Kirim ke Backend
        addBtn.onclick = async function() {
            const productId = this.getAttribute('data-product-id');
            const qty = parseInt(qtyInput.value);

            try {
                const response = await fetch('/cart/add', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        jsonrpc: "2.0",
                        params: { product_id: productId, qty: qty }
                    })
                });

                const data = await response.json();

                if (data?.result) {
                    if (cartBadge) cartBadge.innerText = data.result.cart_qty;
                    addBtn.innerText = "Added!";
                    addBtn.classList.replace('btn-danger', 'btn-success');
                    setTimeout(() => {
                        addBtn.innerText = "Add to Cart";
                        addBtn.classList.replace('btn-success', 'btn-danger');
                    }, 2000);
                }
            } catch (error) {
                console.error("Failed add to cart", error);
            }
        };
        return true;
    };

    // Polling Odoo DOM
    const checkExist = setInterval(() => {
        if (setupProductDetail()) clearInterval(checkExist);
    }, 500);
})();

// cart_page
$(document).on('click', '.js_update_qty', function() {
    const $btn = $(this);
    const $row = $btn.closest('.cart-item-row');
    const lineId = $row.data('line-id');
    const direction = $btn.data('direction');

    $.ajax({
        url: '/cart/update_qty',
        type: 'POST',
        dataType: 'json',
        contentType: 'application/json',
        data: JSON.stringify({
            jsonrpc: "2.0",
            params: { line_id: lineId, direction: direction }
        }),
        success: (data) => {
            if (!data?.result) return;
            const res = data.result;

            if (res.status === 'success') {
                $row.find('.js_qty_val').text(res.new_qty);
                $row.find('.js_subtotal').text(formatIDR(res.subtotal));
                $('.js_cart_total').text(formatIDR(res.total_amount));
            } else if (res.status === 'limit_reached') {
                $('#modalStockAlert').modal('show');
                $row.find('.js_qty_val').text(res.current_qty);
            } else if (res.status === 'removed') {
                $row.fadeOut(300, ()=> {
                    $row.remove();
                    $('.js_cart_total').text(formatIDR(res.total_amount));
                    if (res.cart_qty === 0) location.reload();
                });
            }
        }
    });
});

$(document).on('click', '.js_delete_line', function() {
    const $row = $(this).closest('.cart-item-row');
    const lineId = $row.data('line-id');

    $.ajax({
        url: '/cart/delete_line',
        type: 'POST',
        dataType: 'json',
        contentType: 'application/json',
        data: JSON.stringify({ jsonrpc: "2.0", params: { line_id: lineId } }),
        success: (data) => {
            if (data?.result?.status === 'success') {
                $row.fadeOut(300, () => {
                    $row.remove();
                    $('.js_cart_total').text(formatIDR(data.result.total_amount));
                    if (data.result.cart_qty === 0) location.reload();
                });
            }
        }
    });
});

$(document).on('click', '.js_btn_checkout', function() {
    const hasUnavailable = $('.badge:contains("Unavailable")').length > 0;
    if (hasUnavailable) {
        $('#modalUnavailableAlert').modal('show');
        return;
    }

    $.ajax({
        url: '/cart/checkout',
        type: 'POST',
        dataType: 'json',
        contentType: 'application/json',
        data: JSON.stringify({ jsonrpc: "2.0", params: {} }),
        success: function(data) {
            const res = data.result;
            if (res.status === 'success') {
                window.location.href = res.redirect;
            } else {
                alert(res.message || "Failed");
                location.reload();
            }
        }
    });
});

// checkout_qr_page
$(document).ready(function() {
    // === 1. LOGIKA SMART BACK (Solusi untuk ReferenceError) ===
    $(document).on('click', '.js_smart_back', function(ev) {
        ev.preventDefault();
        const referrer = document.referrer;

        // Jika datang dari halaman QR/Checkout, arahkan ke tenants
        if (referrer.includes('/checkout/') || referrer.includes('/order/validate/')) {
            window.location.href = '/tenants';
        } else if (referrer === "" || !referrer.includes(window.location.hostname)) {
            window.location.href = '/tenants';
        } else {
            window.history.back();
        }
    });

    // === 2. LOGIKA TIMER (checkout_qr_page) ===
    const timerElement = document.getElementById('txn_timer');
    if (timerElement) {
        const orderId = $('.js_btn_edit_order').data('order-id');
        const STORAGE_KEY = `order_timer_end_${orderId}`;

        let timerEnd = localStorage.getItem(STORAGE_KEY);
        if (!timerEnd) {
            timerEnd = new Date().getTime() + (1 * 60 * 1000);
            localStorage.setItem(STORAGE_KEY, timerEnd);
        }

        const countdown = setInterval(() => {
            const now = new Date().getTime();
            const distance = timerEnd - now;

            if (distance <= 0) {
                clearInterval(countdown);
                localStorage.removeItem(STORAGE_KEY);
                timerElement.innerHTML = "0:00";
                executeAutoCancel(orderId);
            } else {
                const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
                const seconds = Math.floor((distance % (1000 * 60)) / 1000);
                timerElement.innerHTML = `${minutes}:${seconds < 10 ? '0' + seconds : seconds}`;
            }
        }, 1000);
    }

    // === 3. FUNGSI AUTO CANCEL ===
    function executeAutoCancel(orderId) {
        $.ajax({
            url: '/checkout/edit_order',
            type: 'POST',
            dataType: 'json',
            contentType: 'application/json',
            data: JSON.stringify({ jsonrpc: "2.0", params: { order_id: orderId } }),
            success: (data) => {
                $('#modalTimeOutAlert').modal('show');
                $('#btn-timeout-ok').one('click', function() {
                    window.location.href = '/cart';
                });
                $('#modalTimeOutAlert').on('hidden.bs.modal', function () {
                    window.location.href = '/cart';
                });
            }
        });
    }

    // === 4. REFRESH STATUS PEMBAYARAN ===
    /**$(document).on('click', '.js_btn_refresh_status', function() {
        const token = $(this).data('token');
        const $btn = $(this);
        $btn.text('Checking...').prop('disabled', true);

        $.ajax({
            url: `/checkout/check_status/${token}`,
            type: 'POST',
            dataType: 'json',
            contentType: 'application/json',
            data: JSON.stringify({ jsonrpc: "2.0", params: {} }),
            success: (data) => {
                const res = data.result;
                if (res.is_paid) {
                    const orderId = $('.js_btn_edit_order').data('order-id');
                    localStorage.removeItem(`order_timer_end_${orderId}`);
                    window.location.href = `/checkout/paid_success/${token}`;
                } else {
                    alert("Payment pending. Please complete your payment at the cashier.");
                    $btn.text('Refresh Status').prop('disabled', false);
                }
            }
        });
    });**/

    // === 5. EDIT ORDER (MODAL & AJAX) ===
    $(document).on('click', '.js_btn_edit_order', function() {
        $('#modalEditConfirm').modal('show');
    });

    $(document).on('click', '#confirm-edit-yes', function() {
        const orderId = $('.js_btn_edit_order').data('order-id');
        const $btn = $(this);
        $btn.prop('disabled', true).text('Processing...');

        $.ajax({
            url: '/checkout/edit_order',
            type: 'POST',
            dataType: 'json',
            contentType: 'application/json',
            data: JSON.stringify({ jsonrpc: "2.0", params: { order_id: orderId } }),
            success: (data) => {
                if (data?.result?.status === 'success') {
                    localStorage.removeItem(`order_timer_end_${orderId}`);
                    window.location.href = data.result.redirect;
                }
            }
        });
    });

    // === 6. POLLING STATUS PEMBAYARAN (Odoo 18 Fix) ===
    const qrElement = document.getElementById('qrcode');
    if (qrElement) {
        // Ambil token dari URL atau dari data attribute
        const pathArray = window.location.pathname.split('/');
        const token = pathArray[pathArray.length - 1];
        const orderId = $('.js_btn_edit_order').data('order-id');

        const pollInterval = setInterval(function() {
            $.ajax({
                url: `/checkout/check_status/${token}`,
                type: 'POST',
                dataType: 'json',
                contentType: 'application/json',
                data: JSON.stringify({ jsonrpc: "2.0", params: {} }),
                success: function(data) {
                    const res = data.result;

                    if (res && res.is_paid) {
                        // Hentikan polling
                        clearInterval(pollInterval);

                        // Bersihkan timer di localStorage
                        localStorage.removeItem(`order_timer_end_${orderId}`);

                        // Arahkan ke halaman sukses pembayaran
                        window.location.href = `/checkout/paid_success/${token}`;
                    }
                    else if (res && res.state === 'draft') {
                        // Jika order di-cancel atau timeout oleh sistem lain
                        clearInterval(pollInterval);
                        window.location.href = '/cart';
                    }
                },
                error: function() {
                    // Jika error (misal koneksi putus), polling tetap berjalan di cycle berikutnya
                    console.error("Polling failed, retrying...");
                }
            });
        }, 3000); // Cek setiap 3 detik
    }
});

$(document).ready(function() {
    $(document).on('click', '.js_show_barcode', function() {
        $("#modalBarcode").modal('show');
    });
});