from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    dira_brand_id = fields.Many2one(
        'dira.brand', 
        string='Brand'
    )
    dira_item_category_id = fields.Many2one(
        'dira.item.category',
        string='Item Category'
    )
    dira_sub_category_id = fields.Many2one(
        'dira.sub.category', 
        string='Sub Category'
    )
    dira_specification_id = fields.Many2one(
        'dira.specification', 
        string='Specification'
    )
    dira_division_id = fields.Many2one(
        'dira.division', 
        string='Division'
    )