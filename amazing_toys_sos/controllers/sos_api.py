import hmac
import json
import logging
import datetime as _dt

from odoo import http, fields, SUPERUSER_ID
from odoo.http import request

_logger = logging.getLogger(__name__)

_API_KEY_PARAM = 'sos.api.key'


def _check_api_key(req):
    """Return True if the request carries a valid SOS API key.

    Uses hmac.compare_digest to prevent timing-oracle attacks.
    """
    expected = (
        req.env['ir.config_parameter']
        .sudo()
        .get_param(_API_KEY_PARAM, default=False)
    )
    if not expected:
        _logger.warning('[SOS API] %s not configured in system parameters', _API_KEY_PARAM)
        return False
    provided = req.httprequest.headers.get('X-SOS-API-KEY', '')
    # Timing-safe comparison — prevents key enumeration via response latency.
    return hmac.compare_digest(provided.encode(), expected.encode())


def _json_error(message, status=400):
    return request.make_json_response({'error': message}, status=status)


class SosApiController(http.Controller):

    @http.route(
        '/api/sos/order',
        type='http',
        auth='none',
        methods=['POST'],
        csrf=False,
        save_session=False,
    )
    def create_order(self, **_kwargs):
        """
        POST /api/sos/order
        Headers:
            X-SOS-API-KEY: <key>
            Content-Type: application/json
        Body: {
            "table": "T1",
            "items": [
                {"product_id": 42, "qty": 2, "price_unit": 15000},
                ...
            ],
            "customer_id": 123,
            "note": "No spicy sauce",
            "warehouse_id": 1          (optional, defaults to first warehouse)
            "pricelist_id": 1          (optional)
        }
        Response 200: {
            "sale_order_id": 456,
            "name": "S00123",
            "status": "confirmed"
        }
        """
        # ---- auth ----
        if not _check_api_key(request):
            return _json_error('Unauthorized: invalid or missing X-SOS-API-KEY', status=401)

        # ---- parse body ----
        try:
            payload = json.loads(request.httprequest.data or '{}')
        except json.JSONDecodeError:
            return _json_error('Invalid JSON body')

        table = payload.get('table') or ''
        items = payload.get('items') or []
        customer_id = payload.get('customer_id')
        note = payload.get('note') or ''
        warehouse_id = payload.get('warehouse_id')
        pricelist_id = payload.get('pricelist_id')
        txn_number = payload.get('txn_number') or ''

        # ---- validate ----
        if not table:
            return _json_error('Missing required field: table')
        if not items:
            return _json_error('Missing required field: items (must be non-empty)')
        if not customer_id:
            return _json_error('Missing required field: customer_id')

        # Run all DB operations as SUPERUSER to avoid ACL issues on an auth='none' endpoint.
        env = request.env(user=SUPERUSER_ID)

        partner = env['res.partner'].browse(customer_id)
        if not partner.exists():
            return _json_error(f'customer_id {customer_id} not found', status=422)

        # ---- build order lines ----
        order_lines = []
        for idx, item in enumerate(items):
            product_id = item.get('product_id')
            qty = item.get('qty') or item.get('product_uom_qty') or 0
            price_unit = item.get('price_unit')

            if not product_id:
                return _json_error(f'items[{idx}]: missing product_id')
            if not qty or float(qty) <= 0:
                return _json_error(f'items[{idx}]: qty must be > 0')

            product = env['product.product'].browse(int(product_id))
            if not product.exists():
                return _json_error(f'items[{idx}]: product_id {product_id} not found', status=422)

            line_vals = {
                'product_id': product.id,
                'product_uom_qty': float(qty),
            }
            if price_unit is not None:
                line_vals['price_unit'] = float(price_unit)

            order_lines.append((0, 0, line_vals))

        # ---- resolve optional fields ----
        if not warehouse_id:
            wh = env['stock.warehouse'].search([('company_id', '=', env.company.id)], limit=1)
            warehouse_id = wh.id if wh else False

        # ---- create SO ----
        session_ref = f'SOS-{table}-{_dt.datetime.now().strftime("%Y%m%d%H%M%S")}'

        # Use TXN from frontend; generate via ir.sequence if absent.
        if not txn_number:
            txn_number = env['sale.order']._sos_generate_txn_number()

        so_vals = {
            'partner_id': partner.id,
            'origin': session_ref,
            'note': note,
            'order_line': order_lines,
            'sos_txn_number': txn_number,
        }
        if warehouse_id:
            so_vals['warehouse_id'] = warehouse_id
        if pricelist_id:
            pricelist = env['product.pricelist'].browse(int(pricelist_id))
            if pricelist.exists():
                so_vals['pricelist_id'] = pricelist.id

        try:
            order = env['sale.order'].create(so_vals)
        except Exception as exc:
            _logger.exception('[SOS API] Failed to create sale.order: %s', exc)
            return _json_error(f'Order creation failed: {exc}', status=500)

        _logger.info('[SOS API] Created SO %s (id=%d) for table %s', order.name, order.id, table)

        return request.make_json_response({
            'sale_order_id': order.id,
            'name': order.name,
            'txn_number': order.sos_txn_number,
            'origin': order.origin,
            'status': order.state,
        })

    @http.route(
        '/api/sos/order/<int:order_id>',
        type='http',
        auth='none',
        methods=['GET'],
        csrf=False,
        save_session=False,
    )
    def get_order(self, order_id, **_kwargs):
        """GET status of a specific SOS order."""
        if not _check_api_key(request):
            return _json_error('Unauthorized', status=401)

        env = request.env(user=SUPERUSER_ID)
        order = env['sale.order'].browse(order_id)
        if not order.exists():
            return _json_error(f'Order {order_id} not found', status=404)

        invoices = order.invoice_ids.filtered(lambda i: i.move_type == 'out_invoice')
        return request.make_json_response({
            'sale_order_id': order.id,
            'name': order.name,
            'state': order.state,
            'invoice_status': order.invoice_status,
            'sos_order': order.sos_order,
            'invoices': [
                {'id': inv.id, 'name': inv.name, 'state': inv.state}
                for inv in invoices
            ],
        })
