# -*- coding: utf-8 -*-
"""Excel report generator using openpyxl.

Produces multi-sheet workbooks with auto-widths, styled headers, zebra rows,
and embedded bar/pie charts.
"""
import base64
import io
import logging
from typing import Any

_logger = logging.getLogger(__name__)

# Style constants
HEADER_FILL_COLOR = '2E4057'
HEADER_FONT_COLOR = 'FFFFFF'
ZEBRA_FILL_COLOR = 'EBF5FB'
BORDER_COLOR = 'BDC3C7'


class ExcelGenerator:
    """Generates Excel workbooks from ReportResult objects.

    Args:
        env: Odoo environment (used to read company info).
    """

    def __init__(self, env: Any) -> None:
        self.env = env

    def generate(self, result: Any) -> bytes:
        """Generate an Excel file and return base64-encoded bytes.

        Args:
            result: ReportResult dataclass with data and metadata.

        Returns:
            Base64-encoded bytes of the .xlsx file.
        """
        try:
            import openpyxl
            from openpyxl.styles import (
                Font, PatternFill, Alignment, Border, Side, numbers
            )
            from openpyxl.chart import BarChart, PieChart, Reference
            from openpyxl.utils import get_column_letter
        except ImportError as e:
            raise ImportError('openpyxl is required. Run: pip install openpyxl') from e

        wb = openpyxl.Workbook()
        wb.remove(wb.active)  # remove default sheet

        # Sheet 1: Summary
        ws_summary = wb.create_sheet('Summary')
        self._write_summary_sheet(ws_summary, result, openpyxl)

        # Sheet 2: Detail
        ws_detail = wb.create_sheet('Detail')
        self._write_detail_sheet(ws_detail, result, openpyxl)

        # Add chart to detail sheet if data supports it
        self._add_chart(ws_detail, ws_summary, result, openpyxl)

        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return base64.b64encode(buffer.read())

    def _write_summary_sheet(self, ws: Any, result: Any, openpyxl: Any) -> None:
        """Write KPI summary to the first sheet."""
        from openpyxl.styles import Font, PatternFill, Alignment

        company = self.env.company
        ws.column_dimensions['A'].width = 35
        ws.column_dimensions['B'].width = 25

        # Title
        ws['A1'] = f'{company.name} — {result.intent.title()} Report'
        ws['A1'].font = Font(size=14, bold=True, color=HEADER_FILL_COLOR)
        ws.merge_cells('A1:B1')

        ws['A2'] = f'Period: {result.date_from} → {result.date_to}'
        ws['A2'].font = Font(italic=True, color='7F8C8D')
        ws.merge_cells('A2:B2')

        row = 4
        kpi_data = self._extract_kpi(result)
        for label, value in kpi_data:
            ws.cell(row=row, column=1, value=label).font = Font(bold=True)
            cell = ws.cell(row=row, column=2, value=value)
            if isinstance(value, (int, float)):
                cell.number_format = '#,##0.00'
                cell.alignment = Alignment(horizontal='right')
            row += 1

    def _write_detail_sheet(self, ws: Any, result: Any, openpyxl: Any) -> None:
        """Write detailed records to the second sheet."""
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        rows, headers = self._extract_detail_rows(result)
        if not headers:
            ws['A1'] = 'No detail data available.'
            return

        header_fill = PatternFill('solid', fgColor=HEADER_FILL_COLOR)
        zebra_fill = PatternFill('solid', fgColor=ZEBRA_FILL_COLOR)
        thin = Side(border_style='thin', color=BORDER_COLOR)
        border = Border(left=thin, right=thin, top=thin, bottom=thin)

        # Write headers
        for col_idx, header in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = Font(bold=True, color=HEADER_FONT_COLOR)
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center', wrap_text=True)
            cell.border = border

        # Write data rows
        for row_idx, row_data in enumerate(rows, start=2):
            fill = zebra_fill if row_idx % 2 == 0 else None
            for col_idx, value in enumerate(row_data, start=1):
                cell = ws.cell(row=row_idx, column=col_idx, value=value)
                cell.border = border
                if fill:
                    cell.fill = fill
                if isinstance(value, (int, float)):
                    cell.number_format = '#,##0.00'
                    cell.alignment = Alignment(horizontal='right')

        # Auto-column width
        for col_idx, header in enumerate(headers, start=1):
            col_letter = get_column_letter(col_idx)
            lengths = [len(str(header))] + [
                len(str(r[col_idx - 1])) for r in rows if col_idx - 1 < len(r)
            ]
            max_length = max(lengths, default=10)
            ws.column_dimensions[col_letter].width = min(max_length + 4, 50)

        ws.freeze_panes = 'A2'

    def _add_chart(self, ws_detail: Any, ws_summary: Any, result: Any, openpyxl: Any) -> None:
        """Add a chart to the summary sheet based on intent."""
        from openpyxl.chart import BarChart, PieChart, Reference

        intent = result.intent
        try:
            if intent == 'invoice':
                self._add_pie_chart(ws_summary, result, openpyxl)
            else:
                self._add_bar_chart(ws_detail, result, openpyxl)
        except Exception as e:
            _logger.warning('Chart generation failed: %s', e)

    def _add_bar_chart(self, ws: Any, result: Any, openpyxl: Any) -> None:
        """Add a bar chart for sales/purchase data."""
        from openpyxl.chart import BarChart, Reference

        top_products = result.data.get('top_products', [])[:10]
        if not top_products:
            return

        start_row = ws.max_row + 2
        ws.cell(row=start_row, column=1, value='Product')
        ws.cell(row=start_row, column=2, value='Amount')

        for i, prod in enumerate(top_products, start=1):
            ws.cell(row=start_row + i, column=1, value=prod.get('name', ''))
            ws.cell(row=start_row + i, column=2, value=prod.get('amount', 0))

        chart = BarChart()
        chart.type = 'col'
        chart.title = 'Top Products by Revenue'
        chart.y_axis.title = 'Amount'
        chart.x_axis.title = 'Product'
        chart.width = 20
        chart.height = 12

        data = Reference(ws, min_col=2, min_row=start_row, max_row=start_row + len(top_products))
        cats = Reference(ws, min_col=1, min_row=start_row + 1, max_row=start_row + len(top_products))
        chart.add_data(data, titles_from_data=True)
        chart.set_categories(cats)
        ws.add_chart(chart, f'D{start_row}')

    def _add_pie_chart(self, ws: Any, result: Any, openpyxl: Any) -> None:
        """Add a pie chart for invoice payment status."""
        from openpyxl.chart import PieChart, Reference

        data_rows = [
            ('Paid', result.data.get('total_paid', 0)),
            ('Unpaid', result.data.get('total_unpaid', 0)),
            ('Overdue', result.data.get('total_overdue', 0)),
        ]
        start_row = ws.max_row + 2
        for i, (label, value) in enumerate(data_rows):
            ws.cell(row=start_row + i, column=4, value=label)
            ws.cell(row=start_row + i, column=5, value=value)

        chart = PieChart()
        chart.title = 'Invoice Payment Status'
        chart.width = 16
        chart.height = 12

        data = Reference(ws, min_col=5, min_row=start_row, max_row=start_row + len(data_rows) - 1)
        labels = Reference(ws, min_col=4, min_row=start_row, max_row=start_row + len(data_rows) - 1)
        chart.add_data(data)
        chart.dataLabels = openpyxl.chart.label.DataLabelList()
        chart.dataLabels.showPercent = True
        chart.set_categories(labels)
        ws.add_chart(chart, 'D4')

    # -------------------------------------------------------------------
    # Data extraction helpers
    # -------------------------------------------------------------------

    def _extract_kpi(self, result: Any) -> list[tuple[str, Any]]:
        """Extract key-value KPI pairs from result data."""
        data = result.data
        intent = result.intent

        if intent == 'summary':
            kpi = data.get('kpi', {})
            return [
                ('Total Revenue', kpi.get('total_revenue', 0)),
                ('Total Invoiced', kpi.get('total_invoiced', 0)),
                ('Total Unpaid', kpi.get('total_unpaid', 0)),
                ('Overdue Amount', kpi.get('total_overdue', 0)),
                ('Low Stock Items', kpi.get('low_stock_count', 0)),
                ('Sales Orders', kpi.get('order_count', 0)),
            ]
        if intent == 'sales':
            return [
                ('Total Revenue', data.get('total_revenue', 0)),
                ('Total Orders', data.get('order_count', 0)),
                ('Confirmed Orders', data.get('confirmed_count', 0)),
            ]
        if intent == 'invoice':
            return [
                ('Total Invoiced', data.get('total_invoiced', 0)),
                ('Total Paid', data.get('total_paid', 0)),
                ('Total Unpaid', data.get('total_unpaid', 0)),
                ('Total Overdue', data.get('total_overdue', 0)),
                ('Paid Invoices', data.get('count_paid', 0)),
                ('Unpaid Invoices', data.get('count_unpaid', 0)),
                ('Overdue Invoices', data.get('count_overdue', 0)),
            ]
        if intent == 'inventory':
            return [
                ('Total Products', data.get('total_products', 0)),
                ('Low Stock Items', data.get('low_stock_count', 0)),
                ('Total Quantity', data.get('total_quantity', 0)),
            ]
        if intent == 'purchase':
            return [
                ('Total Spend', data.get('total_spend', 0)),
                ('Total Orders', data.get('order_count', 0)),
                ('Confirmed Orders', data.get('confirmed_count', 0)),
            ]
        return []

    def _extract_detail_rows(self, result: Any) -> tuple[list, list]:
        """Extract table headers and rows from result data for detail sheet."""
        intent = result.intent
        data = result.data

        if intent in ('sales', 'summary'):
            records = data.get('orders', data.get('sales', {}).get('orders', []))
            headers = ['Order', 'Customer', 'Date', 'Status', 'Amount']
            rows = [[r.get('name'), r.get('partner'), r.get('date'), r.get('state'), r.get('amount')]
                    for r in records]
            return rows, headers

        if intent == 'invoice':
            records = data.get('invoices', [])
            headers = ['Invoice', 'Customer', 'Date', 'Due Date', 'Amount', 'Residual', 'Status', 'Payment']
            rows = [[r.get('name'), r.get('partner'), r.get('date'), r.get('due'),
                     r.get('amount'), r.get('residual'), r.get('state'), r.get('payment_state')]
                    for r in records]
            return rows, headers

        if intent == 'inventory':
            records = data.get('quants', [])
            headers = ['Product', 'Location', 'Quantity', 'Reserved', 'Available']
            rows = [[r.get('product'), r.get('location'), r.get('quantity'),
                     r.get('reserved'), r.get('available')]
                    for r in records]
            return rows, headers

        if intent == 'purchase':
            records = data.get('orders', [])
            headers = ['Order', 'Vendor', 'Date', 'Status', 'Amount']
            rows = [[r.get('name'), r.get('vendor'), r.get('date'), r.get('state'), r.get('amount')]
                    for r in records]
            return rows, headers

        return [], []
