import logging
import datetime

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

_API_KEY_PARAM = 'sos.api.key'

# Daftar kode error integrasi SOS-Odoo
SOS_ERROR_CODES = {
    'SOS-E001': 'API key belum dikonfigurasi. Atur parameter sistem "sos.api.key".',
    'SOS-E002': 'Model sale.order tidak dapat diakses. Periksa hak akses user atau modul sale_stock.',
    'SOS-E003': 'Tidak ada warehouse yang terkonfigurasi untuk perusahaan ini.',
    'SOS-E004': 'Model product.product tidak dapat diakses. Pastikan modul stock terinstall.',
    'SOS-E005': 'Admin user (base.user_admin) tidak ditemukan atau tidak dapat diakses.',
    'SOS-E006': 'Error tidak terduga. Lihat log server (odoo.log) untuk detail teknis.',
    'SOS-OK':   'Semua komponen integrasi berfungsi normal.',
}


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sos_api_key = fields.Char(
        string='SOS API Key',
        config_parameter=_API_KEY_PARAM,
        help='API key yang digunakan SOS app untuk autentikasi ke Odoo (header X-SOS-API-KEY).',
    )
    sos_last_test_result = fields.Char(
        string='Hasil Test Terakhir',
        config_parameter='sos.last_test_result',
        readonly=True,
    )
    sos_last_test_date = fields.Char(
        string='Tanggal Test',
        config_parameter='sos.last_test_date',
        readonly=True,
    )

    # ------------------------------------------------------------------ #
    #  Core: logika test integrasi                                        #
    # ------------------------------------------------------------------ #

    def _sos_test_integration(self):
        """
        Jalankan health-check integrasi SOS-Odoo secara menyeluruh.

        Memeriksa:
          1. API key terkonfigurasi            → SOS-E001 jika tidak
          2. Admin user dapat diakses          → SOS-E005 jika tidak
          3. Model sale.order dapat diakses    → SOS-E002 jika tidak
          4. Model product.product dapat diakses → SOS-E004 jika tidak
          5. Minimal 1 warehouse tersedia      → SOS-E003 jika tidak

        Return:
            dict { 'success': bool, 'error_code': str, 'message': str }
        """
        env = self.env

        # --- SOS-E001: API key ---
        api_key = env['ir.config_parameter'].sudo().get_param(_API_KEY_PARAM)
        if not api_key:
            return self._sos_build_result(False, 'SOS-E001')

        # --- SOS-E005: Admin user ---
        try:
            admin_user = env.ref('base.user_admin')
            if not admin_user.exists():
                return self._sos_build_result(False, 'SOS-E005')
        except Exception as exc:
            _logger.exception('[SOS] Admin user check failed: %s', exc)
            return self._sos_build_result(False, 'SOS-E005')

        # --- SOS-E002: sale.order ---
        try:
            env['sale.order'].sudo().search_count([('id', '=', 0)])
        except Exception as exc:
            _logger.exception('[SOS] sale.order access check failed: %s', exc)
            return self._sos_build_result(False, 'SOS-E002')

        # --- SOS-E004: product.product ---
        try:
            env['product.product'].sudo().search_count([('id', '=', 0)])
        except Exception as exc:
            _logger.exception('[SOS] product.product access check failed: %s', exc)
            return self._sos_build_result(False, 'SOS-E004')

        # --- SOS-E003: warehouse ---
        try:
            wh_count = env['stock.warehouse'].sudo().search_count(
                [('company_id', '=', env.company.id)]
            )
            if not wh_count:
                return self._sos_build_result(False, 'SOS-E003')
        except Exception as exc:
            _logger.exception('[SOS] Warehouse check failed: %s', exc)
            return self._sos_build_result(False, 'SOS-E003')

        return self._sos_build_result(True, 'SOS-OK')

    def _sos_build_result(self, success, code):
        """Bangun dict hasil test dan simpan ke ir.config_parameter."""
        message = SOS_ERROR_CODES.get(code, 'Kode error tidak dikenal.')
        now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        param = self.env['ir.config_parameter'].sudo()
        param.set_param('sos.last_test_result', f'[{code}] {message}')
        param.set_param('sos.last_test_date', now_str)

        _logger.info('[SOS Integration] Test result: %s – %s', code, message)
        return {'success': success, 'error_code': code, 'message': message}

    # ------------------------------------------------------------------ #
    #  Tombol: Test Koneksi (standalone, tanpa simpan)                   #
    # ------------------------------------------------------------------ #

    def action_sos_test_connection(self):
        """Tombol 'Test Koneksi' – cek integrasi tanpa menyimpan perubahan."""
        result = self._sos_test_integration()
        notif_type = 'success' if result['success'] else 'danger'
        title = (
            _('SOS Integrasi: Berhasil ✓')
            if result['success']
            else _('SOS Integrasi: Gagal [%(code)s]', code=result['error_code'])
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': result['message'],
                'type': notif_type,
                'sticky': not result['success'],
            },
        }

    # ------------------------------------------------------------------ #
    #  Override execute(): simpan + auto-test saat klik "Simpan"         #
    # ------------------------------------------------------------------ #

    def execute(self):
        """
        Override standar Odoo settings execute().

        Alur:
          1. Simpan semua settings (super().execute())
          2. Jalankan test integrasi SOS-Odoo
          3. Tampilkan notifikasi hasil (success / warning + kode error)
          4. Lanjutkan ke reload halaman settings (via 'next')
        """
        save_action = super().execute()

        try:
            test = self._sos_test_integration()
        except Exception as exc:
            _logger.exception('[SOS] Unexpected error during integration test: %s', exc)
            test = {
                'success': False,
                'error_code': 'SOS-E006',
                'message': f'{SOS_ERROR_CODES["SOS-E006"]} Detail: {exc}',
            }

        if test['success']:
            notif_type = 'success'
            title = _('SOS Integrasi: Tersimpan & Terverifikasi ✓')
        else:
            notif_type = 'warning'
            title = _('SOS Integrasi: Tersimpan, namun ada masalah [%(code)s]',
                      code=test['error_code'])

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': test['message'],
                'type': notif_type,
                'sticky': not test['success'],
                'next': save_action,
            },
        }
