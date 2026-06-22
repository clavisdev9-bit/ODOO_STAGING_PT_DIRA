# -*- coding: utf-8 -*-
"""MCP Bridge — lightweight MCP-compatible interface exposing Odoo as an AI tool server.

Allows external AI agents to call Odoo data and report generation via a standard
MCP-style tool dispatch protocol.
"""
import json
import logging
from typing import Any

_logger = logging.getLogger(__name__)

TOOL_SCHEMA = {
    'search_records': {
        'name': 'search_records',
        'description': 'Search records in any accessible Odoo model',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'model': {'type': 'string', 'description': 'Odoo model technical name (e.g. sale.order)'},
                'domain': {'type': 'array', 'description': 'Odoo domain filter list', 'default': []},
                'fields': {'type': 'array', 'items': {'type': 'string'}, 'description': 'Fields to return'},
                'limit': {'type': 'integer', 'default': 100, 'description': 'Max records to return'},
            },
            'required': ['model'],
        },
    },
    'get_report': {
        'name': 'get_report',
        'description': 'Trigger the AI Report Agent pipeline with a natural language message',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'message': {'type': 'string', 'description': 'Natural language report request'},
                'output_format': {
                    'type': 'array',
                    'items': {'type': 'string', 'enum': ['pdf', 'xlsx']},
                    'default': ['pdf', 'xlsx'],
                },
            },
            'required': ['message'],
        },
    },
    'list_models': {
        'name': 'list_models',
        'description': 'List Odoo models available for reporting',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'filter': {'type': 'string', 'description': 'Optional keyword to filter model names'},
            },
        },
    },
    'get_kpi': {
        'name': 'get_kpi',
        'description': 'Fetch pre-defined KPI values for the current company',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'kpi': {
                    'type': 'string',
                    'enum': ['revenue_this_month', 'unpaid_invoices', 'low_stock_count', 'sales_count'],
                    'description': 'KPI identifier',
                },
                'date_range': {'type': 'string', 'default': 'this_month'},
            },
            'required': ['kpi'],
        },
    },
}

ALLOWED_MODELS = {
    'sale.order', 'account.move', 'stock.quant', 'purchase.order',
    'hr.expense', 'res.partner', 'product.product', 'product.template',
}


