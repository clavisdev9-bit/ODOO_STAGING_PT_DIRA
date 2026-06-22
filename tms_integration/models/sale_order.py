import json
import time
import logging
import requests
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    tms_synced = fields.Boolean('Sent to TMS', default=False, copy=False)
    tms_sync_date = fields.Datetime('TMS Sync Date', copy=False)

    def action_confirm(self):
        """Override: T1 — SO confirmed → send webhook to TMS."""
        result = super().action_confirm()
        for order in self:
            order._tms_trigger_t1()
        return result

    def action_resend_to_tms(self):
        """Manual resend: use when auto T1 failed or was skipped."""
        for order in self.filtered(lambda o: o.state in ('sale', 'done')):
            order._tms_trigger_t1()

    def _tms_trigger_t1(self):
        """T1: SO confirmed → notify TMS to create order."""
        tms_url = self._get_tms_config('tms.webhook.url')
        if not tms_url:
            return

        picking = self.picking_ids.filtered(
            lambda p: p.picking_type_code == 'outgoing' and p.state not in ('done', 'cancel')
        )[:1]

        payload = {
            'trigger': 'T1',
            'sale_order_id': self.id,
            'sale_order_name': self.name,
            'picking_id': picking.id if picking else False,
            'partner_id': self.partner_id.id,
            'partner_name': self.partner_id.name,
            'partner_phone': self.partner_id.phone or self.partner_id.mobile or None,
            'partner_email': self.partner_id.email or None,
            'delivery_address': self._format_address(self.partner_shipping_id),
            'delivery_lat': self.partner_shipping_id.partner_latitude or None,
            'delivery_lng': self.partner_shipping_id.partner_longitude or None,
            'scheduled_date': picking.scheduled_date.isoformat() if picking and picking.scheduled_date else None,
            'priority': picking.priority if picking else '0',
            'order_lines': self._tms_get_order_lines(),
        }

        self._post_tms_webhook('/api/v1/webhook/odoo/so-confirmed', payload, 'T1', picking)

    def _tms_get_order_lines(self):
        lines = []
        for move in self.picking_ids.filtered(
            lambda p: p.picking_type_code == 'outgoing'
        ).mapped('move_ids'):
            product = move.product_id
            lines.append({
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

    def _post_tms_webhook(self, endpoint, payload, trigger_code, picking=None):
        tms_url = self._get_tms_config('tms.webhook.url')
        api_key = self._get_tms_config('tms.api.key')
        if not tms_url or not api_key:
            _logger.warning('TMS webhook URL or API key not configured, skipping %s', trigger_code)
            return

        url = tms_url.rstrip('/') + endpoint
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}',
        }
        start = time.time()
        status = 'error'
        response_text = None
        http_code = None
        error_msg = None

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            http_code = resp.status_code
            response_text = resp.text
            if resp.ok:
                status = 'success'
                if picking:
                    picking.sudo().write({'tms_sync_date': fields.Datetime.now()})
                self.sudo().write({'tms_synced': True, 'tms_sync_date': fields.Datetime.now()})
            else:
                error_msg = f'HTTP {resp.status_code}: {resp.text[:500]}'
        except requests.exceptions.Timeout:
            error_msg = 'TMS webhook timeout after 10s'
        except Exception as e:
            error_msg = str(e)

        duration_ms = int((time.time() - start) * 1000)

        self.env['tms.sync.log'].log(
            trigger_code=trigger_code,
            direction='odoo_to_tms',
            picking=picking,
            sale_order=self,
            status=status,
            request_payload=json.dumps(payload),
            response_payload=response_text,
            error_message=error_msg,
            http_status_code=http_code,
            duration_ms=duration_ms,
        )

        if status == 'error':
            _logger.error('TMS %s webhook failed for SO %s: %s', trigger_code, self.name, error_msg)

    @api.model
    def _get_tms_config(self, key):
        return self.env['ir.config_parameter'].sudo().get_param(key)
