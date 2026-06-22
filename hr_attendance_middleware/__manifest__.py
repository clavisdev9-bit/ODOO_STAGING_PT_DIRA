{
    'name': 'HR-Attendance',
    'version': '18.0.1.0.0',
    'summary': 'Middleware penghubung mesin absensi (fingerprint/RFID/ZKTeco) dengan Odoo 18',
    'description': """
HR-Attendance Middleware
========================
Modul middleware profesional untuk menghubungkan mesin absensi biometrik
(ZKTeco, fingerprint, RFID, face recognition) dengan sistem HR Odoo 18.

Fitur Utama:
- Manajemen multi-device absensi
- REST API endpoint (Push mode) untuk menerima data dari mesin
- Scheduler otomatis untuk sinkronisasi berkala
- Log raw data dari mesin absensi
- Riwayat sinkronisasi dengan detail error
- Wizard sync manual per device
- Dashboard statistik kehadiran
- Konfigurasi timezone per device
- Dukungan protokol ZKTeco (via pyzk) & HTTP Push
    """,
    'author': 'Clavis Development',
    'website': 'https://github.com/clavisdev9-bit',
    'category': 'Human Resources/Attendances',
    'license': 'LGPL-3',
    'depends': [
        'hr_attendance',
        'mail',
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/cron_data.xml',
        'views/attendance_device_views.xml',
        'views/attendance_raw_log_views.xml',
        'views/attendance_sync_history_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
        'wizard/sync_attendance_wizard_views.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
}
