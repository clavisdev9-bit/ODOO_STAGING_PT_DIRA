from odoo import models, fields, api


class MstSubCategory(models.Model):
    _name = 'x.mst.sub.category'
    _description = 'Master Sub Category'
    _order = 'no_urut asc'

    name = fields.Char(string='Sub Category', required=True)
    no_urut = fields.Char(string='No. Urut', size=2, readonly=True, copy=False)
    prefix = fields.Char(string='Prefix', size=10, required=True)
    item_category_id = fields.Many2one(
        'x.mst.item.category',
        string='Item Category',
        required=True,
        ondelete='restrict',
    )
    is_active = fields.Boolean(string='Aktif', default=True)
    brand_line_ids = fields.One2many(
        'x.mst.sub.cat.brand', 'sub_category_id',
        string='Brands',
    )

    _sql_constraints = [
        ('no_urut_item_cat_unique', 'UNIQUE(no_urut, item_category_id)',
         'No. Urut dalam Item Category yang sama harus unik!'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('no_urut'):
                item_cat_id = vals.get('item_category_id')
                last = self.search([('item_category_id', '=', item_cat_id)], order='no_urut desc', limit=1)
                try:
                    next_num = int(last.no_urut) + 1 if last and last.no_urut else 1
                except ValueError:
                    next_num = self.search_count([('item_category_id', '=', item_cat_id)]) + 1
                vals['no_urut'] = str(next_num).zfill(2)
        return super().create(vals_list)


class MstSubCatBrand(models.Model):
    _name = 'x.mst.sub.cat.brand'
    _description = 'Sub Category Brand Mapping'
    _order = 'no_urut_brand asc'

    sub_category_id = fields.Many2one(
        'x.mst.sub.category',
        string='Sub Category',
        required=True,
        ondelete='cascade',
    )
    brand_id = fields.Many2one(
        'x.mst.brand',
        string='Brand',
        required=True,
        ondelete='restrict',
    )
    no_urut_brand = fields.Char(string='No. Urut Brand', size=2, readonly=True, copy=False)

    _sql_constraints = [
        ('sub_cat_brand_unique', 'UNIQUE(sub_category_id, brand_id)',
         'Brand yang sama tidak boleh duplikat dalam Sub Category!'),
        ('no_urut_sub_cat_unique', 'UNIQUE(sub_category_id, no_urut_brand)',
         'No. Urut Brand dalam Sub Category yang sama harus unik!'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('no_urut_brand'):
                sub_cat_id = vals.get('sub_category_id')
                last = self.search([('sub_category_id', '=', sub_cat_id)], order='no_urut_brand desc', limit=1)
                try:
                    next_num = int(last.no_urut_brand) + 1 if last and last.no_urut_brand else 1
                except ValueError:
                    next_num = self.search_count([('sub_category_id', '=', sub_cat_id)]) + 1
                vals['no_urut_brand'] = str(next_num).zfill(2)
        return super().create(vals_list)
