from odoo import models, fields

class EventTenant(models.Model):
    _name = 'event.tenant'
    _description = 'Event Tenant'

    name = fields.Char(string='Tenant Name',required=True)
    booth_code = fields.Char(string='Booth Code')
    description = fields.Char(string='Description')
    floor = fields.Selection(selection=[
        ('ug', 'UG'),
        ('gf', 'GF'),
        ('2nd', '2nd Floor')
    ], default='ug', index=True)
    user_ids = fields.Many2many(comodel_name='res.users', string='Tenant Staff')

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    tenant_id = fields.Many2one('event.tenant', string='Tenant')

class ProductProduct(models.Model):
    _inherit = 'product.product'

    tenant_id = fields.Many2one(related='product_tmpl_id.tenant_id', store=True, readonly=False)