from odoo import api, fields, models


class QcNcr(models.Model):
    _name = 'qc.ncr'
    _description = 'Non Conformance Report'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'

    name = fields.Char(
        string='NCR Reference', readonly=True, default='New', copy=False,
    )
    inspection_id = fields.Many2one(
        'qc.inspection', string='QC Inspection', index=True, ondelete='cascade',
    )
    project_id = fields.Many2one(
        related='inspection_id.project_id', store=True, string='Project',
    )
    description = fields.Text(string='Non Conformance Description', required=True)
    root_cause = fields.Text(string='Root Cause Analysis')
    corrective_action_ids = fields.One2many(
        'qc.corrective.action', 'ncr_id', string='Corrective Actions',
    )
    ca_count = fields.Integer(compute='_compute_ca_count', string='CAs')
    status = fields.Selection([
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('closed', 'Closed'),
    ], string='Status', default='open', tracking=True)
    raised_by = fields.Many2one(
        'res.users', string='Raised By',
        default=lambda self: self.env.user,
    )
    raised_date = fields.Date(string='Raised Date', default=fields.Date.today)

    def _compute_ca_count(self):
        for rec in self:
            rec.ca_count = len(rec.corrective_action_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('qc.ncr') or 'New'
                )
        return super().create(vals_list)
