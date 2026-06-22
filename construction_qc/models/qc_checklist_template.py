from odoo import api, fields, models


class QcChecklistTemplate(models.Model):
    _name = 'qc.checklist.template'
    _description = 'QC Checklist Template'
    _order = 'name'

    name = fields.Char(string='Template Name', required=True)
    work_package_type = fields.Char(
        string='Work Package Type', required=True,
        help='Keyword matched against Work Package field on new inspections.',
    )
    active = fields.Boolean(default=True)
    line_ids = fields.One2many(
        'qc.checklist.template.line', 'template_id', string='Checklist Items',
    )
    line_count = fields.Integer(compute='_compute_line_count', string='Items')

    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec.line_ids)


class QcChecklistTemplateLine(models.Model):
    _name = 'qc.checklist.template.line'
    _description = 'QC Checklist Template Line'
    _order = 'sequence, id'

    template_id = fields.Many2one(
        'qc.checklist.template', required=True, ondelete='cascade', index=True,
    )
    sequence = fields.Integer(default=10)
    item = fields.Char(string='Checklist Item', required=True)
    specification = fields.Char(string='Standard / Specification')
