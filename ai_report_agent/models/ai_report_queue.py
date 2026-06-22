# -*- coding: utf-8 -*-
import json
import logging
from datetime import datetime
from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class AiReportQueue(models.Model):
    """Async job queue for large report requests."""

    _name = 'ai.report.queue'
    _description = 'AI Report Async Queue'
    _order = 'scheduled_at asc, id asc'

    history_id = fields.Many2one(
        comodel_name='ai.report.history',
        string='History Record',
        required=True,
        ondelete='cascade',
    )
    payload = fields.Text(
        string='Payload (JSON)',
        required=True,
        help='Validated intent JSON to process',
    )
    status = fields.Selection(
        selection=[
            ('pending', 'Pending'),
            ('running', 'Running'),
            ('done', 'Done'),
            ('failed', 'Failed'),
        ],
        string='Status',
        default='pending',
        required=True,
        index=True,
    )
    retry_count = fields.Integer(string='Retry Count', default=0)
    max_retries = fields.Integer(string='Max Retries', default=3)
    scheduled_at = fields.Datetime(
        string='Scheduled At',
        default=fields.Datetime.now,
    )
    started_at = fields.Datetime(string='Started At', readonly=True)
    finished_at = fields.Datetime(string='Finished At', readonly=True)
    error_message = fields.Text(string='Error', readonly=True)

    @api.model
    def process_queue(self) -> None:
        """Process pending jobs in the queue. Called by ir.cron."""
        pending_jobs = self.search([
            ('status', '=', 'pending'),
            ('retry_count', '<', 3),
        ], limit=10)

        _logger.info('AI Report Queue: processing %d pending jobs', len(pending_jobs))

        for job in pending_jobs:
            job._run_job()

    def _run_job(self) -> None:
        """Execute the report pipeline for one queued job."""
        self.ensure_one()
        self.write({
            'status': 'running',
            'started_at': fields.Datetime.now(),
        })

        try:
            payload = json.loads(self.payload)
            from ..services.report_builder import ReportBuilder
            builder = ReportBuilder(self.env)
            result = builder.build(payload)

            from ..services.excel_generator import ExcelGenerator
            from ..services.pdf_generator import PDFGenerator

            attachments = []
            output_formats = payload.get('output_formats', ['pdf', 'xlsx'])

            if 'xlsx' in output_formats:
                excel_gen = ExcelGenerator(self.env)
                xlsx_bytes = excel_gen.generate(result)
                xlsx_att = self.env['ir.attachment'].create({
                    'name': f'report_{self.history_id.id}.xlsx',
                    'type': 'binary',
                    'datas': xlsx_bytes,
                    'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    'res_model': 'ai.report.history',
                    'res_id': self.history_id.id,
                })
                attachments.append(xlsx_att.id)

            if 'pdf' in output_formats:
                pdf_gen = PDFGenerator(self.env)
                pdf_bytes = pdf_gen.generate(result)
                pdf_att = self.env['ir.attachment'].create({
                    'name': f'report_{self.history_id.id}.pdf',
                    'type': 'binary',
                    'datas': pdf_bytes,
                    'mimetype': 'application/pdf',
                    'res_model': 'ai.report.history',
                    'res_id': self.history_id.id,
                })
                attachments.append(pdf_att.id)

            self.history_id.write({
                'status': 'done',
                'attachment_ids': [(4, att_id) for att_id in attachments],
            })
            self.history_id.message_post(
                body=_('Report is ready. <a href="/web#model=ai.report.history&id=%s">View Report</a>') % self.history_id.id,
                message_type='notification',
            )
            self.write({
                'status': 'done',
                'finished_at': fields.Datetime.now(),
            })

        except Exception as e:
            _logger.exception('Queue job %s failed: %s', self.id, e)
            self.write({
                'status': 'failed' if self.retry_count >= self.max_retries else 'pending',
                'retry_count': self.retry_count + 1,
                'error_message': str(e),
                'finished_at': fields.Datetime.now(),
            })
            self.history_id.write({
                'status': 'error',
                'error_message': str(e),
            })
