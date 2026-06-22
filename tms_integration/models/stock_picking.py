import json
import time
import logging
import requests
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

TMS_STATUS = [
    ('not_sent', 'Not Sent'),
    ('assigned', 'Assigned'),
    ('picked_up', 'Picked Up'),
    ('in_transit', 'In Transit'),
    ('delivered', 'Delivered'),
    ('failed', 'Failed'),
    ('cancelled', 'Cancelled'),
]


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    # --- TMS Core Fields ---
    tms_tracking_number = fields.Char(
        'TMS Tracking Number', copy=False, index=True, readonly=True)
    tms_status = fields.Selection(
        TMS_STATUS, string='TMS Status', default='not_sent',
        copy=False, index=True, tracking=True)
    tms_sync_date = fields.Datetime('Last TMS Sync', copy=False)

    # --- Assignment Fields (written back by TMS) ---
    tms_driver_name = fields.Char('TMS Driver', copy=False)
    tms_vehicle_number = fields.Char('TMS Vehicle Plate', copy=False)
    tms_eta = fields.Datetime('ETA', copy=False)
    tms_actual_cost = fields.Monetary(
        'Actual Shipping Cost (IDR)', copy=False,
        currency_field='tms_currency_id')
    tms_currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.ref('base.IDR', raise_if_not_found=False))

    # --- Proof of Delivery ---
    tms_pod_photos = fields.Text(
        'POD Photo URLs (JSON)', copy=False,
        help='JSON array of S3/MinIO URLs for proof of delivery photos')
    tms_signature_url = fields.Char('Digital Signature URL', copy=False)
    tms_pod_note = fields.Text('Delivery Notes', copy=False)
    tms_pod_date = fields.Datetime('POD Completed At', copy=False)

    # --- Urgency ---
    tms_urgency = fields.Selection([
        ('normal', 'Normal'),
        ('urgent', 'Urgent'),
    ], string='TMS Urgency', default='normal')

    def _compute_tms_pod_photo_list(self):
        for rec in self:
            try:
                rec.tms_pod_photo_count = len(json.loads(rec.tms_pod_photos or '[]'))
            except (json.JSONDecodeError, TypeError):
                rec.tms_pod_photo_count = 0

    tms_pod_photo_count = fields.Integer(
        'POD Photo Count', compute='_compute_tms_pod_photo_list')

    # ------------------------------------------------------------------ #
    # T2: Picking Assigned → send webhook to TMS
    # ------------------------------------------------------------------ #
    def action_assign(self):
        result = super().action_assign()
        for picking in self.filtered(
            lambda p: p.picking_type_code == 'outgoing'
                and p.state == 'assigned'
                and p.tms_status == 'not_sent'
        ):
            picking._tms_trigger_t2()
        return result

    def _tms_trigger_t2(self):
        """T2: Picking assigned — notify TMS."""
        payload = {
            'trigger': 'T2',
            'picking_id': self.id,
            'picking_name': self.name,
            'sale_order': self.sale_id.name if self.sale_id else None,
            'state': self.state,
            'scheduled_date': self.scheduled_date.isoformat() if self.scheduled_date else None,
        }
        self._post_tms_webhook('/api/v1/webhook/odoo/picking-assigned', payload, 'T2')

    # ------------------------------------------------------------------ #
    # T3: Manual "Send to TMS" action
    # ------------------------------------------------------------------ #
    def action_send_to_tms(self):
        """T3: Manual send to TMS — opens wizard for urgency/notes."""
        self.ensure_one()
        if self.picking_type_code != 'outgoing':
            raise UserError('Hanya Delivery Order (outgoing) yang bisa dikirim ke TMS.')
        if self.state in ('done', 'cancel'):
            raise UserError('Tidak bisa mengirim picking yang sudah selesai atau dibatalkan.')
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'tms.send.to.tms.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_picking_id': self.id},
        }

    def _do_send_to_tms(self, urgency='normal', notes=False):
        """Execute T3: POST to TMS backend."""
        self.ensure_one()
        sale = self.sale_id

        payload = {
            'trigger': 'T3',
            'picking_id': self.id,
            'picking_name': self.name,
            'sale_order': sale.name if sale else None,
            'partner_name': self.partner_id.name,
            'partner_phone': self.partner_id.phone or self.partner_id.mobile or None,
            'delivery_address': self._format_address(self.partner_id),
            'delivery_lat': self.partner_id.partner_latitude or None,
            'delivery_lng': self.partner_id.partner_longitude or None,
            'urgency': urgency,
            'notes': notes,
            'scheduled_date': self.scheduled_date.isoformat() if self.scheduled_date else None,
            'priority': self.priority,
            'move_lines': self._tms_get_move_lines(),
        }

        tms_url = self._get_tms_config('tms.backend.url')
        api_key = self._get_tms_config('tms.api.key')
        if not tms_url or not api_key:
            raise UserError('TMS Backend URL atau API Key belum dikonfigurasi.\nPeriksa Settings → Technical → System Parameters.')

        url = tms_url.rstrip('/') + '/api/v1/orders/send-to-tms'
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
        }
        start = time.time()
        status = 'error'
        http_code = None
        response_text = None
        error_msg = None
        tracking_number = None

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            http_code = resp.status_code
            response_text = resp.text
            if resp.ok:
                data = resp.json().get('data', {})
                tracking_number = data.get('tracking_number')
                self.write({
                    'tms_tracking_number': tracking_number,
                    'tms_status': 'assigned',
                    'tms_driver_name': data.get('driver_name'),
                    'tms_vehicle_number': data.get('vehicle', '').split('(')[-1].replace(')', '').strip(),
                    'tms_eta': data.get('eta'),
                    'tms_sync_date': fields.Datetime.now(),
                    'tms_urgency': urgency,
                })
                status = 'success'
            else:
                error_msg = f'HTTP {resp.status_code}: {resp.text[:500]}'
        except requests.exceptions.Timeout:
            error_msg = 'TMS request timeout after 10s'
        except Exception as e:
            error_msg = str(e)

        duration_ms = int((time.time() - start) * 1000)

        self.env['tms.sync.log'].log(
            trigger_code='T3',
            direction='odoo_to_tms',
            picking=self,
            sale_order=sale,
            status=status,
            request_payload=json.dumps(payload),
            response_payload=response_text,
            error_message=error_msg,
            http_status_code=http_code,
            duration_ms=duration_ms,
            tms_tracking_number=tracking_number,
        )

        if status == 'error':
            raise UserError(f'Gagal mengirim ke TMS:\n{error_msg}')

        return tracking_number

    # ------------------------------------------------------------------ #
    # T6: TMS notifies delivery complete → validate picking + create invoice
    # ------------------------------------------------------------------ #
    def tms_confirm_delivery(self, payload):
        """
        Called by webhook controller on T6.
        payload keys: tracking_number, actual_cost, pod_photos, signature_url,
                      pod_note, pod_date, qty_done_lines[{move_id, qty_done}]
        """
        self.ensure_one()
        _logger.info('T6 delivery confirm for picking %s', self.name)

        write_vals = {
            'tms_status': 'delivered',
            'tms_actual_cost': payload.get('actual_cost', 0.0),
            'tms_pod_photos': json.dumps(payload.get('pod_photos', [])),
            'tms_signature_url': payload.get('signature_url'),
            'tms_pod_note': payload.get('pod_note'),
            'tms_pod_date': payload.get('pod_date'),
            'tms_sync_date': fields.Datetime.now(),
        }
        self.write(write_vals)

        # Update qty_done per move line
        for line in payload.get('qty_done_lines', []):
            move = self.move_ids.filtered(lambda m: m.id == line.get('move_id'))
            if move:
                for ml in move.move_line_ids:
                    ml.quantity = line.get('qty_done', move.product_uom_qty)

        # Validate the picking (set to done)
        if self.state not in ('done', 'cancel'):
            self.with_context(skip_immediate=True)._action_done()

        # Auto-create invoice if sale order exists
        if self.sale_id:
            self._tms_create_invoice()

        self.env['tms.sync.log'].log(
            trigger_code='T6',
            direction='tms_to_odoo',
            picking=self,
            sale_order=self.sale_id,
            status='success',
            request_payload=json.dumps(payload),
            tms_tracking_number=self.tms_tracking_number,
        )

    def _tms_create_invoice(self):
        """Auto-create customer invoice after delivery complete (T6)."""
        sale = self.sale_id
        if not sale or sale.invoice_status == 'invoiced':
            return

        try:
            sale._create_invoices()
            invoice = sale.invoice_ids.filtered(lambda i: i.state == 'draft')[:1]
            if invoice:
                _logger.info('T6: Auto-created invoice %s for SO %s', invoice.name, sale.name)
        except Exception as e:
            _logger.error('T6: Failed to auto-create invoice for SO %s: %s', sale.name, e)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _tms_get_move_lines(self):
        lines = []
        for move in self.move_ids:
            product = move.product_id
            lines.append({
                'move_id': move.id,
                'product_id': product.id,
                'product_code': product.default_code,
                'product_name': product.name,
                'barcode': product.barcode,
                'qty_ordered': move.product_uom_qty,
                'uom_name': move.product_uom.name,
                'uom_factor': move.product_uom.factor,
                'weight_per_unit': product.weight,
                'pkg_length_cm': product.tms_pkg_length,
                'pkg_width_cm': product.tms_pkg_width,
                'pkg_height_cm': product.tms_pkg_height,
            })
        return lines

    @staticmethod
    def _format_address(partner):
        parts = filter(None, [
            partner.street,
            partner.street2,
            partner.city,
            partner.state_id.name if partner.state_id else None,
        ])
        return ', '.join(parts)

    def _post_tms_webhook(self, endpoint, payload, trigger_code):
        tms_url = self._get_tms_config('tms.webhook.url')
        api_key = self._get_tms_config('tms.api.key')
        if not tms_url or not api_key:
            return

        url = tms_url.rstrip('/') + endpoint
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
        }
        start = time.time()
        status = 'error'
        http_code = None
        response_text = None
        error_msg = None

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            http_code = resp.status_code
            response_text = resp.text
            status = 'success' if resp.ok else 'error'
            if not resp.ok:
                error_msg = f'HTTP {resp.status_code}: {resp.text[:500]}'
        except requests.exceptions.Timeout:
            error_msg = 'Webhook timeout after 10s'
        except Exception as e:
            error_msg = str(e)

        duration_ms = int((time.time() - start) * 1000)

        self.env['tms.sync.log'].log(
            trigger_code=trigger_code,
            direction='odoo_to_tms',
            picking=self,
            sale_order=self.sale_id,
            status=status,
            request_payload=json.dumps(payload),
            response_payload=response_text,
            error_message=error_msg,
            http_status_code=http_code,
            duration_ms=duration_ms,
        )

    @api.model
    def _get_tms_config(self, key):
        return self.env['ir.config_parameter'].sudo().get_param(key)
