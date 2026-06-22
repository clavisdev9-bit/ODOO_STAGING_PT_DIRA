from odoo import models, fields, api


class TmsSyncLog(models.Model):
    _name = 'tms.sync.log'
    _description = 'TMS Synchronization Log'
    _order = 'create_date desc'
    _rec_name = 'trigger_code'

    trigger_code = fields.Selection([
        ('T1', 'T1: SO Confirmed → Create TMS Order'),
        ('T2', 'T2: Picking Assigned → Update TMS'),
        ('T3', 'T3: Send to TMS'),
        ('T4', 'T4: Driver Pickup'),
        ('T5', 'T5: GPS Update'),
        ('T6', 'T6: Delivery Complete → Validate & Invoice'),
        ('T7', 'T7: Punch-out → Create Expense'),
    ], string='Trigger', required=True, index=True)

    direction = fields.Selection([
        ('odoo_to_tms', 'Odoo → TMS'),
        ('tms_to_odoo', 'TMS → Odoo'),
    ], string='Direction', required=True)

    status = fields.Selection([
        ('success', 'Success'),
        ('error', 'Error'),
        ('pending', 'Pending'),
    ], string='Status', required=True, default='pending', index=True)

    picking_id = fields.Many2one('stock.picking', string='Delivery Order', ondelete='set null', index=True)
    sale_order_id = fields.Many2one('sale.order', string='Sale Order', ondelete='set null', index=True)
    tms_tracking_number = fields.Char('TMS Tracking Number')
    request_payload = fields.Text('Request Payload (JSON)')
    response_payload = fields.Text('Response Payload (JSON)')
    error_message = fields.Text('Error Message')
    http_status_code = fields.Integer('HTTP Status Code')
    duration_ms = fields.Integer('Duration (ms)')
    retry_count = fields.Integer('Retry Count', default=0)

    @api.model
    def log(self, trigger_code, direction, picking=None, sale_order=None,
            status='success', request_payload=None, response_payload=None,
            error_message=None, http_status_code=None, duration_ms=None,
            tms_tracking_number=None):
        vals = {
            'trigger_code': trigger_code,
            'direction': direction,
            'status': status,
            'picking_id': picking.id if picking else False,
            'sale_order_id': sale_order.id if sale_order else False,
            'request_payload': request_payload,
            'response_payload': response_payload,
            'error_message': error_message,
            'http_status_code': http_status_code,
            'duration_ms': duration_ms,
            'tms_tracking_number': tms_tracking_number,
        }
        return self.sudo().create(vals)
