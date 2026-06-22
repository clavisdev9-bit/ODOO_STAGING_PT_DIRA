from odoo import fields, models


class QcAttachment(models.Model):
    _name = 'qc.attachment'
    _description = 'QC Photo Evidence'
    _order = 'attachment_type, id'

    inspection_id = fields.Many2one(
        'qc.inspection', required=True, ondelete='cascade', index=True,
    )
    attachment_type = fields.Selection([
        ('before', 'Before Work'),
        ('during', 'During Work'),
        ('after', 'After Work'),
        ('drawing', 'Drawing / Schematic'),
        ('other', 'Other'),
    ], string='Type', required=True, default='after')
    file = fields.Binary(string='File', required=True, attachment=True)
    filename = fields.Char(string='Filename')
    description = fields.Char(string='Description')
