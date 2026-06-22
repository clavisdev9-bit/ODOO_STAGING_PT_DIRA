from odoo import models, fields


class ClavisAiLog(models.Model):
    _name = 'clavis.ai.log'
    _description = 'Clavis AI Request Log'
    _order = 'create_date desc'
    _rec_name = 'session_id'

    session_id = fields.Char('Session ID', required=True, index=True)
    user_id = fields.Many2one(
        'res.users', 'User', required=True,
        default=lambda self: self.env.user,
        ondelete='restrict',
    )
    message = fields.Text('User Message', required=True)
    response = fields.Text('AI Response')
    status = fields.Selection([
        ('pending', 'Pending'),
        ('done', 'Done'),
        ('error', 'Error'),
    ], string='Status', default='pending', required=True, index=True)
    action_required = fields.Boolean('Action Required', default=False)
    action_details = fields.Json('Action Details')
    tool_called = fields.Char('Tool Called')
    latency_ms = fields.Integer('Latency (ms)')
    error_message = fields.Text('Error Message')
    context_data = fields.Json('Context Data')
