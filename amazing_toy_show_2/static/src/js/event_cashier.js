/** @odoo-module **/

(function() {
    "use strict";

    // Fungsi utama
    function initCashierScan() {
        const scanInput = document.getElementById('scan_transaction_id');
        if (!scanInput) return; // Jika elemen belum ada, keluar

        // Fokus otomatis
        scanInput.focus();

        function showError(title, message, icon) {
            $("#error_title").text(title);
            $("#error_message").text(message);
            $("#error_icon").text(icon);
            $("#modalScanError").modal('show');
            $("#scan_transaction_id").val('');
            setTimeout(() => $("#scan_transaction_id").focus(), 500);
        }

        async function fetchOrder(searchValue) {
            if (!searchValue) return;
            const cleanValue = searchValue.toUpperCase().trim();

            try {
                const response = await fetch('/cashier/get_order_details', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        jsonrpc: "2.0",
                        params: {
                            search_val: cleanValue
                        }
                    })
                });

                const data = await response.json();

                if (data.result) {
                    const result = data.result;
                    if (result.status === 'success') {
                        window.location.href = '/cashier/review/' + result.order_id;
                    } else if (result.status === 'invalid') {
                        showError('Expired transaction', result.message, '⏰');
                    } else if (result.status === 'paid') {
                        showError('Paid', result.message, '✅');
                    } else {
                        showError('Not Found', result.message, '🔍');
                    }
                }
            } catch (err) {
                console.error("RPC Error:", err);
                showError('System Error', 'Connection failed', '🚫');
            }
        }

        // Listener Enter
        $("#scan_transaction_id").on('keypress', function(e) {
            if (e.which === 13) {
                e.preventDefault();
                fetchOrder($(this).val());
            }
        });

        $("#btn_find_transaction").on('click', function() {
            fetchOrder($("#scan_transaction_id").val());
        });
    }

    // Interval untuk memastikan DOM siap (Odoo 18 fix)
    const checkReady = setInterval(function() {
        if (typeof jQuery !== 'undefined' && document.getElementById('scan_transaction_id')) {
            initCashierScan();
            clearInterval(checkReady);
        }
    }, 100); // Cek setiap 100ms
})();

// validate payment
(function() {
    "use strict";

    function initPaymentLogic() {
        const cashInput = document.getElementById('cash_received');
        const changeDisplay = document.getElementById('change_display');
        const grandTotal = parseFloat(document.getElementById('grand_total').dataset.amount);
        let selectedMethod = 'cash';

        // Fungsi Format & Clean
        function formatRupiah(angka) {
            return angka.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
        }

        function cleanRupiah(string) {
            // Menghapus titik agar kembali menjadi angka murni
            return parseFloat(string.replace(/\./g, '')) || 0;
        }

        // 1. Toggle Method
        $(".method-btn").on('click', function() {
            $(".method-btn").removeClass('active btn-danger text-white').addClass('btn-outline-danger');
            $(this).addClass('active btn-danger text-white').removeClass('btn-outline-danger');

            selectedMethod = $(this).data('method');
            if (selectedMethod === 'qr' || selectedMethod === 'card') {
                $("#cash_input_section").addClass('d-none');
                // Untuk non-cash, set tampilan format dan raw value
                cashInput.value = formatRupiah(grandTotal);
            } else {
                $("#cash_input_section").removeClass('d-none');
                cashInput.value = '';
                changeDisplay.innerText = "Rp 0";
                cashInput.focus();
            }
        });

        // 2. Listener Input dengan Format Rupiah
        cashInput.addEventListener('input', function(e) {
            let value = this.value.replace(/\D/g, ''); // Hanya ambil angka
            this.value = formatRupiah(value); // Tampilkan format titik

            const received = cleanRupiah(this.value);
            const change = Math.round(received - grandTotal);

            if (change >= 0) {
                changeDisplay.innerText = "Rp " + formatRupiah(change);
                changeDisplay.classList.remove('text-danger');
                changeDisplay.classList.add('text-success');
            } else {
                const shortage = Math.abs(change);
                changeDisplay.innerText = "Kurang: Rp " + formatRupiah(shortage);
                changeDisplay.classList.remove('text-success');
                changeDisplay.classList.add('text-danger');
            }
        });

        // Update fungsi formatRupiah agar menangani pembulatan
        function formatRupiah(angka) {
            if (angka === "" || angka === 0) return "0";

            // Pastikan angka bulat (integer) sebelum diformat titik
            let nilaiBulat = Math.floor(Math.abs(angka));
            return nilaiBulat.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
        }

        // 3. Confirm Payment (Perbaikan di bagian ambil nilai)
        $("#btn_confirm_payment").on('click', async function() {
            // PENTING: Gunakan cleanRupiah, jangan parseFloat langsung
            const received = cleanRupiah(cashInput.value);
            const change = received - grandTotal;

            if (received < grandTotal) {
                $("#modalFailed").modal('show');
                return;
            }

            const orderId = window.location.pathname.split('/').pop();

            try {
                const response = await fetch('/cashier/validate_payment', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        jsonrpc: "2.0",
                        params: {
                            order_id: orderId,
                            method: selectedMethod,
                            received: received, // Data yang dikirim sudah angka murni
                            change: change >= 0 ? change : 0
                        }
                    })
                });

                const data = await response.json();
                if (data.result && data.result.status === 'success') {
                    $("#modalSuccess").modal('show');
                    $("#btn_print_receipt").on('click', function() {
                        const orderId = window.location.pathname.split('/').pop();
                        const printUrl = '/cashier/print_receipt/' + orderId;

                        // Buka jendela baru untuk print
                        const printWindow = window.open(printUrl, 'PrintReceipt', 'width=400,height=600');
                        printWindow.onload = function() {
                            printWindow.print();
                            printWindow.onafterprint = function() {
                                printWindow.close();
                            };
                        };
                    });
                } else {
                    alert(data.result.message || "Gagal memproses pembayaran");
                }
            } catch (err) {
                console.error("Payment Error:", err);
            }
        });
    }

    const checkReady = setInterval(function() {
        if (typeof jQuery !== 'undefined' && document.getElementById('cash_received')) {
            initPaymentLogic();
            clearInterval(checkReady);
        }
    }, 100);
})();