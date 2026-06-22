# -*- coding: utf-8 -*-
"""HTTP controllers for AI Report Agent.

Exposes:
  POST /ai/report      — main report generation endpoint
  GET  /mcp/tools      — MCP tool schema discovery
  POST /mcp/call       — MCP tool dispatch
"""
import json
import logging
import time
from functools import wraps
from collections import defaultdict

from odoo import http
from odoo.http import request, Response

_logger = logging.getLogger(__name__)

# Rate limiting: max 10 requests per minute per user
_RATE_LIMIT_WINDOW = 60
_RATE_LIMIT_MAX = 10
_rate_counters: dict = defaultdict(list)


def _check_rate_limit(user_id: int) -> bool:
    """Return True if request is allowed, False if rate-limited."""
    now = time.time()
    window_start = now - _RATE_LIMIT_WINDOW
    calls = _rate_counters[user_id]
    # Prune old entries
    _rate_counters[user_id] = [t for t in calls if t > window_start]
    if len(_rate_counters[user_id]) >= _RATE_LIMIT_MAX:
        return False
    _rate_counters[user_id].append(now)
    return True


class AIReportController(http.Controller):
    """Main controller for AI-powered report generation."""

    @http.route('/ai/report', type='json', auth='user', methods=['POST'], csrf=False)
    def generate_report(self, **kwargs) -> dict:
        """Generate a report from natural language input.

        Request body (JSON):
            {
                "message": "unpaid invoices this month",
                "session_id": "optional-session-id",
                "output_formats": ["pdf", "xlsx"]   // optional, defaults to both
            }

        Returns:
            {
                "status": "ok",
                "intent": {...},
                "download_url": "/web/content/...",
                "download_urls": {"pdf": "...", "xlsx": "..."},
                "insight": "...",
                "history_id": 123,
                "needs_clarification": false,
                "clarification_question": null
            }
        """
        user_id = request.env.user.id

        if not _check_rate_limit(user_id):
            return {
                'status': 'error',
                'error': 'Rate limit exceeded. Maximum 10 requests per minute.',
            }

        # For type='json' routes Odoo unwraps JSON-RPC params into **kwargs directly
        user_message = (kwargs.get('message') or '').strip()
        session_id = kwargs.get('session_id') or ''
        output_formats = kwargs.get('output_formats') or ['pdf', 'xlsx']

        if not user_message:
            return {'status': 'error', 'error': 'Message is required.'}

        start_time = time.time()

        # Create history record immediately
        history = request.env['ai.report.history'].create({
            'user_message': user_message,
            'session_id': session_id,
            'status': 'processing',
        })

        try:
            result = self._run_pipeline(user_message, session_id, output_formats, history)
            elapsed_ms = int((time.time() - start_time) * 1000)
            history.write({'processing_time_ms': elapsed_ms})
            return result

        except Exception as e:
            _logger.exception('Report generation failed for message: %s', user_message)
            history.write({
                'status': 'error',
                'error_message': str(e),
            })
            return {
                'status': 'error',
                'error': str(e),
                'history_id': history.id,
            }

    def _run_pipeline(
        self,
        user_message: str,
        session_id: str,
        output_formats: list,
        history: object,
    ) -> dict:
        """Execute the full AI → Rule Engine → Builder → Generator pipeline."""
        from ..services.ai_interpreter import AIInterpreter, InterpretError, LLMConnectionError
        from ..services.rule_engine import RuleEngine
        from ..services.report_builder import ReportBuilder
        from ..services.excel_generator import ExcelGenerator
        from ..services.pdf_generator import PDFGenerator

        env = request.env

        # Fetch context from recent history for continuity
        recent_history = env['ai.report.history'].search([
            ('session_id', '=', session_id),
            ('status', '=', 'done'),
        ], limit=3, order='create_date desc') if session_id else env['ai.report.history'].browse([])

        # Layer 2: AI Interpretation
        interpreter = AIInterpreter(env)
        try:
            raw_intent = interpreter.interpret(user_message, list(recent_history))
        except LLMConnectionError as e:
            # Surface configuration/connectivity errors directly — do not hide them
            _logger.error('LLM connection error: %s', e)
            history.write({'status': 'error', 'error_message': str(e)})
            raise
        except InterpretError as e:
            _logger.warning('AI parse error: %s — using safe default', e)
            raw_intent = interpreter._default_intent()

        # Inject output_formats from request
        raw_intent['output_formats'] = output_formats

        # Layer 3: Rule Engine validation
        engine = RuleEngine(env)
        validated_intent = engine.validate_and_expand(raw_intent)

        # Check async threshold
        config = env['ai.report.config'].get_active_config()
        estimated_rows = env[validated_intent['model']].search_count(
            validated_intent.get('domain', [])
        ) if not isinstance(validated_intent['model'], list) else 0

        history.write({
            'interpreted_intent': json.dumps(raw_intent, default=str),
            'report_type': validated_intent.get('intent', 'unknown'),
            'ai_confidence': raw_intent.get('confidence', 0.0),
        })

        if estimated_rows > config.async_threshold:
            return self._enqueue_async(validated_intent, history)

        # Layer 5: Build report data
        builder = ReportBuilder(env)
        result = builder.build(validated_intent)

        # Update history with dates
        history.write({
            'date_from': result.date_from,
            'date_to': result.date_to,
        })

        # Layer 6: Generate files
        attachments = []
        download_urls = {}

        if 'xlsx' in output_formats:
            excel_gen = ExcelGenerator(env)
            xlsx_bytes = excel_gen.generate(result)
            xlsx_att = env['ir.attachment'].create({
                'name': f'report_{history.id}.xlsx',
                'type': 'binary',
                'datas': xlsx_bytes,
                'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'res_model': 'ai.report.history',
                'res_id': history.id,
            })
            attachments.append(xlsx_att.id)
            download_urls['xlsx'] = f'/web/content/{xlsx_att.id}?download=true'

        if 'pdf' in output_formats:
            try:
                pdf_gen = PDFGenerator(env)
                pdf_bytes = pdf_gen.generate(result)
                pdf_att = env['ir.attachment'].create({
                    'name': f'report_{history.id}.pdf',
                    'type': 'binary',
                    'datas': pdf_bytes,
                    'mimetype': 'application/pdf',
                    'res_model': 'ai.report.history',
                    'res_id': history.id,
                })
                attachments.append(pdf_att.id)
                download_urls['pdf'] = f'/web/content/{pdf_att.id}?download=true'
            except Exception as pdf_err:
                _logger.warning('PDF generation failed (non-fatal): %s', pdf_err)

        history.write({
            'status': 'done',
            'attachment_ids': [(4, att_id) for att_id in attachments],
            'insight_text': result.insight_text,
        })

        # Post chatter message with download links
        links = ' | '.join(
            f'<a href="{url}">{fmt.upper()}</a>'
            for fmt, url in download_urls.items()
        )
        history.message_post(
            body=f'Report ready: {links}',
            message_type='notification',
        )

        return {
            'status': 'ok',
            'intent': validated_intent,
            'download_url': download_urls.get('pdf') or download_urls.get('xlsx', ''),
            'download_urls': download_urls,
            'insight': result.insight_text,
            'history_id': history.id,
            'needs_clarification': validated_intent.get('needs_clarification', False),
            'clarification_question': validated_intent.get('clarification_question'),
            'record_count': len(result.raw_records),
            'date_from': result.date_from.isoformat(),
            'date_to': result.date_to.isoformat(),
        }

    def _enqueue_async(self, validated_intent: dict, history: object) -> dict:
        """Queue the job for async processing and return immediately."""
        env = request.env
        env['ai.report.queue'].create({
            'history_id': history.id,
            'payload': json.dumps(validated_intent, default=str),
            'status': 'pending',
        })
        history.write({'status': 'processing'})
        return {
            'status': 'queued',
            'message': 'Report queued for async processing due to large dataset.',
            'history_id': history.id,
            'needs_clarification': validated_intent.get('needs_clarification', False),
            'clarification_question': validated_intent.get('clarification_question'),
        }