class OdooMCPBridge:
    """Standard bridge between MCP tool calls and Odoo ORM.

    Allows external AI agents to call Odoo as an MCP server.

    Args:
        env: Odoo environment.
    """

    TOOLS = TOOL_SCHEMA

    def __init__(self, env: Any) -> None:
        self.env = env

    def get_tool_schema(self) -> dict:
        """Return the full MCP tool schema for discovery."""
        return {
            'tools': list(TOOL_SCHEMA.values()),
            'server_info': {
                'name': 'odoo-ai-report-agent',
                'version': '1.0.0',
                'description': 'Odoo 18 AI Report Agent MCP Server',
            },
        }

    def dispatch(self, tool_name: str, arguments: dict) -> dict:
        """Route an MCP tool call to the appropriate handler.

        Args:
            tool_name: Name of the tool to call.
            arguments: Tool arguments dict.

        Returns:
            Dict with 'content' key containing the tool result.
        """
        handlers = {
            'search_records': self._search_records,
            'get_report': self._get_report,
            'list_models': self._list_models,
            'get_kpi': self._get_kpi,
        }

        handler = handlers.get(tool_name)
        if not handler:
            return {
                'isError': True,
                'content': [{'type': 'text', 'text': f'Unknown tool: {tool_name}'}],
            }

        try:
            result = handler(**arguments)
            return {
                'content': [{'type': 'text', 'text': json.dumps(result, default=str)}],
            }
        except Exception as e:
            _logger.exception('MCP tool %s failed: %s', tool_name, e)
            return {
                'isError': True,
                'content': [{'type': 'text', 'text': f'Tool error: {e}'}],
            }

    def _search_records(
        self, model: str, domain: list | None = None,
        fields: list | None = None, limit: int = 100
    ) -> list:
        """Search records in an Odoo model."""
        if model not in ALLOWED_MODELS:
            raise PermissionError(f'Model {model!r} is not in the allowed model list for MCP access.')

        domain = domain or []
        # Scope to current company
        domain = [('company_id', '=', self.env.company.id)] + domain

        records = self.env[model].search(domain, limit=min(limit, 500))

        if fields:
            return records.read(fields)
        return [{'id': r.id, 'name': getattr(r, 'name', str(r.id))} for r in records]

    def _get_report(self, message: str, output_format: list | None = None) -> dict:
        """Trigger the full AI report pipeline."""
        from .ai_interpreter import AIInterpreter
        from .rule_engine import RuleEngine
        from .report_builder import ReportBuilder

        interpreter = AIInterpreter(self.env)
        intent = interpreter.interpret(message)

        engine = RuleEngine(self.env)
        validated = engine.validate_and_expand(intent)

        builder = ReportBuilder(self.env)
        result = builder.build(validated)

        return {
            'intent': validated.get('intent'),
            'date_from': result.date_from.isoformat(),
            'date_to': result.date_to.isoformat(),
            'kpi': result.data.get('kpi', {}),
            'record_count': len(result.raw_records),
            'needs_clarification': validated.get('needs_clarification', False),
            'clarification_question': validated.get('clarification_question'),
        }

    def _list_models(self, filter: str | None = None) -> list:
        """List allowed models for MCP access."""
        models = sorted(ALLOWED_MODELS)
        if filter:
            models = [m for m in models if filter.lower() in m.lower()]
        return [{'model': m, 'description': self.env[m]._description} for m in models if m in self.env]

    def _get_kpi(self, kpi: str, date_range: str = 'this_month') -> dict:
        """Fetch a single pre-defined KPI value."""
        from .date_parser import DateParser
        from .report_builder import ReportBuilder

        parser = DateParser()
        date_from, date_to = parser.parse(date_range)
        company_id = self.env.company.id

        if kpi == 'revenue_this_month':
            orders = self.env['sale.order'].search([
                ('date_order', '>=', date_from.strftime('%Y-%m-%d')),
                ('date_order', '<=', date_to.strftime('%Y-%m-%d') + ' 23:59:59'),
                ('state', 'in', ['sale', 'done']),
                ('company_id', '=', company_id),
            ])
            return {'kpi': kpi, 'value': sum(orders.mapped('amount_total')),
                    'currency': self.env.company.currency_id.name}

        if kpi == 'unpaid_invoices':
            invoices = self.env['account.move'].search([
                ('move_type', 'in', ['out_invoice', 'out_refund']),
                ('payment_state', 'in', ['not_paid', 'partial']),
                ('company_id', '=', company_id),
            ])
            return {'kpi': kpi, 'count': len(invoices),
                    'total': sum(invoices.mapped('amount_residual')),
                    'currency': self.env.company.currency_id.name}

        if kpi == 'low_stock_count':
            quants = self.env['stock.quant'].search([
                ('location_id.usage', '=', 'internal'),
                ('company_id', '=', company_id),
            ])
            low = quants.filtered(
                lambda q: q.product_id.reordering_rules and
                any(r.product_min_qty > q.quantity for r in q.product_id.reordering_rules)
            )
            return {'kpi': kpi, 'count': len(low)}

        if kpi == 'sales_count':
            count = self.env['sale.order'].search_count([
                ('date_order', '>=', date_from.strftime('%Y-%m-%d')),
                ('date_order', '<=', date_to.strftime('%Y-%m-%d') + ' 23:59:59'),
                ('company_id', '=', company_id),
            ])
            return {'kpi': kpi, 'count': count}

        raise ValueError(f'Unknown KPI: {kpi}')
