from odoo import api, fields, models


class QcCorrectiveAction(models.Model):
    _name = 'qc.corrective.action'
    _description = 'QC Corrective Action'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'

    name = fields.Char(
        string='Reference', readonly=True, default='New', copy=False,
    )
    inspection_id = fields.Many2one(
        'qc.inspection', string='QC Inspection', index=True, ondelete='cascade',
    )
    ncr_id = fields.Many2one(
        'qc.ncr', string='NCR', index=True, ondelete='set null',
    )
    project_id = fields.Many2one(
        related='inspection_id.project_id', store=True, string='Project',
    )
    description = fields.Text(string='What Needs To Be Fixed', required=True)
    action_taken = fields.Text(string='Action Taken')
    pic_id = fields.Many2one(
        'res.users', string='Person In Charge', tracking=True,
    )
    target_date = fields.Date(string='Target Completion', tracking=True)
    completion_date = fields.Date(string='Actual Completion')
    status = fields.Selection([
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('verified', 'Verified'),
    ], string='Status', default='open', tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('qc.corrective.action') or 'New'
                )
        return super().create(vals_list)
