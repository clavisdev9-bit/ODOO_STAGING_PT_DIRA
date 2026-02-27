from odoo import models, fields, api

class DiraBrand(models.Model):
    _name = 'dira.brand'
    _description = 'Master Data Brand'

    code = fields.Char(string='Brand Code', required=True)
    name = fields.Char(string='Brand Name', required=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Gagal! Brand Code sudah dipakai.'),
        ('name_unique', 'unique(name)', 'Gagal! Nama Brand sudah terdaftar.')
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code'):
                # Format otomatis jadi 3 digit pas create
                vals['code'] = str(vals['code']).strip().zfill(3)
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('code'):
            # Format otomatis jadi 3 digit pas diedit
            vals['code'] = str(vals['code']).strip().zfill(3)
        return super().write(vals)


class DiraSubCategory(models.Model):
    _name = 'dira.sub.category'
    _description = 'Master Data Sub Category'

    code = fields.Char(string='Sub Category Code', required=True)
    name = fields.Char(string='Sub Category Name', required=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Gagal! Sub Category Code sudah dipakai.'),
        ('name_unique', 'unique(name)', 'Gagal! Nama Sub Category sudah terdaftar.')
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code'):
                vals['code'] = str(vals['code']).strip().zfill(3)
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('code'):
            vals['code'] = str(vals['code']).strip().zfill(3)
        return super().write(vals)


class DiraSpesifikasi(models.Model):
    _name = 'dira.spesifikasi'
    _description = 'Master Data Spesifikasi'

    code = fields.Char(string='Spec Code', required=True)
    name = fields.Char(string='Spec Name', required=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Gagal! Spec Code sudah dipakai.'),
        ('name_unique', 'unique(name)', 'Gagal! Nama Spesifikasi sudah terdaftar.')
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code'):
                vals['code'] = str(vals['code']).strip().zfill(3)
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('code'):
            vals['code'] = str(vals['code']).strip().zfill(3)
        return super().write(vals)
    
class DiraDivision(models.Model):
    _name = 'dira.division'
    _description = 'Master Data Division'

    code = fields.Char(string='Division Code', required=True)
    name = fields.Char(string='Division Name', required=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Gagal! Division Code sudah dipakai.'),
        ('name_unique', 'unique(name)', 'Gagal! Nama Division sudah terdaftar.')
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('code'):
                vals['code'] = str(vals['code']).strip().zfill(3)
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('code'):
            vals['code'] = str(vals['code']).strip().zfill(3)
        return super().write(vals)