from odoo import models, fields, api

class DiraDivision(models.Model):
    _name = 'dira.division'
    _description = 'Master Data Division'

    code = fields.Char(string='Division Code', required=True, copy=False, default='New')
    name = fields.Char(string='Division Name', required=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Gagal! Division Code sudah dipakai.'),
        ('name_unique', 'unique(name)', 'Gagal! Nama Division sudah terdaftar.')
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Ngecek apakah kotak 'code' isinya masih tulisan 'New'
            if vals.get('code', 'New') == 'New':
                # Tarik nomor antrean dari sequence.xml
                vals['code'] = self.env['ir.sequence'].next_by_code('dira.division.sequence') or 'New'
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('code'):
            vals['code'] = str(vals['code']).strip().zfill(3)
        return super().write(vals)
    
class DiraItemCategory(models.Model):
    _name = 'dira.item.category'
    _description = 'Master Data Item Category'

    code = fields.Char(string='Item Category Code', required=True, copy=False, default='New')
    name = fields.Char(string='Item Category Name', required=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Gagal! Item Category Code sudah dipakai.'),
        ('name_unique', 'unique(name)', 'Gagal! Nama Item Category sudah terdaftar.')
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Ngecek apakah kotak 'code' isinya masih tulisan 'New'
            if vals.get('code', 'New') == 'New':
                # Tarik nomor antrean dari sequence.xml
                vals['code'] = self.env['ir.sequence'].next_by_code('dira.item.category.sequence') or 'New'
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('code'):
            vals['code'] = str(vals['code']).strip().zfill(3)
        return super().write(vals)

class DiraSubCategory(models.Model):
    _name = 'dira.sub.category'
    _description = 'Master Data Sub Category'

    code = fields.Char(string='Sub Category Code', required=True, copy=False, default='New')
    name = fields.Char(string='Sub Category Name', required=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Gagal! Sub Category Code sudah dipakai.'),
        ('name_unique', 'unique(name)', 'Gagal! Nama Sub Category sudah terdaftar.')
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Ngecek apakah kotak 'code' isinya masih tulisan 'New'
            if vals.get('code', 'New') == 'New':
                # Tarik nomor antrean dari sequence.xml
                vals['code'] = self.env['ir.sequence'].next_by_code('dira.sub.category.sequence') or 'New'
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('code'):
            vals['code'] = str(vals['code']).strip().zfill(3)
        return super().write(vals)
    
class DiraBrand(models.Model):
    _name = 'dira.brand'
    _description = 'Master Data Brand'

    code = fields.Char(string='Brand Code', required=True, copy=False, default='New')
    name = fields.Char(string='Brand Name', required=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Gagal! Brand Code sudah dipakai.'),
        ('name_unique', 'unique(name)', 'Gagal! Nama Brand sudah terdaftar.')
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Ngecek apakah kotak 'code' isinya masih tulisan 'New'
            if vals.get('code', 'New') == 'New':
                # Tarik nomor antrean dari sequence.xml
                vals['code'] = self.env['ir.sequence'].next_by_code('dira.brand.sequence') or 'New'
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('code'):
            # Format otomatis jadi 3 digit pas diedit
            vals['code'] = str(vals['code']).strip().zfill(3)
        return super().write(vals)


class DiraSpecification(models.Model):
    _name = 'dira.specification'
    _description = 'Master Data Specification'

    code = fields.Char(string='Spec Code', required=True, copy=False, default='New')
    name = fields.Char(string='Spec Name', required=True)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Gagal! Spec Code sudah dipakai.'),
        ('name_unique', 'unique(name)', 'Gagal! Nama Specification sudah terdaftar.')
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # Ngecek apakah kotak 'code' isinya masih tulisan 'New'
            if vals.get('code', 'New') == 'New':
                # Tarik nomor antrean dari sequence.xml
                vals['code'] = self.env['ir.sequence'].next_by_code('dira.specification.sequence') or 'New'
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('code'):
            vals['code'] = str(vals['code']).strip().zfill(3)
        return super().write(vals)
