# -*- coding: utf-8 -*-
"""Report Preview Wizard — allows users to review the interpreted intent before generating."""
import logging
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class ReportPreviewWizard(models.TransientModel):
    """Wizard to preview and confirm a report before generation."""

    _name = 'report.preview.wizard'
    _description = 'Report Preview Wizard'

    history_id = fields.Many2one(
        comodel_name='ai.report.history',
        string='History Record',
    )
    user_message = fields.Text(
        string='Your Request',
        readonly=True,
    )
    interpreted_intent = fields.Text(
        string='AI Interpretation (JSON)',
        readonly=True,
    )
    insight_text = fields.Text(
        string='AI Insight',
        readonly=True,
    )
    report_type = fields.Selection(
        selection=[
            ('sales', 'Sales'),
            ('invoice', 'Invoice'),
            ('inventory', 'Inventory'),
            ('purchase', 'Purchase'),
            ('summary', 'Summary'),
        ],
        string='Report Type',
    )
    date_from = fields.Date(string='Date From')
    date_to = fields.Date(string='Date To')
    output_format_pdf = fields.Boolean(string='Generate PDF', default=True)
    output_format_xlsx = fields.Boolean(string='Generate Excel', default=True)
    state = fields.Selection(
        selection=[('preview', 'Preview'), ('done', 'Done')],
        default='preview',
        string='State',
    )
    download_url_pdf = fields.Char(string='PDF Download URL', readonly=True)
    download_url_xlsx = fields.Char(string='Excel Download URL', readonly=True)

    @api.model
    def default_get(self, fields_list: list) -> dict:
        res = super().default_get(fields_list)
        if self.env.context.get('default_history_id'):
            history = self.env['ai.report.history'].browse(
                self.env.context['default_history_id']
            )
            if history:
                res.update({
                    'report_type': history.report_type,
                    'date_from': history.date_from,
                    'date_to': history.date_to,
                })
        return res

    def action_generate(self) -> dict:
        """Generate the report with current settings."""
        self.ensure_one()
        output_formats = []
        if self.output_format_pdf:
            output_formats.append('pdf')
        if self.output_format_xlsx:
            output_formats.append('xlsx')

        if not output_formats:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Format Selected'),
                    'message': _('Please select at least one output format.'),
                    'type': 'warning',
                },
            }

        if not self.history_id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Error'),
                    'message': _('No history record linked to this preview.'),
                    'type': 'danger',
                },
            }

        try:
            import json
            from ..services.rule_engine import RuleEngine
            from ..services.report_builder import ReportBuilder
            from ..services.excel_generator import ExcelGenerator
            from ..services.pdf_generator import PDFGenerator

            raw_intent = json.loads(self.history_id.interpreted_intent or '{}')
            raw_intent['output_formats'] = output_formats

            # Override dates if user modified them in wizard
            if self.date_from:
                raw_intent.setdefault('filters', {})['custom_start'] = self.date_from.isoformat()
                raw_intent['date_range'] = 'custom'
            if self.date_to:
                raw_intent.setdefault('filters', {})['custom_end'] = self.date_to.isoformat()

            engine = RuleEngine(self.env)
            validated = engine.validate_and_expand(raw_intent)

            builder = ReportBuilder(self.env)
            result = builder.build(validated)

            attachments = []
            urls = {}

            if 'xlsx' in output_formats:
                gen = ExcelGenerator(self.env)
                data = gen.generate(result)
                att = self.env['ir.attachment'].create({
                    'name': f'report_{self.history_id.id}.xlsx',
                    'type': 'binary',
                    'datas': data,
                    'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    'res_model': 'ai.report.history',
                    'res_id': self.history_id.id,
                })
                attachments.append(att.id)
                urls['xlsx'] = f'/web/content/{att.id}?download=true'

            if 'pdf' in output_formats:
                gen = PDFGenerator(self.env)
                data = gen.generate(result)
                att = self.env['ir.attachment'].create({
                    'name': f'report_{self.history_id.id}.pdf',
                    'type': 'binary',
                    'datas': data,
                    'mimetype': 'application/pdf',
                    'res_model': 'ai.report.history',
                    'res_id': self.history_id.id,
                })
                attachments.append(att.id)
                urls['pdf'] = f'/web/content/{att.id}?download=true'

            self.history_id.write({
                'status': 'done',
                'attachment_ids': [(4, aid) for aid in attachments],
                'date_from': result.date_from,
                'date_to': result.date_to,
            })

            self.write({
                'state': 'done',
                'download_url_pdf': urls.get('pdf', ''),
                'download_url_xlsx': urls.get('xlsx', ''),
            })

        except Exception as e:
            _logger.exception('Preview wizard generation failed: %s', e)
            self.history_id.write({'status': 'error', 'error_message': str(e)})
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Generation Failed'),
                    'message': str(e),
                    'type': 'danger',
                },
            }

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'report.preview.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_close(self) -> dict:
        """Close the wizard."""
        return {'type': 'ir.actions.act_window_close'}
