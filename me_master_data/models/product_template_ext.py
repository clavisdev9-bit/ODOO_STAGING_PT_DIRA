from odoo import models, fields, api


class ProductTemplateExt(models.Model):
    _inherit = 'product.template'

    x_mst_item_category = fields.Many2one(
        'x.mst.item.category',
        string='Item Category',
        domain="[('categ_id', '=', categ_id), ('is_active', '=', True)]",
    )
    x_mst_sub_category = fields.Many2one(
        'x.mst.sub.category',
        string='Sub Category',
        domain="[('item_category_id', '=', x_mst_item_category), ('is_active', '=', True)]",
    )
    x_mst_brand = fields.Many2one(
        'x.mst.brand',
        string='Brand',
        domain="[('is_active', '=', True)]",
    )
    x_nama_tambahan = fields.Char(string='Nama Tambahan / Deskripsi')
    default_code = fields.Char(
        compute='_compute_kode_item',
        store=True,
        copy=False,
        readonly=False,   # allow manual override when needed
    )
    x_kode_item = fields.Char(
        string='Kode Item Internal',
        compute='_compute_kode_item',
        store=True,
        
        readonly=True,
        copy=False,
    )

    _sql_constraints = [
        ('sub_category_brand_name_unique',
         'UNIQUE(x_mst_sub_category, x_mst_brand, name)',
         'Item dengan Sub Category, Brand, dan Nama yang sama sudah ada!'),
    ]

    @api.onchange('categ_id')
    def _onchange_categ_id(self):
        self.x_mst_item_category = False
        self.x_mst_sub_category = False
        self.x_mst_brand = False

    @api.onchange('x_mst_item_category')
    def _onchange_item_category(self):
        self.x_mst_sub_category = False
        self.x_mst_brand = False

    @api.onchange('x_mst_sub_category')
    def _onchange_sub_category(self):
        self.x_mst_brand = False

    @api.depends('x_mst_sub_category', 'x_mst_brand', 'x_nama_tambahan',
                 'x_mst_sub_category.name', 'x_mst_brand.name')
    def _compute_kode_item(self):
        for rec in self:
            if not rec.x_mst_sub_category or not rec.x_mst_brand:
                continue
            sc = rec.x_mst_sub_category
            br = rec.x_mst_brand
            ic = sc.item_category_id
            cat = ic.categ_id

            # name
            base = '{} {}'.format(sc.name, br.name)
            rec.name = '{} {}'.format(base, rec.x_nama_tambahan).strip() \
                if rec.x_nama_tambahan else base

            # running number
            run = rec._get_running_number(sc.id, br.id)

            # default_code
            no_cat = (cat.x_no_urut or '00').zfill(2)
            no_ic = (ic.no_urut or '00').zfill(2)
            no_sc = (sc.no_urut or '00').zfill(2)
            no_brand = rec._get_brand_no_urut(sc, br)
            new_code = '{}-{}-{}-{}-{}'.format(
                no_cat, no_ic, no_sc, no_brand, run
            )
            rec.default_code = new_code

            # x_kode_item
            prefix_cat = (cat.x_prefix or 'XX').upper()
            prefix_ic = (ic.prefix or 'XX').upper()
            prefix_sc = (sc.prefix or 'XX').upper()
            kode_br = (br.kode or 'XXXX').upper()[:4]
            rec.x_kode_item = '{}-{}-{}-{}-{}'.format(
                prefix_cat, prefix_ic, prefix_sc, kode_br, run
            )

            # sync default_code ke semua product.product variant
            if rec.id:
                rec.product_variant_ids.filtered(
                    lambda v: v.default_code != new_code
                ).write({'default_code': new_code})

    def _get_running_number(self, sub_cat_id, brand_id):
        domain = [
            ('x_mst_sub_category', '=', sub_cat_id),
            ('x_mst_brand', '=', brand_id),
        ]
        if self.id:
            domain.append(('id', '!=', self.id))
        count = self.search_count(domain)
        return str(count + 1).zfill(3)

    def _get_brand_no_urut(self, sub_cat, brand):
        mapping = self.env['x.mst.sub.cat.brand'].search([
            ('sub_category_id', '=', sub_cat.id),
            ('brand_id', '=', brand.id),
        ], limit=1)
        return (mapping.no_urut_brand or '00').zfill(2) if mapping else '00'
