import logging
from datetime import date, datetime, timezone

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class AccountMoveSos(models.Model):
    """
    Extends account.move with SOS audit trail.
    Invoice creation + posting is triggered from sale_order_sos via
    Automated Action #3; the logic lives here so it is testable standalone.
    """
    _name = 'account.move'
    _inherit = ['account.move', 'sos.audit.mixin']

    SOS_TRACKED_FIELDS = ['state', 'payment_state']


class SaleOrderSosInvoice(models.Model):
    """
    Additional method on sale.order that handles Auto #3.
    Kept in a separate file to preserve single-responsibility.
    """
    _inherit = 'sale.order'

    # ------------------------------------------------------------------
    # Auto #3 — called by Automated Action on write (invoice_status → to invoice)
    # ------------------------------------------------------------------
    def action_sos_auto_invoice(self):
        """
        Create and immediately post an invoice for each SOS order that is
        confirmed and ready to invoice.  Idempotent: orders that already have
        a posted invoice are skipped.
        """
        now_utc = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        today = date.today()

        eligible = self.filtered(
            lambda o: o.sos_order
            and o.state == 'sale'
            and o.invoice_status == 'to invoice'
        )

        for order in eligible:
            # Skip if a posted invoice already exists (idempotency guard)
            existing_posted = order.invoice_ids.filtered(
                lambda inv: inv.state == 'posted' and inv.move_type == 'out_invoice'
            )
            if existing_posted:
                continue

            # Void any leftover draft invoices so _create_invoices() starts clean
            order.invoice_ids.filtered(lambda inv: inv.state == 'draft').button_cancel()

            invoices = order.sudo()._create_invoices(final=True)
            invoices.write({
                'invoice_date': today,
                'ref': order.name,
            })
            invoices.sudo().action_post()

            inv_names = ', '.join(invoices.mapped('name'))
            _logger.info('[SOS Auto #3] Invoices %s posted for SO %s at %s', inv_names, order.name, now_utc)

            for inv in invoices:
                inv.message_post(
                    body=(
                        f'<b>[SOS Auto #3]</b> Invoice auto-created and posted at {now_utc} '
                        f'for Sales Order <b>{order.name}</b>'
                    ),
                    message_type='notification',
                    subtype_xmlid='mail.mt_note',
                )
            order.message_post(
                body=(
                    f'<b>[SOS Auto #3]</b> Invoice <b>{inv_names}</b> '
                    f'auto-created and posted at {now_utc}'
                ),
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )
