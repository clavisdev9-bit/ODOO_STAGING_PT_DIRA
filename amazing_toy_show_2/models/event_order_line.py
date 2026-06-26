from odoo import fields, models, api

class EventOrderLine(models.Model):
    _name = 'event.order.line'
    _description = 'Event Order Line'

    order_id = fields.Many2one(comodel_name='event.order', required=True, ondelete='cascade')
    product_id = fields.Many2one(comodel_name='product.product', required=True)
    tenant_id = fields.Many2one(comodel_name='event.tenant', related='product_id.tenant_id', store=True)
    is_handed_over = fields.Boolean(string="Handed Over", default=False)
    handover_date = fields.Datetime(string="Handover Date")
    qty = fields.Integer(default=1)
    price_unit = fields.Float()
    subtotal = fields.Float(compute='_compute_subtotal', store=True)

    @api.depends('qty', 'price_unit')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line.qty * line.price_unit

    def action_item_handover(self):
        self.write({
            'is_handed_over': True,
            'handover_date': fields.Datetime.now()
        })
        self.order_id._check_order_completion()