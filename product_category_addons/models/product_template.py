from odoo import models, fields, api

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    brand_id = fields.Many2one('brand', string='Brand')
    item_category_id = fields.Many2one('item.category', string='Item Category')
    sub_category_id = fields.Many2one('sub.category', string='Sub Category')

    @api.model
    def create(self, vals):
        if not vals.get('default_code'):
            categ = self.env['product.category'].browse(vals.get('categ_id'))
            item = self.env['item.category'].browse(vals.get('item_category_id'))
            sub = self.env['sub.category'].browse(vals.get('sub_category_id'))

            prefix = "%s%s%s" % (
                (categ.code or '').zfill(2),
                (item.code or '').zfill(2),
                (sub.code or '').zfill(3)
            )

            last_product = self.search(
                [('default_code', 'like', prefix + '%')],
                order='default_code desc',
                limit=1
            )

            if last_product:
                last_seq = int(last_product.default_code[-4:])
                seq = str(last_seq + 1).zfill(4)
            else:
                seq = '0001'

            vals['default_code'] = prefix + seq

        return super().create(vals)

    _sql_constraints = [
        ('default_code_unique', 'unique(default_code)', 'Internal Reference must be unique!')
    ]