import logging
from datetime import datetime, timezone

from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class SaleOrderSos(models.Model):
    """
    Extends sale.order with SOS audit trail and the auto-confirm logic
    invoked by Automated Action #1.

    Only orders whose `origin` starts with "SOS-" are considered SOS orders.
    All mutations go through SosAuditMixin.write() so every state change is
    recorded in sos.audit.log and posted to the chatter.
    """
    _name = 'sale.order'
    _inherit = ['sale.order', 'sos.audit.mixin']

    SOS_TRACKED_FIELDS = ['state', 'invoice_status']

    sos_order = fields.Boolean(
        string='SOS Order',
        compute='_compute_sos_order',
        store=True,
        index=True,
    )
    sos_txn_number = fields.Char(
        string='No. Transaksi SOS',
        index=True,
        copy=False,
        help='Nomor transaksi unik dari aplikasi Amazing Toys SOS (format: TXN-YYYYMMDD-NNNNN).',
    )

    @api.depends('origin')
    def _compute_sos_order(self):
        for order in self:
            order.sos_order = bool(order.origin and order.origin.startswith('SOS-'))

    @api.model
    def _sos_generate_txn_number(self):
        """Generate nomor transaksi SOS menggunakan ir.sequence."""
        return self.env['ir.sequence'].next_by_code('sos.txn.number') or '/'

    # ------------------------------------------------------------------
    # Auto #1 — called by Automated Action on create/write
    # ------------------------------------------------------------------
    def action_sos_auto_confirm(self):
        """
        Confirm all SOS draft orders in self.  Idempotent: already-confirmed
        orders are silently skipped.
        """
        now_utc = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        for order in self.filtered(lambda o: o.sos_order and o.state == 'draft'):
            order.action_confirm()
            _logger.info('[SOS Auto #1] Order %s auto-confirmed at %s', order.name, now_utc)
            order.message_post(
                body=f'<b>[SOS Auto #1]</b> Order auto-confirmed at {now_utc}',
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )
