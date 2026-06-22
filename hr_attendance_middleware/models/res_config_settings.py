from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    attendance_global_api_key = fields.Char(
        string='Global API Key',
        config_parameter='hr_attendance_middleware.global_api_key',
        help='Kunci API global sebagai fallback jika device tidak memiliki API key sendiri.'
    )
    attendance_default_timezone = fields.Selection(
        [('Asia/Jakarta', 'WIB (Asia/Jakarta)'),
         ('Asia/Makassar', 'WITA (Asia/Makassar)'),
         ('Asia/Jayapura', 'WIT (Asia/Jayapura)'),
         ('UTC', 'UTC')],
        string='Timezone Default Mesin',
        config_parameter='hr_attendance_middleware.default_timezone',
        default='Asia/Jakarta',
    )
    attendance_auto_sync_interval = fields.Integer(
        string='Interval Auto-Sync (menit)',
        config_parameter='hr_attendance_middleware.auto_sync_interval',
        default=60,
        help='Interval waktu dalam menit untuk sinkronisasi otomatis (Pull mode).'
    )
    attendance_log_retention_days = fields.Integer(
        string='Retensi Log Raw (hari)',
        config_parameter='hr_attendance_middleware.log_retention_days',
        default=90,
        help='Log raw akan dihapus otomatis setelah melewati jumlah hari ini.'
    )
    attendance_enable_api = fields.Boolean(
        string='Aktifkan REST API',
        config_parameter='hr_attendance_middleware.enable_api',
        default=True,
        help='Aktifkan endpoint REST API untuk menerima data push dari mesin.'
    )
