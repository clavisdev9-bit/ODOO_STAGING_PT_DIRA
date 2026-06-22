import json
import logging
import hashlib
import hmac
from functools import wraps

from odoo import http, fields
from odoo.http import request, Response

_logger = logging.getLogger(__name__)


def _json_response(data, status=200):
    return Response(
        json.dumps(data),
        status=status,
        mimetype='application/json',
    )


def _verify_bearer(func):
    """Decorator: validate Bearer token from TMS backend."""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        auth_header = request.httprequest.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return _json_response({'success': False, 'error': 'Missing Bearer token'}, 401)
        token = auth_header[7:]
        expected = request.env['ir.config_parameter'].sudo().get_param('tms.webhook.secret')
        if not expected or not hmac.compare_digest(token, expected):
            return _json_response({'success': False, 'error': 'Invalid token'}, 401)
        return func(self, *args, **kwargs)
    return wrapper


def _verify_hmac(func):
    """Decorator: validate HMAC-SHA256 signature from Odoo→TMS direction."""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        signature = request.httprequest.headers.get('X-TMS-Signature', '')
        secret = request.env['ir.config_parameter'].sudo().get_param('tms.hmac.secret')
        if not secret:
            return _json_response({'success': False, 'error': 'HMAC secret not configured'}, 500)
        body = request.httprequest.get_data()
        expected_sig = hmac.HMAC(
            secret.encode(), body, hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(f'sha256={expected_sig}', signature):
            return _json_response({'success': False, 'error': 'Invalid HMAC signature'}, 401)
        return func(self, *args, **kwargs)
    return wrapper


class TmsWebhookController(http.Controller):

    # ------------------------------------------------------------------ #
    # T5: GPS Update from TMS → Odoo (store for dashboard display)
    # ------------------------------------------------------------------ #
    @http.route('/tms/webhook/gps-update', type='json', auth='none', methods=['POST'], csrf=False)
    @_verify_bearer
    def gps_update(self, **kwargs):
        """
        T5: Receive GPS position update from TMS backend.
        payload: { vehicle_id(odoo), order_id(tms), lat, lng, speed_kmh, timestamp }
        """
        try:
            payload = request.get_json_data()
        except Exception:
            return _json_response({'success': False, 'error': 'Invalid JSON'}, 400)

        vehicle_id = payload.get('odoo_vehicle_id')
        lat = payload.get('lat')
        lng = payload.get('lng')

        if not all([vehicle_id, lat, lng]):
            return _json_response({'success': False, 'error': 'Missing required fields: odoo_vehicle_id, lat, lng'}, 400)

        # Update the fleet vehicle's last known position
        vehicle = request.env['fleet.vehicle'].sudo().browse(int(vehicle_id))
        if not vehicle.exists():
            return _json_response({'success': False, 'error': f'Vehicle {vehicle_id} not found'}, 404)

        # Store GPS on related picking (in_transit pickings for this vehicle)
        picking_ref = payload.get('tms_order_picking_id')
        if picking_ref:
            picking = request.env['stock.picking'].sudo().browse(int(picking_ref))
            if picking.exists() and picking.tms_status in ('assigned', 'picked_up', 'in_transit'):
                picking.write({
                    'tms_status': 'in_transit',
                    'tms_sync_date': fields.Datetime.now(),
                })

        request.env['tms.sync.log'].sudo().log(
            trigger_code='T5',
            direction='tms_to_odoo',
            status='success',
            request_payload=json.dumps(payload),
        )

        return _json_response({'success': True, 'message': 'GPS update received'})

    # ------------------------------------------------------------------ #
    # T6: Delivery Complete from TMS → validate picking + create invoice
    # ------------------------------------------------------------------ #
    @http.route('/tms/webhook/delivery-complete', type='json', auth='none', methods=['POST'], csrf=False)
    @_verify_bearer
    def delivery_complete(self, **kwargs):
        """
        T6: TMS notifies delivery is complete.
        payload: {
            tms_tracking_number, picking_id,
            actual_cost, pod_photos[], signature_url, pod_note, pod_date,
            qty_done_lines: [{move_id, qty_done}]
        }
        """
        try:
            payload = request.get_json_data()
        except Exception:
            return _json_response({'success': False, 'error': 'Invalid JSON'}, 400)

        picking_id = payload.get('picking_id')
        tracking_number = payload.get('tms_tracking_number')

        # Resolve picking
        picking = None
        if picking_id:
            picking = request.env['stock.picking'].sudo().browse(int(picking_id))
        elif tracking_number:
            picking = request.env['stock.picking'].sudo().search(
                [('tms_tracking_number', '=', tracking_number)], limit=1)

        if not picking or not picking.exists():
            return _json_response({'success': False, 'error': 'Picking not found'}, 404)

        if picking.state == 'done':
            return _json_response({'success': True, 'message': 'Picking already validated'})

        if picking.state == 'cancel':
            return _json_response({'success': False, 'error': 'Picking is cancelled'}, 400)

        try:
            picking.tms_confirm_delivery(payload)
        except Exception as e:
            _logger.exception('T6: Error confirming delivery for picking %s', picking.name)
            request.env['tms.sync.log'].sudo().log(
                trigger_code='T6',
                direction='tms_to_odoo',
                picking=picking,
                status='error',
                request_payload=json.dumps(payload),
                error_message=str(e),
            )
            return _json_response({'success': False, 'error': str(e)}, 500)

        return _json_response({
            'success': True,
            'message': 'Delivery confirmed, picking validated',
            'picking_name': picking.name,
            'invoice_created': bool(picking.sale_id and picking.sale_id.invoice_ids),
        })

    # ------------------------------------------------------------------ #
    # T7: Punch-out → Auto-create hr.expense
    # ------------------------------------------------------------------ #
    @http.route('/tms/webhook/expense-create', type='json', auth='none', methods=['POST'], csrf=False)
    @_verify_bearer
    def expense_create(self, **kwargs):
        """
        T7: Driver punches out — auto-create hr.expense in Odoo.
        payload: {
            tms_route_ref, driver_odoo_employee_id,
            expense_date, plate_number,
            fuel_cost, driver_allowance, depreciation, maintenance,
            total_km, duration_hours
        }
        """
        try:
            payload = request.get_json_data()
        except Exception:
            return _json_response({'success': False, 'error': 'Invalid JSON'}, 400)

        employee_id = payload.get('driver_odoo_employee_id')
        expense_date = payload.get('expense_date')
        plate_number = payload.get('plate_number', '')

        if not employee_id:
            return _json_response({'success': False, 'error': 'driver_odoo_employee_id required'}, 400)

        employee = request.env['hr.employee'].sudo().browse(int(employee_id))
        if not employee.exists():
            return _json_response({'success': False, 'error': f'Employee {employee_id} not found'}, 404)

        expense_name = f"Vehicle Op - {plate_number} ({expense_date or fields.Date.today()})"
        tms_route_ref = payload.get('tms_route_ref', '')

        cost_lines = {
            'Fuel Cost': payload.get('fuel_cost', 0.0),
            'Driver Allowance': payload.get('driver_allowance', 0.0),
            'Depreciation': payload.get('depreciation', 0.0),
            'Maintenance': payload.get('maintenance', 0.0),
        }

        idr = request.env.ref('base.IDR', raise_if_not_found=False)
        expense_product = request.env['ir.config_parameter'].sudo().get_param('tms.expense.product_id')
        product = request.env['product.product'].sudo().browse(int(expense_product)) if expense_product else False

        created_expenses = []
        for label, amount in cost_lines.items():
            if amount <= 0:
                continue
            expense = request.env['hr.expense'].sudo().create({
                'name': f'{expense_name} — {label}',
                'employee_id': employee.id,
                'date': expense_date or fields.Date.today(),
                'unit_amount': amount,
                'quantity': 1,
                'currency_id': idr.id if idr else False,
                'product_id': product.id if product else False,
                'description': f'TMS Route: {tms_route_ref} | km: {payload.get("total_km", 0)} | hours: {payload.get("duration_hours", 0)}',
            })
            created_expenses.append(expense.id)

        request.env['tms.sync.log'].sudo().log(
            trigger_code='T7',
            direction='tms_to_odoo',
            status='success',
            request_payload=json.dumps(payload),
            response_payload=json.dumps({'expense_ids': created_expenses}),
            tms_tracking_number=tms_route_ref,
        )

        return _json_response({
            'success': True,
            'message': f'{len(created_expenses)} expense line(s) created',
            'expense_ids': created_expenses,
        })

    # ------------------------------------------------------------------ #
    # Health check
    # ------------------------------------------------------------------ #
    @http.route('/tms/webhook/health', type='http', auth='none', methods=['GET'], csrf=False)
    def health_check(self, **kwargs):
        return _json_response({'status': 'ok', 'module': 'tms_integration'})
