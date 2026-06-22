# -*- coding: utf-8 -*-
"""Deterministic Rule Engine — validates and expands AI intent into Odoo-ready structures.

No AI calls are made here. All logic is rule-based and testable.
"""
import logging
import re
from typing import Any

_logger = logging.getLogger(__name__)

# Canonical intent → Odoo model mapping
INTENT_MODEL_MAP: dict[str, str | list[str]] = {
    'sales': 'sale.order',
    'invoice': 'account.move',
    'inventory': 'stock.quant',
    'purchase': 'purchase.order',
    'expense': 'hr.expense',
    'summary': ['sale.order', 'account.move', 'stock.quant'],
}

VALID_INTENTS = set(INTENT_MODEL_MAP.keys()) | {'unknown'}

VALID_DATE_RANGES = {
    'today', 'this_week', 'last_week', 'this_month', 'last_month',
    'this_quarter', 'last_quarter', 'Q1', 'Q2', 'Q3', 'Q4', 'this_year', 'custom',
}

VALID_REPORT_TYPES = {'table', 'summary', 'chart'}

VALID_OUTPUT_FORMATS = {'pdf', 'xlsx'}

VALID_INVOICE_STATES = {'draft', 'posted', 'cancel'}
VALID_PAYMENT_STATES = {'not_paid', 'in_payment', 'paid', 'partial', 'reversed', 'invoicing_legacy'}
VALID_SALE_STATES = {'draft', 'sent', 'sale', 'done', 'cancel'}
VALID_PURCHASE_STATES = {'draft', 'sent', 'to approve', 'purchase', 'done', 'cancel'}

# Patterns that suggest injection attempts
_INJECTION_PATTERNS = re.compile(
    r'(DROP|INSERT|UPDATE|DELETE|SELECT|\bOR\b|\bAND\b|--|;|<script|javascript:)',
    re.IGNORECASE,
)


class RuleEngineError(Exception):
    """Raised when intent cannot be resolved to a valid domain."""


class RuleEngine:
    """Validates, sanitizes, and expands a raw AI intent dict.

    Args:
        env: Odoo environment for model lookups.
    """

    def __init__(self, env: Any) -> None:
        self.env = env

    def validate_and_expand(self, intent_dict: dict) -> dict:
        """Validate and expand an AI-produced intent dict.

        Args:
            intent_dict: Raw dict from AIInterpreter.

        Returns:
            Expanded dict with resolved model, validated domain fragments, date objects.

        Raises:
            RuleEngineError: If intent is unknown and fallback is disabled.
        """
        intent = self._sanitize_str(intent_dict.get('intent', 'unknown'))
        if intent not in VALID_INTENTS:
            _logger.warning('Unknown intent "%s", defaulting to "summary"', intent)
            intent = 'summary'

        date_range = self._sanitize_str(intent_dict.get('date_range', 'this_month'))
        if date_range not in VALID_DATE_RANGES:
            _logger.warning('Invalid date_range "%s", defaulting to "this_month"', date_range)
            date_range = 'this_month'

        report_type = self._sanitize_str(intent_dict.get('report_type', 'table'))
        if report_type not in VALID_REPORT_TYPES:
            report_type = 'table'

        raw_formats = intent_dict.get('output_format') or intent_dict.get('output_formats') or ['pdf', 'xlsx']
        output_formats = [f for f in raw_formats if f in VALID_OUTPUT_FORMATS] or ['pdf']

        filters = self._validate_filters(intent_dict.get('filters', {}), intent)

        model = INTENT_MODEL_MAP.get(intent, 'sale.order')

        domain = self._build_domain(intent, filters)

        confidence = float(intent_dict.get('confidence', 0.5))
        needs_clarification = bool(intent_dict.get('needs_clarification', False))
        clarification_question = intent_dict.get('clarification_question')

        # Auto-flag ambiguity when date not specified
        if date_range == 'this_month' and not intent_dict.get('date_range'):
            needs_clarification = True
            if not clarification_question:
                clarification_question = (
                    'Date range not specified. Defaulting to this month. '
                    'Please confirm or specify a date range.'
                )

        return {
            'intent': intent,
            'model': model,
            'date_range': date_range,
            'filters': filters,
            'report_type': report_type,
            'output_formats': output_formats,
            'domain': domain,
            'confidence': confidence,
            'needs_clarification': needs_clarification,
            'clarification_question': clarification_question,
        }

    def _validate_filters(self, raw_filters: dict, intent: str) -> dict:
        """Sanitize and validate filter values against allowed enums."""
        filters = {}

        state = self._sanitize_str(raw_filters.get('state', ''))
        if state:
            valid_states = {
                'invoice': VALID_INVOICE_STATES,
                'sales': VALID_SALE_STATES,
                'purchase': VALID_PURCHASE_STATES,
            }.get(intent, set())
            filters['state'] = state if state in valid_states else ''

        payment_state = self._sanitize_str(raw_filters.get('payment_state', ''))
        if payment_state and payment_state in VALID_PAYMENT_STATES:
            filters['payment_state'] = payment_state

        # Partner and product IDs must be integers
        partner_id = self._safe_int(raw_filters.get('partner_id'))
        if partner_id:
            filters['partner_id'] = partner_id

        product_id = self._safe_int(raw_filters.get('product_id'))
        if product_id:
            filters['product_id'] = product_id

        warehouse_id = self._safe_int(raw_filters.get('warehouse_id'))
        if warehouse_id:
            filters['warehouse_id'] = warehouse_id

        filters['custom_start'] = self._sanitize_str(raw_filters.get('custom_start', ''))
        filters['custom_end'] = self._sanitize_str(raw_filters.get('custom_end', ''))

        return filters

    def _build_domain(self, intent: str, filters: dict) -> list:
        """Build Odoo domain fragments from validated filters."""
        domain: list = []

        if filters.get('state'):
            domain.append(('state', '=', filters['state']))

        if filters.get('payment_state') and intent == 'invoice':
            domain.append(('payment_state', '=', filters['payment_state']))

        if filters.get('partner_id'):
            domain.append(('partner_id', '=', filters['partner_id']))

        if intent == 'invoice':
            domain.append(('move_type', 'in', ['out_invoice', 'out_refund']))

        if intent == 'inventory':
            domain.append(('location_id.usage', '=', 'internal'))

        return domain

    @staticmethod
    def _sanitize_str(value: Any) -> str:
        """Strip potential injection patterns and return safe string."""
        if not isinstance(value, str):
            return ''
        if _INJECTION_PATTERNS.search(value):
            _logger.warning('Potential injection detected in value: %s — sanitized to empty', value)
            return ''
        return value.strip()

    @staticmethod
    def _safe_int(value: Any) -> int | None:
        """Convert value to int safely, return None on failure."""
        try:
            result = int(value)
            return result if result > 0 else None
        except (TypeError, ValueError):
            return None
