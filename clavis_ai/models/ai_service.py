import time
import logging

import requests

from odoo import api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

_DEMO_SCENARIOS = [
    {
        'keywords': ['customer 7', 'partner 7', 'partner #7', 'john doe'],
        'tool': 'get_customer_info(partner_id=7)',
        'answer': "Here's the profile for **Partner #7**:",
        'action_required': False,
        'action_details': {
            'type': 'info',
            'display': {
                'Name': 'John Doe',
                'Company': 'TechCorp Ltd',
                'Email': 'j.doe@techcorp.io',
                'Credit Limit': '$5,000',
                'Status': 'Active',
            },
        },
    },
    {
        'keywords': ['create quotation', 'new quotation', 'buat quotation', 'buat order'],
        'tool': 'request_create_sale_order(partner_id=7, products=[...])',
        'answer': "I've prepared a quotation draft for John Doe. Please confirm to create the record in Odoo:",
        'action_required': True,
        'action_details': {
            'action': 'create_sale_order',
            'type': 'action',
            'params': {'partner_id': 7, 'product_ids': []},
            'status': 'pending_confirmation',
            'display': {
                'Customer': 'John Doe (#7)',
                'Products': 'Laptop Pro x1',
                'Pricelist': 'USD Public',
                'Company': 'TechCorp Ltd',
            },
        },
    },
    {
        'keywords': ['open quotation', 'draft quotation', 'my quotation', 'open order'],
        'tool': 'get_sale_orders(state=draft)',
        'answer': "You currently have **3 draft quotations** open:",
        'action_required': False,
        'action_details': {
            'type': 'list',
            'items': [
                'SO-0040 — Acme Corp — $1,200',
                'SO-0041 — Globex — $3,400',
                'SO-0042 — TechCorp — $890',
            ],
        },
    },
    {
        'keywords': ['product', 'laptop', 'item', 'catalog', 'search product'],
        'tool': 'search_products(keyword="laptop")',
        'answer': "I found **3 products** matching your query:",
        'action_required': False,
        'action_details': {
            'type': 'list',
            'items': [
                'Laptop Pro — $1,200 — In Stock: 15 units',
                'Laptop Air — $950 — In Stock: 8 units',
                'Laptop Gaming — $1,800 — In Stock: 3 units',
            ],
        },
    },
]


class ClavisAiService(models.AbstractModel):
    _name = 'clavis.ai.service'
    _description = 'Clavis AI Service Client'

    @api.model
    def _get_config(self):
        ICP = self.env['ir.config_parameter'].sudo()
        return {
            'url': ICP.get_param('clavis_ai.service_url', '').strip(),
            'api_key': ICP.get_param('clavis_ai.api_key', ''),
            'enabled': ICP.get_param('clavis_ai.enabled', 'False') == 'True',
        }

    @api.model
    def send_chat(self, session_id, user_id, message, context=None):
        config = self._get_config()
        if not config['enabled'] or not config['url']:
            return self._demo_response(message)

        try:
            start = time.time()
            headers = {
                'X-API-Key': config['api_key'],
                'Content-Type': 'application/json',
            }
            payload = {
                'session_id': session_id,
                'user_id': user_id,
                'message': message,
                'context': context or {},
            }
            resp = requests.post(
                f"{config['url'].rstrip('/')}/chat",
                json=payload,
                headers=headers,
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            latency = int((time.time() - start) * 1000)
            return {
                'answer': data.get('answer', ''),
                'action_required': data.get('action_required', False),
                'action_details': data.get('action_details'),
                'tool_called': data.get('tool_called'),
                'latency_ms': latency,
            }
        except requests.exceptions.ConnectionError:
            _logger.warning("Clavis AI service unreachable at %s — using demo mode", config['url'])
            return self._error_response(
                f"Cannot connect to Clavis AI service at `{config['url']}`.\n"
                "Check the URL in *Settings → Clavis AI* or disable the service to use demo mode."
            )
        except requests.exceptions.Timeout:
            _logger.warning("Clavis AI service timed out")
            return self._error_response("Clavis AI service timed out after 60 seconds. Please try again.")
        except requests.exceptions.HTTPError as e:
            _logger.error("Clavis AI HTTP error: %s", e)
            return self._error_response(
                f"Clavis AI service returned HTTP {e.response.status_code}.\n"
                "Check that the service URL and `/chat` endpoint are correct in *Settings → Clavis AI*."
            )
        except requests.exceptions.RequestException as e:
            _logger.error("Clavis AI request error: %s", e)
            return self._error_response(f"Clavis AI request failed: {e}")

    @api.model
    def _demo_response(self, message):
        msg_lower = message.lower()
        for scenario in _DEMO_SCENARIOS:
            if any(kw in msg_lower for kw in scenario['keywords']):
                return {
                    'answer': scenario['answer'],
                    'action_required': scenario['action_required'],
                    'action_details': scenario.get('action_details'),
                    'tool_called': scenario.get('tool'),
                    'latency_ms': 0,
                }
        return {
            'answer': (
                "Clavis AI is running in **demo mode**. "
                "Configure the AI service URL in *Settings → Clavis AI* to enable the full AI backend.\n\n"
                "Try asking:\n"
                "- *show me customer 7*\n"
                "- *create quotation for john doe*\n"
                "- *what are my open quotations*"
            ),
            'action_required': False,
            'action_details': None,
            'tool_called': None,
            'latency_ms': 0,
        }

    @api.model
    def _error_response(self, message):
        return {
            'answer': message,
            'action_required': False,
            'action_details': None,
            'tool_called': None,
            'latency_ms': 0,
        }

    @api.model
    def execute_action(self, action_details):
        action = action_details.get('action')
        params = action_details.get('params', {})

        if action == 'create_sale_order':
            return self._create_sale_order(params)
        raise UserError(f"Unknown action type: {action}")

    @api.model
    def _create_sale_order(self, params):
        partner_id = params.get('partner_id')
        product_ids = params.get('product_ids', [])

        if not partner_id:
            raise UserError("Partner ID is required to create a sale order.")

        partner = self.env['res.partner'].browse(partner_id)
        if not partner.exists():
            raise UserError(f"Partner with ID {partner_id} not found.")

        order_lines = []
        for pid in product_ids:
            product = self.env['product.product'].browse(pid)
            if product.exists():
                order_lines.append((0, 0, {
                    'product_id': product.id,
                    'product_uom_qty': 1,
                    'price_unit': product.lst_price,
                }))

        sale_order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': order_lines,
        })

        return {
            'model': 'sale.order',
            'id': sale_order.id,
            'name': sale_order.name,
        }
