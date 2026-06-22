from odoo import models, fields, api


class MstBrand(models.Model):
    _name = 'x.mst.brand'
    _description = 'Master Brand'
    _order = 'no_urut asc'

    name = fields.Char(string='Brand', required=True)
    no_urut = fields.Char(string='No. Urut', size=2, readonly=True, copy=False)
    kode = fields.Char(string='Kode (4chr)', size=4, required=True)
    negara_asal = fields.Char(string='Negara Asal')
    is_active = fields.Boolean(string='Aktif', default=True)
    sub_cat_brand_ids = fields.One2many(
        'x.mst.sub.cat.brand', 'brand_id',
        string='Sub Category Mappings',
    )

    _sql_constraints = [
        ('kode_unique', 'UNIQUE(kode)', 'Kode brand harus unik!'),
        ('no_urut_unique', 'UNIQUE(no_urut)', 'No. Urut brand harus unik!'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('no_urut'):
                last = self.search([], order='no_urut desc', limit=1)
                try:
                    next_num = int(last.no_urut) + 1 if last and last.no_urut else 1
                except ValueError:
                    next_num = self.search_count([]) + 1
                vals['no_urut'] = str(next_num).zfill(2)
        return super().create(vals_list)
