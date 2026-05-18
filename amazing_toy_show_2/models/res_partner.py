from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    age = fields.Integer(string='Age')
    gender = fields.Selection([
        ('male', 'Male'),
        ('female', 'Female'),
        ('other', 'Prefer not to say'),
    ])

    _sql_constraints = [
        ('phone_unique', 'unique(phone)', 'Phone sudah terdaftar'),
        ('email_unique', 'unique(email)', 'Email sudah terdaftar'),
    ]