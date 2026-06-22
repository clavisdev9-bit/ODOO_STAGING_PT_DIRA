from odoo import models, fields, api


class MstItemCategory(models.Model):
    _name = 'x.mst.item.category'
    _description = 'Master Item Category'
    _order = 'no_urut asc'

    name = fields.Char(string='Item Category', required=True)
    no_urut = fields.Char(string='No. Urut', size=2, readonly=True, copy=False)
    prefix = fields.Char(string='Prefix', size=10, required=True)
    categ_id = fields.Many2one(
        'product.category',
        string='Category',
        required=True,
        ondelete='restrict',
    )
    is_active = fields.Boolean(string='Aktif', default=True)
    sub_category_ids = fields.One2many(
        'x.mst.sub.category', 'item_category_id',
        string='Sub Categories',
    )

    _sql_constraints = [
        ('no_urut_categ_unique', 'UNIQUE(no_urut, categ_id)',
         'No. Urut dalam Category yang sama harus unik!'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('no_urut'):
                categ_id = vals.get('categ_id')
                last = self.search([('categ_id', '=', categ_id)], order='no_urut desc', limit=1)
                try:
                    next_num = int(last.no_urut) + 1 if last and last.no_urut else 1
                except ValueError:
                    next_num = self.search_count([('categ_id', '=', categ_id)]) + 1
                vals['no_urut'] = str(next_num).zfill(2)
        return super().create(vals_list)

