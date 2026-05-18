from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class EventCashier(models.Model):
    _name = 'event.cashier'
    _description = 'Event Cashier'

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    pin = fields.Char(required=True)
    is_active = fields.Boolean(default=True)

    _sql_constraints = [
        ('pin_unique', 'unique(pin)', 'PIN sudah digunakan oleh kasir lain! Silakan gunakan PIN unik.'),
        ('code_unique', 'unique(code)', 'Kode Kasir sudah terdaftar!'),
    ]

    @api.constrains('pin')
    def _check_pin_format(self):
        for record in self:
            if not record.pin.isdigit():
                raise ValidationError(_("PIN harus berupa angka saja!"))

            if len(record.pin) < 4 or len(record.pin) > 6:
                raise ValidationError(_("PIN harus terdiri dari 4 sampai 6 digit angka."))