# -*- coding: utf-8 -*-
"""PDF report generator using Odoo QWeb rendering with ReportLab fallback."""
import base64
import io
import logging
from typing import Any

_logger = logging.getLogger(__name__)

TEMPLATE_MAP = {
    'sales': 'ai_report_agent.report_sales_template',
    'invoice': 'ai_report_agent.report_invoice_template',
    'inventory': 'ai_report_agent.report_inventory_template',
    'purchase': 'ai_report_agent.report_purchase_template',
    'summary': 'ai_report_agent.report_summary_template',
}


class PDFGenerator:
    """Generates PDF reports via Odoo QWeb with ReportLab fallback.

    Args:
        env: Odoo environment.
    """

    def __init__(self, env: Any) -> None:
        self.env = env

    def generate(self, result: Any) -> bytes:
        """Generate a PDF and return base64-encoded bytes.

        Args:
            result: ReportResult dataclass.

        Returns:
            Base64-encoded PDF bytes.
        """
        try:
            return self._generate_qweb(result)
        except Exception as qweb_err:
            _logger.warning('QWeb PDF generation failed (%s), trying ReportLab', qweb_err)
            try:
                return self._generate_reportlab(result)
            except Exception as rl_err:
                _logger.error('ReportLab PDF generation also failed: %s', rl_err)
                raise RuntimeError(f'PDF generation failed: QWeb={qweb_err}, ReportLab={rl_err}') from rl_err

    def _generate_qweb(self, result: Any) -> bytes:
        """Render PDF using Odoo's built-in QWeb engine."""
        template_id = TEMPLATE_MAP.get(result.intent, TEMPLATE_MAP['summary'])

        # Build render context
        render_ctx = {
            'result': result,
            'data': result.data,
            'metadata': result.metadata,
            'company': self.env.company,
            'date_from': result.date_from,
            'date_to': result.date_to,
        }

        # Use ir.actions.report for QWeb rendering
        report_action = self.env.ref(template_id, raise_if_not_found=False)
        if not report_action:
            raise ValueError(f'QWeb template {template_id!r} not found')

        # Direct QWeb rendering
        pdf_content, _ = self.env['ir.actions.report']._render_qweb_pdf(
            report_action.id, res_ids=None, data=render_ctx
        )
        return base64.b64encode(pdf_content)

    def _generate_reportlab(self, result: Any) -> bytes:
        """Fallback: generate PDF using ReportLab."""
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import cm
            from reportlab.platypus import (
                SimpleDocTemplate, Table, TableStyle, Paragraph,
                Spacer, HRFlowable,
            )
        except ImportError as e:
            raise ImportError('reportlab is not installed. Run: pip install reportlab') from e

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=1.5 * cm,
            leftMargin=1.5 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        styles = getSampleStyleSheet()
        story = []

        # Company header
        company = self.env.company
        story.append(Paragraph(company.name, styles['Title']))
        story.append(Paragraph(
            f'{result.intent.title()} Report — {result.date_from} to {result.date_to}',
            styles['Heading2'],
        ))
        story.append(HRFlowable(width='100%', thickness=2, color=colors.HexColor('#2E4057')))
        story.append(Spacer(1, 0.5 * cm))

        # Company logo if available
        if company.logo:
            try:
                from reportlab.platypus import Image
                logo_data = base64.b64decode(company.logo)
                logo_buffer = io.BytesIO(logo_data)
                img = Image(logo_buffer, width=4 * cm, height=2 * cm)
                story.insert(0, img)
            except Exception as logo_err:
                _logger.debug('Could not embed logo: %s', logo_err)

        # KPI summary table
        kpi_rows = self._build_kpi_rows(result)
        if kpi_rows:
            story.append(Paragraph('Key Performance Indicators', styles['Heading3']))
            kpi_table_data = [['Metric', 'Value']] + kpi_rows
            kpi_table = Table(kpi_table_data, colWidths=[10 * cm, 6 * cm])
            kpi_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E4057')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#EBF5FB')]),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#BDC3C7')),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ]))
            story.append(kpi_table)
            story.append(Spacer(1, 0.5 * cm))

        # Detail table
        detail_headers, detail_rows = self._build_detail_table(result)
        if detail_rows:
            story.append(Paragraph('Detail Records', styles['Heading3']))
            table_data = [detail_headers] + detail_rows[:500]  # limit for PDF readability
            col_count = len(detail_headers)
            col_width = (A4[0] - 3 * cm) / col_count
            detail_table = Table(table_data, colWidths=[col_width] * col_count, repeatRows=1)
            detail_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E4057')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#EBF5FB')]),
                ('GRID', (0, 0), (-1, -1), 0.3, colors.HexColor('#BDC3C7')),
                ('ALIGN', (-1, 0), (-1, -1), 'RIGHT'),
            ]))
            story.append(detail_table)

        doc.build(story)
        buffer.seek(0)
        return base64.b64encode(buffer.read())

    def _build_kpi_rows(self, result: Any) -> list[list]:
        """Build KPI rows for PDF summary table."""
        from .excel_generator import ExcelGenerator
        gen = ExcelGenerator(self.env)
        return [[label, f'{value:,.2f}' if isinstance(value, float) else str(value)]
                for label, value in gen._extract_kpi(result)]

    def _build_detail_table(self, result: Any) -> tuple[list, list]:
        """Build detail table data for PDF."""
        from .excel_generator import ExcelGenerator
        gen = ExcelGenerator(self.env)
        rows, headers = gen._extract_detail_rows(result)
        str_rows = [[str(v) if v is not None else '' for v in row] for row in rows]
        return headers, str_rows
