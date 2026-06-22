import logging
from datetime import datetime, timezone

from odoo import models, fields, api, _

_logger = logging.getLogger(__name__)


class StockPickingSos(models.Model):
    """
    Extends stock.picking with SOS audit trail and the auto-validate logic
    invoked by Automated Action #2.

    Only outgoing pickings linked to a confirmed SOS Sales Order are processed.
    """
    _name = 'stock.picking'
    _inherit = ['stock.picking', 'sos.audit.mixin']

    SOS_TRACKED_FIELDS = ['state']

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _is_sos_picking(self):
        """Return True if this picking belongs to a SOS sales order."""
        self.ensure_one()
        if self.picking_type_code != 'outgoing':
            return False
        sale = self.sale_id
        return bool(sale and sale.sos_order)

    def _set_all_qty_done(self):
        """
        Mark all move lines as fully done so button_validate() does not
        trigger an immediate-transfer wizard or a backorder dialog.
        In Odoo 17/18 the field is `quantity`; fall back to `qty_done`.
        """
        for move in self.move_ids.filtered(lambda m: m.state not in ('done', 'cancel')):
            qty_field = 'quantity' if hasattr(move, 'quantity') else 'quantity_done'
            setattr(move, qty_field, move.product_uom_qty)
            for line in move.move_line_ids:
                line_qty_field = 'quantity' if hasattr(line, 'quantity') else 'qty_done'
                reserved = getattr(line, 'reserved_qty', getattr(line, 'product_qty', 0.0))
                setattr(line, line_qty_field, reserved)

    # ------------------------------------------------------------------
    # Auto #2 — called by Automated Action on write (state → assigned)
    # ------------------------------------------------------------------
    def action_sos_auto_validate(self):
        """
        Validate all ready SOS outgoing pickings in self.  Idempotent.
        """
        now_utc = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        for picking in self.filtered(lambda p: p._is_sos_picking() and p.state == 'assigned'):
            picking._set_all_qty_done()
            picking.with_context(
                skip_backorder=True,
                skip_immediate=True,
                # Suppress the "create backorder" wizard
                immediate_transfer=True,
            ).button_validate()
            _logger.info('[SOS Auto #2] Picking %s auto-validated at %s', picking.name, now_utc)
            picking.message_post(
                body=f'<b>[SOS Auto #2]</b> Delivery auto-validated at {now_utc}',
                message_type='notification',
                subtype_xmlid='mail.mt_note',
            )
