import json
import logging

from odoo import http, fields
from odoo.http import request

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Endpoint: /api/attendance/push
#
# Mesin absensi mengirim data ke URL ini (HTTP POST, JSON body).
#
# Header yang diperlukan:
#   X-Device-Code : kode unik mesin (wajib)
#   X-Api-Key     : api_key device atau global_api_key (wajib)
#
# Body JSON:
# {
#   "attendances": [
#     {"uid": "101", "timestamp": "2025-01-15 08:03:22"},
#     {"uid": "102", "timestamp": "2025-01-15 08:10:45"},
#     ...
#   ]
# }
#
# Response berhasil (200):
# {
#   "status": "success",
#   "sync_id": 42,
#   "summary": "10 data diproses, 0 dilewati, 0 error"
# }
# ---------------------------------------------------------------------------


class HrAttendanceMiddlewareController(http.Controller):

    @http.route(
        '/api/attendance/push',
        type='json',
        auth='none',
        methods=['POST'],
        csrf=False,
        save_session=False,
    )
    def push_attendance(self, **kwargs):
        """Endpoint utama penerima data push dari mesin absensi."""
        env = request.env(user=1)  # sudo via uid=1

        # Cek apakah API aktif
        api_enabled = env['ir.config_parameter'].sudo().get_param(
            'hr_attendance_middleware.enable_api', 'True'
        )
        if api_enabled.lower() not in ('true', '1', 'yes'):
            return self._error(403, 'API endpoint nonaktif.')

        # Ambil header autentikasi
        device_code = request.httprequest.headers.get('X-Device-Code', '').strip()
        api_key = request.httprequest.headers.get('X-Api-Key', '').strip()

        if not device_code:
            return self._error(400, 'Header X-Device-Code wajib diisi.')
        if not api_key:
            return self._error(400, 'Header X-Api-Key wajib diisi.')

        # Cari device
        device = env['hr.attendance.device'].sudo().search(
            [('code', '=', device_code), ('state', '=', 'active')], limit=1
        )
        if not device:
            _logger.warning('Push API: device tidak ditemukan atau tidak aktif: %s', device_code)
            return self._error(404, f'Device dengan kode "{device_code}" tidak ditemukan atau tidak aktif.')

        # Validasi API key (device key atau global key)
        global_key = env['ir.config_parameter'].sudo().get_param(
            'hr_attendance_middleware.global_api_key', ''
        )
        valid_keys = list(filter(None, [device.api_key, global_key]))
        if api_key not in valid_keys:
            _logger.warning('Push API: API key tidak valid untuk device %s', device_code)
            return self._error(401, 'API key tidak valid.')

        # Ambil payload
        payload = request.get_json_data() or {}
        attendances = payload.get('attendances', [])
        if not isinstance(attendances, list):
            return self._error(400, 'Field "attendances" harus berupa array.')
        if not attendances:
            return {'status': 'success', 'sync_id': None, 'summary': 'Tidak ada data untuk diproses.'}

        # Buat history record
        history = env['hr.attendance.sync.history'].sudo().create({
            'device_id': device.id,
            'sync_type': 'push',
            'state': 'running',
            'started_at': fields.Datetime.now(),
            'triggered_by': False,
        })

        try:
            result = device.sudo()._process_attendance_data(attendances, history)
            device.sudo()._finalize_sync(history, result)

            return {
                'status': 'success',
                'sync_id': history.id,
                'summary': (
                    f"Total: {result['total_raw']} | "
                    f"Diproses: {result['processed']} | "
                    f"Dilewati: {result['skipped']} | "
                    f"Error: {len(result.get('errors', []))}"
                ),
            }

        except Exception as e:
            _logger.exception('Push API: error saat memproses data device %s', device_code)
            device.sudo()._fail_sync(history, str(e))
            return self._error(500, f'Error internal: {e}')

    # -----------------------------------------------------------------------
    # Endpoint: /api/attendance/status
    # Cek status device (GET request, autentikasi sama)
    # -----------------------------------------------------------------------
    @http.route(
        '/api/attendance/status',
        type='http',
        auth='none',
        methods=['GET'],
        csrf=False,
        save_session=False,
    )
    def device_status(self, **kwargs):
        """Cek status dan statistik device. Gunakan header X-Device-Code & X-Api-Key."""
        env = request.env(user=1)

        device_code = request.httprequest.headers.get('X-Device-Code', '').strip()
        api_key = request.httprequest.headers.get('X-Api-Key', '').strip()

        device = env['hr.attendance.device'].sudo().search(
            [('code', '=', device_code)], limit=1
        )
        if not device:
            return request.make_json_response({'error': 'Device tidak ditemukan.'}, status=404)

        global_key = env['ir.config_parameter'].sudo().get_param(
            'hr_attendance_middleware.global_api_key', ''
        )
        if api_key not in filter(None, [device.api_key, global_key]):
            return request.make_json_response({'error': 'API key tidak valid.'}, status=401)

        last_sync = device.last_sync.strftime('%Y-%m-%d %H:%M:%S') if device.last_sync else None

        return request.make_json_response({
            'status': 'ok',
            'device': {
                'name': device.name,
                'code': device.code,
                'state': device.state,
                'protocol': device.protocol,
                'timezone': device.timezone,
                'last_sync': last_sync,
                'last_sync_status': device.last_sync_status,
                'total_records_synced': device.total_records_synced,
            }
        })

    # -----------------------------------------------------------------------
    # Endpoint: /api/attendance/ping  (health check tanpa autentikasi)
    # -----------------------------------------------------------------------
    @http.route(
        '/api/attendance/ping',
        type='http',
        auth='none',
        methods=['GET'],
        csrf=False,
        save_session=False,
    )
    def ping(self, **kwargs):
        """Health check endpoint sederhana."""
        return request.make_json_response({
            'status': 'ok',
            'service': 'HR-Attendance Middleware',
            'version': '18.0.1.0.0',
        })

    @staticmethod
    def _error(code, message):
        return {'status': 'error', 'code': code, 'message': message}
