# -*- coding: utf-8 -*-
"""Report Builder — orchestrates the full pipeline from validated intent to ReportResult."""
import json
import logging
import time
from dataclasses import dataclass, field
from datetime import date
from typing import Any

_logger = logging.getLogger(__name__)

PAGE_SIZE_DEFAULT = 500


@dataclass
class ReportResult:
    """Structured output of a built report."""

    intent: str
    report_type: str
    date_from: date
    date_to: date
    data: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    raw_records: list = field(default_factory=list)
    insight_text: str = ''
    output_formats: list = field(default_factory=lambda: ['pdf', 'xlsx'])


class ReportBuilder:
    """Orchestrates data fetching and aggregation for all report types.

    Args:
        env: Odoo environment.
    """

    def __init__(self, env: Any) -> None:
        self.env = env

    def build(self, validated_intent: dict) -> ReportResult:
        """Build a report from a validated intent dict.

        Args:
            validated_intent: Output from RuleEngine.validate_and_expand().

        Returns:
            ReportResult with aggregated data ready for file generators.
        """
        from .date_parser import DateParser

        intent = validated_intent.get('intent', 'summary')
        date_range = validated_intent.get('date_range', 'this_month')
        filters = validated_intent.get('filters', {})

        parser = DateParser()
        date_from, date_to = parser.parse(date_range, filters)

        config = self.env['ai.report.config'].get_active_config()
        max_rows = config.max_rows or 1000

        result = ReportResult(
            intent=intent,
            report_type=validated_intent.get('report_type', 'table'),
            date_from=date_from,
            date_to=date_to,
            output_formats=validated_intent.get('output_formats', ['pdf', 'xlsx']),
        )

        builder_map = {
            'sales': self._build_sales,
            'invoice': self._build_invoice,
            'inventory': self._build_inventory,
            'purchase': self._build_purchase,
            'summary': self._build_summary,
        }

        builder_fn = builder_map.get(intent, self._build_summary)
        builder_fn(result, validated_intent, date_from, date_to, max_rows)

        result.metadata.update({
            'date_from': date_from.isoformat(),
            'date_to': date_to.isoformat(),
            'intent': intent,
            'report_type': result.report_type,
            'company': self.env.company.name,
            'company_logo': self.env.company.logo,
        })

        return result

    def build_from_history(self, history_record: Any) -> ReportResult:
        """Re-run a report from an existing history record."""
        if not history_record.interpreted_intent:
            raise ValueError('History record has no interpreted intent to re-run.')
        from .rule_engine import RuleEngine
        raw_intent = json.loads(history_record.interpreted_intent)
        engine = RuleEngine(self.env)
        validated = engine.validate_and_expand(raw_intent)
        return self.build(validated)

    # -------------------------------------------------------------------
    # Report type builders
    # -------------------------------------------------------------------

    def _build_sales(
        self, result: ReportResult, intent: dict,
        date_from: date, date_to: date, max_rows: int
    ) -> None:
        """Build Sales Report: revenue, order count, top products."""
        domain = [
            ('date_order', '>=', date_from.strftime('%Y-%m-%d')),
            ('date_order', '<=', date_to.strftime('%Y-%m-%d') + ' 23:59:59'),
            ('company_id', '=', self.env.company.id),
        ] + intent.get('domain', [])

        orders = self.env['sale.order'].search(domain, limit=max_rows)
        total_revenue = sum(orders.mapped('amount_total'))
        confirmed = orders.filtered(lambda o: o.state in ('sale', 'done'))

        product_sales: dict[str, dict] = {}
        for order in confirmed:
            for line in order.order_line:
                pname = line.product_id.display_name or 'Unknown'
                if pname not in product_sales:
                    product_sales[pname] = {'qty': 0.0, 'amount': 0.0}
                product_sales[pname]['qty'] += line.product_uom_qty
                product_sales[pname]['amount'] += line.price_subtotal

        top_products = sorted(product_sales.items(), key=lambda x: x[1]['amount'], reverse=True)[:10]

        result.data = {
            'total_revenue': total_revenue,
            'order_count': len(orders),
            'confirmed_count': len(confirmed),
            'currency': self.env.company.currency_id.name,
            'top_products': [
                {'name': k, 'qty': v['qty'], 'amount': v['amount']}
                for k, v in top_products
            ],
            'orders': [self._sale_order_row(o) for o in orders],
        }
        result.raw_records = orders.ids

    def _build_invoice(
        self, result: ReportResult, intent: dict,
        date_from: date, date_to: date, max_rows: int
    ) -> None:
        """Build Invoice Report: unpaid/overdue/paid breakdown."""
        domain = [
            ('invoice_date', '>=', date_from.strftime('%Y-%m-%d')),
            ('invoice_date', '<=', date_to.strftime('%Y-%m-%d')),
            ('move_type', 'in', ['out_invoice', 'out_refund']),
            ('company_id', '=', self.env.company.id),
        ] + intent.get('domain', [])

        invoices = self.env['account.move'].search(domain, limit=max_rows)
        today = date.today()

        paid = invoices.filtered(lambda i: i.payment_state == 'paid')
        unpaid = invoices.filtered(lambda i: i.payment_state in ('not_paid', 'partial'))
        overdue = unpaid.filtered(
            lambda i: i.invoice_date_due and i.invoice_date_due < today
        )

        result.data = {
            'total_invoiced': sum(invoices.mapped('amount_total')),
            'total_paid': sum(paid.mapped('amount_total')),
            'total_unpaid': sum(unpaid.mapped('amount_residual')),
            'total_overdue': sum(overdue.mapped('amount_residual')),
            'count_paid': len(paid),
            'count_unpaid': len(unpaid),
            'count_overdue': len(overdue),
            'currency': self.env.company.currency_id.name,
            'invoices': [self._invoice_row(inv) for inv in invoices],
        }
        result.raw_records = invoices.ids

    def _build_inventory(
        self, result: ReportResult, intent: dict,
        date_from: date, date_to: date, max_rows: int
    ) -> None:
        """Build Inventory Report: low stock alerts and stock levels."""
        domain = [
            ('location_id.usage', '=', 'internal'),
            ('company_id', '=', self.env.company.id),
        ] + intent.get('domain', [])

        quants = self.env['stock.quant'].search(domain, limit=max_rows)
        low_stock = quants.filtered(
            lambda q: q.product_id.reordering_rules and
            any(r.product_min_qty > q.quantity for r in q.product_id.reordering_rules)
        )

        result.data = {
            'total_products': len(quants.mapped('product_id')),
            'low_stock_count': len(low_stock),
            'total_quantity': sum(quants.mapped('quantity')),
            'quants': [self._quant_row(q) for q in quants],
            'low_stock': [self._quant_row(q) for q in low_stock],
        }
        result.raw_records = quants.ids

    def _build_purchase(
        self, result: ReportResult, intent: dict,
        date_from: date, date_to: date, max_rows: int
    ) -> None:
        """Build Purchase Report: total spend, order counts."""
        domain = [
            ('date_order', '>=', date_from.strftime('%Y-%m-%d')),
            ('date_order', '<=', date_to.strftime('%Y-%m-%d') + ' 23:59:59'),
            ('company_id', '=', self.env.company.id),
        ] + intent.get('domain', [])

        orders = self.env['purchase.order'].search(domain, limit=max_rows)
        confirmed = orders.filtered(lambda o: o.state in ('purchase', 'done'))

        result.data = {
            'total_spend': sum(orders.mapped('amount_total')),
            'order_count': len(orders),
            'confirmed_count': len(confirmed),
            'currency': self.env.company.currency_id.name,
            'orders': [self._purchase_order_row(o) for o in orders],
        }
        result.raw_records = orders.ids

    def _build_summary(
        self, result: ReportResult, intent: dict,
        date_from: date, date_to: date, max_rows: int
    ) -> None:
        """Build Summary KPI dashboard combining sales, invoices, and inventory."""
        sales_result = ReportResult(
            intent='sales', report_type='summary',
            date_from=date_from, date_to=date_to,
        )
        self._build_sales(sales_result, intent, date_from, date_to, max_rows)

        invoice_result = ReportResult(
            intent='invoice', report_type='summary',
            date_from=date_from, date_to=date_to,
        )
        self._build_invoice(invoice_result, intent, date_from, date_to, max_rows)

        inventory_result = ReportResult(
            intent='inventory', report_type='summary',
            date_from=date_from, date_to=date_to,
        )
        self._build_inventory(inventory_result, intent, date_from, date_to, max_rows)

        result.data = {
            'sales': sales_result.data,
            'invoice': invoice_result.data,
            'inventory': inventory_result.data,
            'kpi': {
                'total_revenue': sales_result.data.get('total_revenue', 0),
                'total_invoiced': invoice_result.data.get('total_invoiced', 0),
                'total_unpaid': invoice_result.data.get('total_unpaid', 0),
                'total_overdue': invoice_result.data.get('total_overdue', 0),
                'low_stock_count': inventory_result.data.get('low_stock_count', 0),
                'order_count': sales_result.data.get('order_count', 0),
                'currency': self.env.company.currency_id.name,
            },
        }

    # -------------------------------------------------------------------
    # Row serializers
    # -------------------------------------------------------------------

    @staticmethod
    def _sale_order_row(order: Any) -> dict:
        return {
            'name': order.name,
            'partner': order.partner_id.name,
            'date': order.date_order.strftime('%Y-%m-%d') if order.date_order else '',
            'state': order.state,
            'amount': order.amount_total,
        }

    @staticmethod
    def _invoice_row(inv: Any) -> dict:
        return {
            'name': inv.name,
            'partner': inv.partner_id.name,
            'date': inv.invoice_date.strftime('%Y-%m-%d') if inv.invoice_date else '',
            'due': inv.invoice_date_due.strftime('%Y-%m-%d') if inv.invoice_date_due else '',
            'amount': inv.amount_total,
            'residual': inv.amount_residual,
            'state': inv.state,
            'payment_state': inv.payment_state,
        }

    @staticmethod
    def _quant_row(q: Any) -> dict:
        return {
            'product': q.product_id.display_name,
            'location': q.location_id.complete_name,
            'quantity': q.quantity,
            'reserved': q.reserved_quantity,
            'available': q.quantity - q.reserved_quantity,
        }

    @staticmethod
    def _purchase_order_row(order: Any) -> dict:
        return {
            'name': order.name,
            'vendor': order.partner_id.name,
            'date': order.date_order.strftime('%Y-%m-%d') if order.date_order else '',
            'state': order.state,
            'amount': order.amount_total,
        }
