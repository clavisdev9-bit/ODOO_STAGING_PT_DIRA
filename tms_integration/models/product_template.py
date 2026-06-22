from odoo import models, fields


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # Packaging dimensions used by TMS for 3D capacity planning
    tms_pkg_length = fields.Float('Package Length (cm)', digits=(7, 2))
    tms_pkg_width = fields.Float('Package Width (cm)', digits=(7, 2))
    tms_pkg_height = fields.Float('Package Height (cm)', digits=(7, 2))


class ProductProduct(models.Model):
    _inherit = 'product.product'

    # Proxy fields for direct access from move lines
    tms_pkg_length = fields.Float(related='product_tmpl_id.tms_pkg_length', string='Package Length (cm)', store=True)
    tms_pkg_width = fields.Float(related='product_tmpl_id.tms_pkg_width', string='Package Width (cm)', store=True)
    tms_pkg_height = fields.Float(related='product_tmpl_id.tms_pkg_height', string='Package Height (cm)', store=True)
