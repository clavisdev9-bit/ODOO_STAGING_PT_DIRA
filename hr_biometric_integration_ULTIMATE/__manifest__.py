{
    'name': 'HR Biometric Integration (Ultimate VPS)',
    'summary': 'Professional biometric integration with UI settings and menus.',
    'author': 'Dimas Aryo Novantri',
    'category': 'Human Resources/Attendances',
    'depends': [
        'hr_attendance',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/biometric_menus.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}
