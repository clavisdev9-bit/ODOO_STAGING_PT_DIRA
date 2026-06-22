import json
import logging

from odoo import http, SUPERUSER_ID
from odoo.http import request

_logger = logging.getLogger(__name__)

_API_KEY_PARAM = 'sos.api.key'

# Kode error standar integrasi SOS-Odoo
_ERROR_MESSAGES = {
    'SOS-E001': 'API key belum dikonfigurasi. Atur parameter sistem "sos.api.key".',
    'SOS-E002': 'Model sale.order tidak dapat diakses. Periksa hak akses atau modul sale_stock.',
    'SOS-E003': 'Tidak ada warehouse untuk perusahaan ini. Buat minimal 1 warehouse di Inventory.',
    'SOS-E004': 'Model product.product tidak dapat diakses. Pastikan modul stock terinstall.',
    'SOS-E005': 'Admin user (base.user_admin) tidak ditemukan atau tidak dapat diakses.',
    'SOS-E006': 'Error tidak terduga. Lihat log server Odoo untuk detail teknis.',
}


def _ok(message='Integrasi Odoo berhasil. Semua komponen berfungsi normal.'):
    return request.make_json_response({
        'success': True,
        'error_code': 'SOS-OK',
        'message': message,
    })


def _fail(error_code, detail=None):
    message = _ERROR_MESSAGES.get(error_code, 'Kode error tidak dikenal.')
    if detail:
        message = f'{message} ({detail})'
    _logger.warning('[SOS Admin API] Integration test failed: %s – %s', error_code, message)
    return request.make_json_response({
        'success': False,
        'error_code': error_code,
        'message': message,
    }, status=200)   # tetap 200 agar frontend bisa baca body JSON-nya


class SosAdminApiController(http.Controller):

    @http.route(
        '/api/v1/admin/integration/test-odoo',
        type='http',
        auth='none',
        methods=['POST'],
        csrf=False,
        save_session=False,
    )
    def test_odoo_integration(self, **_kwargs):
        """
        POST /api/v1/admin/integration/test-odoo

        Dipanggil oleh halaman admin SOS (menu Integrasi → Integration with Odoo)
        saat klik tombol "Simpan" atau "Test Koneksi".

        Tidak membutuhkan request body.

        Response 200 (selalu 200 agar body JSON terbaca):
            { "success": true,  "error_code": "SOS-OK",   "message": "..." }
            { "success": false, "error_code": "SOS-E001", "message": "..." }

        Urutan pengecekan:
            SOS-E001 → API key
            SOS-E005 → Admin user
            SOS-E002 → Model sale.order
            SOS-E004 → Model product.product
            SOS-E003 → Warehouse tersedia
        """
        # All checks run with SUPERUSER to avoid false-negative ACL failures on an
        # auth='none' endpoint — we are only reading config/schema, not mutating data.
        env = request.env(user=SUPERUSER_ID)

        # --- SOS-E001: API key harus sudah dikonfigurasi ---
        try:
            api_key = env['ir.config_parameter'].get_param(_API_KEY_PARAM)
        except Exception as exc:
            _logger.exception('[SOS Admin API] Failed to read ir.config_parameter: %s', exc)
            return _fail('SOS-E006', str(exc))

        if not api_key:
            return _fail('SOS-E001')

        # --- SOS-E005: Admin user harus bisa diakses ---
        try:
            admin_user = env.ref('base.user_admin')
            if not admin_user.exists():
                return _fail('SOS-E005')
        except Exception as exc:
            _logger.exception('[SOS Admin API] Admin user check failed: %s', exc)
            return _fail('SOS-E005')

        # --- SOS-E002: Model sale.order ---
        try:
            env['sale.order'].search_count([('id', '=', 0)])
        except Exception as exc:
            _logger.exception('[SOS Admin API] sale.order check failed: %s', exc)
            return _fail('SOS-E002')

        # --- SOS-E004: Model product.product ---
        try:
            env['product.product'].search_count([('id', '=', 0)])
        except Exception as exc:
            _logger.exception('[SOS Admin API] product.product check failed: %s', exc)
            return _fail('SOS-E004')

        # --- SOS-E003: Minimal 1 warehouse ---
        try:
            wh_count = env['stock.warehouse'].search_count(
                [('company_id', '=', env.company.id)]
            )
            if not wh_count:
                return _fail('SOS-E003')
        except Exception as exc:
            _logger.exception('[SOS Admin API] Warehouse check failed: %s', exc)
            return _fail('SOS-E003')

        # --- Semua OK ---
        return _ok()
