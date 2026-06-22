from odoo import models, fields
from odoo.exceptions import UserError


class SendToTmsWizard(models.TransientModel):
    """T3 Wizard: konfirmasi sebelum kirim picking ke TMS backend."""
    _name = 'tms.send.to.tms.wizard'
    _description = 'Send to TMS Wizard'

    picking_id = fields.Many2one('stock.picking', required=True, readonly=True)
    picking_name = fields.Char(related='picking_id.name', readonly=True)
    partner_name = fields.Char(related='picking_id.partner_id.name', readonly=True)
    scheduled_date = fields.Datetime(related='picking_id.scheduled_date', readonly=True)
    urgency = fields.Selection([
        ('normal', 'Normal'),
        ('urgent', 'Urgent'),
    ], string='Urgency', default='normal', required=True)
    notes = fields.Text('Notes / Special Instructions')

    def action_confirm(self):
        self.ensure_one()
        if self.picking_id.tms_status not in ('not_sent', 'failed'):
            raise UserError(
                f'Picking sudah pernah dikirim ke TMS (status: {self.picking_id.tms_status}).\n'
                'Hubungi dispatcher untuk re-assign.'
            )
        tracking_number = self.picking_id._do_send_to_tms(
            urgency=self.urgency,
            notes=self.notes,
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Berhasil dikirim ke TMS',
                'message': f'Tracking Number: {tracking_number}',
                'type': 'success',
                'sticky': False,
            },
        }
