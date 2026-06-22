from odoo import models, fields


class ProductCategoryExt(models.Model):
    _inherit = 'product.category'

    x_no_urut = fields.Char(string='No. Urut', size=2)
    x_prefix = fields.Char(string='Prefix', size=10)
