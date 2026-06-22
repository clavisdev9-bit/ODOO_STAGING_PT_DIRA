# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class AiReportHistory(models.Model):
    """Stores every AI report request with its results and metadata."""

    _name = 'ai.report.history'
    _description = 'AI Report History'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'name'
    _order = 'create_date desc'

    name = fields.Char(
        string='Request',
        compute='_compute_name',
        store=True,
    )
    user_message = fields.Text(
        string='User Message',
        required=True,
    )
    interpreted_intent = fields.Text(
        string='Interpreted Intent (JSON)',
        help='Raw JSON output from the AI interpreter',
    )
    report_type = fields.Selection(
        selection=[
            ('sales', 'Sales'),
            ('invoice', 'Invoice'),
            ('inventory', 'Inventory'),
            ('purchase', 'Purchase'),
            ('summary', 'Summary'),
            ('unknown', 'Unknown'),
        ],
        string='Report Type',
        tracking=True,
    )
    date_from = fields.Date(string='Date From')
    date_to = fields.Date(string='Date To')
    attachment_ids = fields.Many2many(
        comodel_name='ir.attachment',
        relation='ai_report_history_attachment_rel',
        column1='history_id',
        column2='attachment_id',
        string='Output Files',
    )
    status = fields.Selection(
        selection=[
            ('draft', 'Draft'),
            ('processing', 'Processing'),
            ('done', 'Done'),
            ('error', 'Error'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
    )
    error_message = fields.Text(string='Error Details')
    insight_text = fields.Text(
        string='AI Insight',
        help='AI-generated summary of the report results',
    )
    ai_confidence = fields.Float(
        string='AI Confidence',
        digits=(3, 2),
        help='Confidence score returned by the AI (0.0 - 1.0)',
    )
    user_id = fields.Many2one(
        comodel_name='res.users',
        string='Requested By',
        default=lambda self: self.env.user,
        readonly=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Company',
        default=lambda self: self.env.company,
        readonly=True,
    )
    processing_time_ms = fields.Integer(
        string='Processing Time (ms)',
        readonly=True,
    )
    session_id = fields.Char(string='Session ID', index=True)

    @api.depends('user_message')
    def _compute_name(self) -> None:
        for rec in self:
            msg = rec.user_message or ''
            rec.name = msg[:50] + ('...' if len(msg) > 50 else '')

    def action_regenerate(self) -> dict:
        """Re-run the same report request."""
        self.ensure_one()
        try:
            from ..services.report_builder import ReportBuilder
            builder = ReportBuilder(self.env)
            builder.build_from_history(self)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Report Regenerated'),
                    'message': _('Report is being regenerated.'),
                    'type': 'success',
                },
            }
        except Exception as e:
            _logger.exception('Regeneration failed for history %s: %s', self.id, e)
            self.write({'status': 'error', 'error_message': str(e)})
            raise

    def action_download_pdf(self) -> dict:
        """Return action to download the PDF attachment."""
        self.ensure_one()
        pdf_att = self.attachment_ids.filtered(
            lambda a: a.mimetype == 'application/pdf'
        )
        if not pdf_att:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No PDF'),
                    'message': _('No PDF attachment found for this report.'),
                    'type': 'warning',
                },
            }
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{pdf_att[0].id}?download=true',
            'target': 'self',
        }

    def action_download_xlsx(self) -> dict:
        """Return action to download the Excel attachment."""
        self.ensure_one()
        xlsx_att = self.attachment_ids.filtered(
            lambda a: 'spreadsheet' in (a.mimetype or '') or a.name.endswith('.xlsx')
        )
        if not xlsx_att:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Excel'),
                    'message': _('No Excel attachment found for this report.'),
                    'type': 'warning',
                },
            }
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{xlsx_att[0].id}?download=true',
            'target': 'self',
        }

    def action_view_preview_wizard(self) -> dict:
        """Open the report preview wizard for this history record."""
        self.ensure_one()
        wizard = self.env['report.preview.wizard'].create({
            'history_id': self.id,
            'user_message': self.user_message,
            'interpreted_intent': self.interpreted_intent,
            'insight_text': self.insight_text,
        })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'report.preview.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
        }
