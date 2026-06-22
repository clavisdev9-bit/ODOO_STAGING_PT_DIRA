from odoo import fields, models


class QcChecklistLine(models.Model):
    _name = 'qc.checklist.line'
    _description = 'QC Checklist Line'
    _order = 'sequence, id'

    inspection_id = fields.Many2one(
        'qc.inspection', required=True, ondelete='cascade', index=True,
    )
    sequence = fields.Integer(default=10)
    item = fields.Char(string='Checklist Item', required=True)
    specification = fields.Char(string='Standard / Specification')
    actual = fields.Char(string='Actual Result / Measurement')
    result = fields.Selection([
        ('pass', 'Pass'),
        ('fail', 'Fail'),
        ('na', 'N/A'),
    ], string='Result', default='na')
    remark = fields.Char(string='Remark')
