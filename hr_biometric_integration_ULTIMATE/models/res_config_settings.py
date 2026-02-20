from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    biometric_secret_key = fields.Char(
        string='Biometric Secret Key',
        config_parameter='biometric_sync.secret_key',
        help="Kunci rahasia ini digunakan untuk mengamankan endpoint API."
    )
    
    show_biometric_menu = fields.Boolean(
        string="Show Biometric Menu",
        config_parameter='hr_biometric_integration_ULTIMATE.show_biometric_menu',
        help="Jika dicentang, menu Biometric akan muncul di dalam aplikasi Attendances."
    )

