# -*- coding: utf-8 -*-
"""Deterministic date range parser — no AI involved.

All methods return (date_from, date_to) as Python date objects.

Doctests:
    >>> from datetime import date
    >>> import unittest.mock as mock
    >>> with mock.patch('ai_report_agent.services.date_parser.date') as d:
    ...     d.today.return_value = date(2025, 6, 15)
    ...     d.side_effect = lambda *a, **kw: date(*a, **kw)
    ...     dp = DateParser()
    ...     dp.parse('today')
    (datetime.date(2025, 6, 15), datetime.date(2025, 6, 15))
"""
import logging
from datetime import date, timedelta
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)

DATE_RANGE_KEYS = {
    'today', 'this_week', 'this_month', 'last_month', 'last_week',
    'this_quarter', 'last_quarter', 'Q1', 'Q2', 'Q3', 'Q4',
    'this_year', 'custom',
}


class DateParser:
    """Converts symbolic date range keys into concrete (date_from, date_to) pairs.

    All logic is deterministic — no LLM calls, no heuristics.
    """

    def parse(self, date_range_key: str, filters: dict | None = None) -> tuple[date, date]:
        """Parse a date range key and return (date_from, date_to).

        Args:
            date_range_key: One of the supported range keys.
            filters: Optional filter dict containing custom_start / custom_end for 'custom' ranges.

        Returns:
            Tuple of (date_from, date_to) as date objects.

        Raises:
            ValueError: If date_range_key is unknown or custom dates are invalid.

        Examples:
            >>> dp = DateParser()
            >>> from_d, to_d = dp.parse('Q1')
            >>> from_d.month, to_d.month
            (1, 3)
            >>> from_d2, to_d2 = dp.parse('Q3')
            >>> from_d2.month, to_d2.month
            (7, 9)
        """
        today = date.today()
        key = (date_range_key or 'this_month').strip().lower()

        # Normalize Q-labels before lowercasing lookup
        upper_key = date_range_key.strip() if date_range_key else 'this_month'

        dispatch = {
            'today': self._today,
            'this_week': self._this_week,
            'this_month': self._this_month,
            'last_month': self._last_month,
            'last_week': self._last_week,
            'this_quarter': self._this_quarter,
            'last_quarter': self._last_quarter,
            'q1': self._q1,
            'q2': self._q2,
            'q3': self._q3,
            'q4': self._q4,
            'this_year': self._this_year,
            'custom': lambda t: self._custom(t, filters or {}),
        }

        handler = dispatch.get(key) or dispatch.get(upper_key.lower())
        if not handler:
            _logger.warning('Unknown date_range_key "%s", defaulting to this_month', date_range_key)
            handler = self._this_month

        return handler(today)

    # --- Individual handlers ---

    def _today(self, today: date) -> tuple[date, date]:
        return today, today

    def _this_week(self, today: date) -> tuple[date, date]:
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
        return start, end

    def _last_week(self, today: date) -> tuple[date, date]:
        start = today - timedelta(days=today.weekday() + 7)
        end = start + timedelta(days=6)
        return start, end

    def _this_month(self, today: date) -> tuple[date, date]:
        start = today.replace(day=1)
        end = (start + relativedelta(months=1)) - timedelta(days=1)
        return start, end

    def _last_month(self, today: date) -> tuple[date, date]:
        start = (today.replace(day=1) - relativedelta(months=1))
        end = today.replace(day=1) - timedelta(days=1)
        return start, end

    def _this_quarter(self, today: date) -> tuple[date, date]:
        q = (today.month - 1) // 3
        start = date(today.year, q * 3 + 1, 1)
        end = (start + relativedelta(months=3)) - timedelta(days=1)
        return start, end

    def _last_quarter(self, today: date) -> tuple[date, date]:
        q = (today.month - 1) // 3
        if q == 0:
            start = date(today.year - 1, 10, 1)
        else:
            start = date(today.year, (q - 1) * 3 + 1, 1)
        end = (start + relativedelta(months=3)) - timedelta(days=1)
        return start, end

    def _q1(self, today: date) -> tuple[date, date]:
        return date(today.year, 1, 1), date(today.year, 3, 31)

    def _q2(self, today: date) -> tuple[date, date]:
        return date(today.year, 4, 1), date(today.year, 6, 30)

    def _q3(self, today: date) -> tuple[date, date]:
        return date(today.year, 7, 1), date(today.year, 9, 30)

    def _q4(self, today: date) -> tuple[date, date]:
        return date(today.year, 10, 1), date(today.year, 12, 31)

    def _this_year(self, today: date) -> tuple[date, date]:
        return date(today.year, 1, 1), date(today.year, 12, 31)

    def _custom(self, today: date, filters: dict) -> tuple[date, date]:
        """Parse custom start/end from filters dict.

        Args:
            today: Today's date (unused but kept for consistent signature).
            filters: Must contain 'custom_start' and 'custom_end' as ISO strings (YYYY-MM-DD).
        """
        try:
            start_str = filters.get('custom_start', '')
            end_str = filters.get('custom_end', '')
            if not start_str or not end_str:
                raise ValueError('custom_start and custom_end must be provided for custom range')
            from_date = date.fromisoformat(start_str)
            to_date = date.fromisoformat(end_str)
            if from_date > to_date:
                raise ValueError(f'custom_start {start_str} is after custom_end {end_str}')
            return from_date, to_date
        except (ValueError, TypeError) as e:
            _logger.error('Custom date parsing error: %s — falling back to this_month', e)
            return self._this_month(today)
