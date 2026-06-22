import logging
import json
from datetime import datetime, timedelta

import pytz
from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class AttendanceDevice(models.Model):
    """Model untuk manajemen mesin absensi yang terhubung ke Odoo."""
    _name = 'hr.attendance.device'
    _description = 'Mesin Absensi'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name asc'

    name = fields.Char(
        string='Nama Mesin', required=True, tracking=True,
        help='Nama identifikasi mesin absensi, contoh: Mesin Lobby Lantai 1'
    )
    code = fields.Char(
        string='Kode Mesin', required=True, copy=False, tracking=True,
        help='Kode unik mesin. Digunakan sebagai identifier di API.'
    )
    device_type = fields.Selection([
        ('zkteco', 'ZKTeco / Fingerprint'),
        ('rfid', 'RFID Card Reader'),
        ('face', 'Face Recognition'),
        ('http_push', 'HTTP Push (Generic)'),
        ('manual', 'Manual / CSV Import'),
    ], string='Tipe Mesin', default='zkteco', required=True, tracking=True)

    protocol = fields.Selection([
        ('push', 'Push (Mesin → Odoo)'),
        ('pull', 'Pull (Odoo → Mesin)'),
    ], string='Protokol Sync', default='push', required=True, tracking=True,
        help='Push: mesin mengirim data ke Odoo.\nPull: Odoo mengambil data dari mesin secara berkala.'
    )

    # Koneksi untuk mode Pull (ZKTeco)
    ip_address = fields.Char(string='Alamat IP', tracking=True)
    port = fields.Integer(string='Port', default=4370, tracking=True)
    timeout = fields.Integer(string='Timeout (detik)', default=10)
    password = fields.Char(string='Password Mesin', default='0')

    # Lokasi & Zona Waktu
    location_id = fields.Many2one(
        'hr.work.location', string='Lokasi Kerja',
        help='Lokasi kerja yang terkait dengan mesin ini.'
    )
    timezone = fields.Selection(
        [(tz, tz) for tz in sorted(pytz.all_timezones)],
        string='Timezone Mesin', default='Asia/Jakarta', required=True,
        help='Timezone yang digunakan mesin saat mencatat waktu absensi.'
    )

    # Status & Monitoring
    state = fields.Selection([
        ('draft', 'Belum Aktif'),
        ('active', 'Aktif'),
        ('error', 'Error'),
        ('inactive', 'Nonaktif'),
    ], string='Status', default='draft', tracking=True)

    last_sync = fields.Datetime(string='Sinkronisasi Terakhir', readonly=True)
    last_sync_status = fields.Selection([
        ('success', 'Berhasil'),
        ('error', 'Gagal'),
        ('partial', 'Sebagian'),
    ], string='Status Sync Terakhir', readonly=True)
    last_sync_message = fields.Text(string='Pesan Sync Terakhir', readonly=True)

    # API Key untuk mode Push
    api_key = fields.Char(
        string='API Key', copy=False,
        help='Kunci API unik untuk device ini. Digunakan untuk autentikasi saat mesin push data.'
    )

    # Statistik
    raw_log_count = fields.Integer(
        string='Total Log', compute='_compute_counts', store=False
    )
    sync_history_count = fields.Integer(
        string='Riwayat Sync', compute='_compute_counts', store=False
    )
    total_records_synced = fields.Integer(
        string='Total Record Tersync', default=0
    )

    # Opsi lanjutan
    auto_create_employee = fields.Boolean(
        string='Auto Buat Karyawan', default=False,
        help='Otomatis membuat karyawan baru jika ID tidak ditemukan di Odoo.'
    )
    ignore_duplicate = fields.Boolean(
        string='Abaikan Duplikat', default=True,
        help='Abaikan data absensi yang sudah ada untuk rentang waktu yang sama.'
    )
    min_time_diff = fields.Integer(
        string='Jeda Minimal (menit)', default=5,
        help='Jeda minimum antar scan untuk dianggap sebagai event berbeda.'
    )

    # Notifikasi
    notify_on_error = fields.Boolean(string='Notifikasi saat Error', default=True)
    notify_user_ids = fields.Many2many(
        'res.users', string='Kirim Notifikasi Ke',
        help='Pengguna yang akan menerima notifikasi jika terjadi error sync.'
    )

    _sql_constraints = [
        ('code_uniq', 'UNIQUE(code)', 'Kode mesin harus unik!'),
    ]

    @api.depends('raw_log_count', 'sync_history_count')
    def _compute_counts(self):
        for rec in self:
            rec.raw_log_count = self.env['hr.attendance.raw.log'].search_count(
                [('device_id', '=', rec.id)]
            )
            rec.sync_history_count = self.env['hr.attendance.sync.history'].search_count(
                [('device_id', '=', rec.id)]
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('api_key'):
                vals['api_key'] = self._generate_api_key()
        return super().create(vals_list)

    def _generate_api_key(self):
        import secrets
        return secrets.token_urlsafe(32)

    def action_regenerate_api_key(self):
        self.ensure_one()
        self.api_key = self._generate_api_key()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'API Key Diperbarui',
                'message': f'API Key baru: {self.api_key}',
                'type': 'success',
                'sticky': True,
            }
        }

    def action_activate(self):
        self.write({'state': 'active'})

    def action_deactivate(self):
        self.write({'state': 'inactive'})

    def action_test_connection(self):
        """Test koneksi ke mesin (mode Pull/ZKTeco)."""
        self.ensure_one()
        if self.protocol != 'pull':
            raise UserError('Test koneksi hanya untuk mode Pull (ZKTeco).')
        if not self.ip_address:
            raise UserError('Alamat IP wajib diisi untuk test koneksi.')

        try:
            from zk import ZK
            zk = ZK(self.ip_address, port=self.port, timeout=self.timeout,
                    password=int(self.password or 0), force_udp=False, ommit_ping=False)
            conn = zk.connect()
            if conn:
                conn.disconnect()
                self.state = 'active'
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Koneksi Berhasil',
                        'message': f'Berhasil terhubung ke mesin {self.name} ({self.ip_address}:{self.port})',
                        'type': 'success',
                    }
                }
        except ImportError:
            raise UserError(
                'Library pyzk belum terinstall.\n'
                'Jalankan: pip install pyzk'
            )
        except Exception as e:
            self.state = 'error'
            raise UserError(f'Gagal terhubung ke mesin: {e}')

    def action_manual_sync(self):
        """Buka wizard sync manual."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Sync Manual - {self.name}',
            'res_model': 'hr.attendance.sync.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_device_id': self.id},
        }

    def action_view_raw_logs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Log Raw - {self.name}',
            'res_model': 'hr.attendance.raw.log',
            'view_mode': 'list,form',
            'domain': [('device_id', '=', self.id)],
        }

    def action_view_sync_history(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Riwayat Sync - {self.name}',
            'res_model': 'hr.attendance.sync.history',
            'view_mode': 'list,form',
            'domain': [('device_id', '=', self.id)],
        }

    def pull_and_sync(self):
        """Ambil data dari mesin ZKTeco dan proses ke hr.attendance."""
        self.ensure_one()
        if self.protocol != 'pull':
            return
        if not self.ip_address:
            _logger.warning('Device %s tidak memiliki IP address', self.name)
            return

        history = self.env['hr.attendance.sync.history'].create({
            'device_id': self.id,
            'sync_type': 'auto',
            'state': 'running',
            'started_at': fields.Datetime.now(),
        })

        try:
            from zk import ZK
            zk = ZK(self.ip_address, port=self.port, timeout=self.timeout,
                    password=int(self.password or 0), force_udp=False, ommit_ping=False)
            conn = zk.connect()
            attendances_raw = conn.get_attendance()
            conn.disconnect()

            raw_data = []
            for att in attendances_raw:
                raw_data.append({
                    'uid': str(att.user_id),
                    'timestamp': att.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                })

            result = self._process_attendance_data(raw_data, history)
            self._finalize_sync(history, result)

        except ImportError:
            msg = 'Library pyzk tidak terinstall. Jalankan: pip install pyzk'
            self._fail_sync(history, msg)
        except Exception as e:
            self._fail_sync(history, str(e))

    def _process_attendance_data(self, raw_data, history):
        """Proses list attendance data mentah menjadi record hr.attendance."""
        from collections import defaultdict
        from datetime import datetime, time as dt_time

        source_tz = pytz.timezone(self.timezone)
        utc_tz = pytz.utc

        def to_utc(ts_str):
            try:
                naive = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
                return source_tz.localize(naive).astimezone(utc_tz).replace(tzinfo=None)
            except ValueError:
                return None

        daily_scans = defaultdict(list)
        raw_log_vals = []
        skipped = 0

        for item in raw_data:
            uid = str(item.get('uid', ''))
            ts_str = item.get('timestamp', '')
            utc_dt = to_utc(ts_str)

            raw_log_vals.append({
                'device_id': self.id,
                'sync_history_id': history.id,
                'employee_uid': uid,
                'raw_timestamp': ts_str,
                'timestamp_utc': utc_dt,
                'state': 'pending',
            })

            if not utc_dt:
                skipped += 1
                continue

            employee = self.env['hr.employee'].search([('barcode', '=', uid)], limit=1)
            if not employee and self.auto_create_employee:
                employee = self.env['hr.employee'].create({'name': f'Karyawan {uid}', 'barcode': uid})
            if not employee:
                skipped += 1
                continue

            date_key = (employee.id, utc_dt.date())
            daily_scans[date_key].append(utc_dt)

        if raw_log_vals:
            self.env['hr.attendance.raw.log'].create(raw_log_vals)

        processed = 0
        errors = []
        min_diff = timedelta(minutes=self.min_time_diff)

        for (employee_id, scan_date), scans in daily_scans.items():
            try:
                scans.sort()
                # Kelompokkan scan dengan jeda minimum
                groups = []
                current_group = [scans[0]]
                for s in scans[1:]:
                    if s - current_group[-1] >= min_diff:
                        groups.append(current_group)
                        current_group = [s]
                    else:
                        current_group.append(s)
                groups.append(current_group)

                check_in = groups[0][0]
                check_out = groups[-1][-1] if len(groups) > 1 or len(groups[0]) > 1 else None

                domain = [
                    ('employee_id', '=', employee_id),
                    ('check_in', '>=', datetime.combine(scan_date, dt_time.min)),
                    ('check_in', '<=', datetime.combine(scan_date, dt_time.max)),
                ]
                existing = self.env['hr.attendance'].search(domain, limit=1)

                if existing:
                    if self.ignore_duplicate:
                        processed += 1
                        continue
                    vals = {}
                    if check_in < existing.check_in:
                        vals['check_in'] = check_in
                    if check_out and (not existing.check_out or check_out > existing.check_out):
                        vals['check_out'] = check_out
                    if vals:
                        existing.write(vals)
                else:
                    self.env['hr.attendance'].create({
                        'employee_id': employee_id,
                        'check_in': check_in,
                        'check_out': check_out,
                    })
                processed += 1
            except Exception as e:
                errors.append(str(e))
                _logger.exception('Error saat memproses absensi employee_id=%s date=%s', employee_id, scan_date)

        self.total_records_synced += processed
        return {
            'total_raw': len(raw_data),
            'processed': processed,
            'skipped': skipped,
            'errors': errors,
        }

    def _finalize_sync(self, history, result):
        errors = result.get('errors', [])
        state = 'success' if not errors else 'partial' if result['processed'] > 0 else 'error'
        message = (
            f"Total raw: {result['total_raw']} | "
            f"Diproses: {result['processed']} | "
            f"Dilewati: {result['skipped']} | "
            f"Error: {len(errors)}"
        )
        history.write({
            'state': state,
            'finished_at': fields.Datetime.now(),
            'total_raw': result['total_raw'],
            'total_processed': result['processed'],
            'total_skipped': result['skipped'],
            'error_log': '\n'.join(errors) if errors else False,
            'summary': message,
        })
        self.write({
            'last_sync': fields.Datetime.now(),
            'last_sync_status': state,
            'last_sync_message': message,
        })
        if state in ('error', 'partial') and self.notify_on_error:
            self._send_error_notification(message)

    def _fail_sync(self, history, message):
        history.write({
            'state': 'error',
            'finished_at': fields.Datetime.now(),
            'error_log': message,
            'summary': f'GAGAL: {message}',
        })
        self.write({
            'state': 'error',
            'last_sync': fields.Datetime.now(),
            'last_sync_status': 'error',
            'last_sync_message': message,
        })
        _logger.error('Sync gagal untuk device %s: %s', self.name, message)
        if self.notify_on_error:
            self._send_error_notification(message)

    def _send_error_notification(self, message):
        if not self.notify_user_ids:
            return
        self.message_post(
            body=f'<b>Error Sinkronisasi Mesin Absensi</b><br/>'
                 f'Device: {self.name}<br/>'
                 f'Waktu: {fields.Datetime.now()}<br/>'
                 f'Pesan: {message}',
            partner_ids=self.notify_user_ids.mapped('partner_id').ids,
            message_type='comment',
            subtype_xmlid='mail.mt_comment',
        )

    @api.model
    def cron_auto_sync_all(self):
        """Dipanggil oleh cron job untuk sync semua device aktif mode Pull."""
        devices = self.search([('state', '=', 'active'), ('protocol', '=', 'pull')])
        _logger.info('Cron auto-sync: memproses %d device', len(devices))
        for device in devices:
            try:
                device.pull_and_sync()
            except Exception as e:
                _logger.exception('Cron sync gagal untuk device %s: %s', device.name, e)