class MCPController(http.Controller):
    """MCP-compatible tool server for external AI agent integration."""

    @http.route('/mcp/tools', type='http', auth='user', methods=['GET'], csrf=False)
    def get_tools(self, **kwargs) -> Response:
        """Return MCP tool schema for discovery.

        Returns:
            JSON response with tool definitions.
        """
        from ..services.mcp_bridge import OdooMCPBridge
        bridge = OdooMCPBridge(request.env)
        schema = bridge.get_tool_schema()
        return Response(
            json.dumps(schema, indent=2),
            content_type='application/json',
            status=200,
        )

    @http.route('/mcp/call', type='json', auth='user', methods=['POST'], csrf=False)
    def call_tool(self, **kwargs) -> dict:
        """Dispatch an MCP tool call.

        Request body:
            {
                "tool_name": "get_report",
                "arguments": {"message": "sales this month"}
            }

        Returns:
            MCP-standard response with 'content' key.
        """
        tool_name = kwargs.get('tool_name') or ''
        arguments = kwargs.get('arguments') or {}

        if not tool_name:
            return {
                'isError': True,
                'content': [{'type': 'text', 'text': 'tool_name is required'}],
            }

        from ..services.mcp_bridge import OdooMCPBridge
        bridge = OdooMCPBridge(request.env)
        return bridge.dispatch(tool_name, arguments)
