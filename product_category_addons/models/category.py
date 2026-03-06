from odoo import models, fields

class ItemCategory(models.Model):
    _name = 'item.category'
    _rec_name = 'name'

    name = fields.Char('Name')
    code = fields.Char('Code')

class SubCategory(models.Model):
    _name = 'sub.category'
    _rec_name = 'name'

    name = fields.Char('Name')
    code = fields.Char('Code')