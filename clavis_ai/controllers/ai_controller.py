import logging
import threading
import uuid
from datetime import date

import odoo
import odoo.api

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class ClavisAiController(http.Controller):

    # ── Chat ──────────────────────────────────────────────────────────────────

    @http.route('/clavis/chat/send', type='json', auth='user')
    def send_message(self, message, session_id=None, context=None):
        if not session_id:
            session_id = f"sess_{uuid.uuid4().hex[:8]}"

        uid = request.env.uid
        log = request.env['clavis.ai.log'].sudo().create({
            'session_id': session_id,
            'user_id': uid,
            'message': message,
            'status': 'pending',
            'context_data': context or {},
        })
        log_id = log.id
        db = request.env.cr.dbname

        def _process():
            try:
                with odoo.registry(db).cursor() as cr:
                    env = odoo.api.Environment(cr, uid, {})
                    result = env['clavis.ai.service'].send_chat(
                        session_id, uid, message, context or {}
                    )
                    env['clavis.ai.log'].browse(log_id).write({
                        'status': 'done',
                        'response': result['answer'],
                        'action_required': result.get('action_required', False),
                        'action_details': result.get('action_details'),
                        'tool_called': result.get('tool_called'),
                        'latency_ms': result.get('latency_ms', 0),
                    })
            except Exception as e:
                _logger.error("Clavis AI background error (log %s): %s", log_id, e)
                try:
                    with odoo.registry(db).cursor() as cr:
                        env = odoo.api.Environment(cr, uid, {})
                        env['clavis.ai.log'].browse(log_id).write({
                            'status': 'error',
                            'error_message': str(e),
                        })
                except Exception:
                    _logger.exception("Failed to write error status for log %s", log_id)

        t = threading.Thread(target=_process, daemon=True)
        t.start()

        return {'request_id': log_id, 'session_id': session_id}

    @http.route('/clavis/chat/status/<int:request_id>', type='json', auth='user')
    def get_status(self, request_id):
        log = request.env['clavis.ai.log'].sudo().browse(request_id)
        if not log.exists():
            return {'status': 'error', 'error_message': 'Request not found'}
        return {
            'status': log.status,
            'response': log.response,
            'action_required': log.action_required,
            'action_details': log.action_details,
            'tool_called': log.tool_called,
            'latency_ms': log.latency_ms,
            'error_message': log.error_message,
        }

    @http.route('/clavis/chat/history', type='json', auth='user')
    def get_history(self, session_id):
        logs = request.env['clavis.ai.log'].sudo().search([
            ('session_id', '=', session_id),
            ('status', '!=', 'pending'),
        ], order='create_date asc', limit=50)
        return [{
            'id': log.id,
            'message': log.message,
            'response': log.response,
            'action_required': log.action_required,
            'action_details': log.action_details,
            'tool_called': log.tool_called,
            'status': log.status,
        } for log in logs]

    # ── Action Confirmation ───────────────────────────────────────────────────

    @http.route('/clavis/action/confirm', type='json', auth='user')
    def confirm_action(self, log_id):
        log = request.env['clavis.ai.log'].sudo().browse(log_id)
        if not log.exists() or not log.action_required:
            return {'success': False, 'message': 'No pending action found'}
        try:
            result = request.env['clavis.ai.service'].execute_action(log.action_details)
            log.write({'action_required': False})
            return {'success': True, 'result': result}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    # ── Metrics & Logs ────────────────────────────────────────────────────────

    @http.route('/clavis/metrics', type='json', auth='user')
    def get_metrics(self):
        env = request.env
        today = date.today()
        first_day = today.replace(day=1)

        open_orders = env['sale.order'].sudo().search_count([('state', '=', 'draft')])
        customers = env['res.partner'].sudo().search_count([('customer_rank', '>', 0)])
        ai_requests = env['clavis.ai.log'].sudo().search_count([
            ('user_id', '=', env.uid),
            ('status', '=', 'done'),
        ])

        revenue_orders = env['sale.order'].sudo().search([
            ('state', 'in', ['sale', 'done']),
            ('date_order', '>=', first_day.strftime('%Y-%m-%d')),
        ])
        revenue_mtd = sum(o.amount_total for o in revenue_orders)

        return {
            'open_orders': open_orders,
            'customers': customers,
            'revenue_mtd': revenue_mtd,
            'ai_requests': ai_requests,
        }

    @http.route('/clavis/recent_logs', type='json', auth='user')
    def get_recent_logs(self, limit=10):
        logs = request.env['clavis.ai.log'].sudo().search(
            [('user_id', '=', request.env.uid)],
            order='create_date desc',
            limit=limit,
        )
        return [{
            'id': log.id,
            'create_date': log.create_date.strftime('%H:%M') if log.create_date else '',
            'status': log.status,
            'message': (log.message[:55] + '…') if log.message and len(log.message) > 55 else log.message,
            'tool_called': log.tool_called or '',
            'latency_ms': log.latency_ms or 0,
        } for log in logs]
