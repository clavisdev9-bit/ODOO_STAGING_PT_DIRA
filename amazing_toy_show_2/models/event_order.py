from odoo import models, fields, api
import uuid

class EventOrder(models.Model):
    _name = 'event.order'
    _description = 'Event Order'
    _order = 'id desc'

    name = fields.Char(default='#', readonly=True)
    token = fields.Char(default=lambda self: str(uuid.uuid4()), index=True)
    partner_id = fields.Many2one(comodel_name='res.partner', string='Customer')
    state = fields.Selection(selection=[
        ('draft', 'Cart'),
        ('confirmed', 'QR Generated'),
        ('paid', 'Paid'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], default='draft', index=True)
    line_ids = fields.One2many(comodel_name='event.order.line', inverse_name='order_id')
    total_amount = fields.Float(compute='_compute_total', store=True)
    total_qty = fields.Integer(compute='_compute_total', store=True)
    cart_qty = fields.Integer(compute='_compute_total', store=True)
    cashier_id = fields.Many2one(comodel_name='event.cashier')
    payment_method = fields.Selection(selection=[
        ('cash', 'Cash'),
        ('qr', 'QR Code'),
        ('card', 'Card/EDC')
    ])
    amount_received = fields.Float()
    amount_change = fields.Float()
    date_paid = fields.Datetime()

    @api.depends('line_ids.subtotal', 'line_ids.qty', 'line_ids.product_id.qty_available')
    def _compute_total(self):
        for order in self:
            order.total_amount = sum(order.line_ids.mapped('subtotal'))
            order.total_qty = sum(order.line_ids.mapped('qty'))
            order.cart_qty = len(order.line_ids)

    @api.model
    def get_or_create_cart(self, partner_id):
        """Fungsi tunggal untuk mengelola pengambilan keranjang"""
        if not partner_id:
            return False

        order = self.sudo().search([
            ('partner_id', '=', partner_id),
            ('state', '=', 'draft')
        ], limit=1)

        if not order:
            order = self.sudo().create({
                'partner_id': partner_id
            })
        return order

    def get_checkout_url(self):
        """Menghasilkan URL unik untuk di-scan kasir"""
        self.ensure_one()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        return f"{base_url}/order/validate/{self.token}"

    def action_checkout(self):
        self.ensure_one()
        unavailable_lines = self.line_ids.filtered(lambda l: l.product_id.qty_available < l.qty)
        if unavailable_lines:
            return False

        if self.name == '#':
            self.name = self.env['ir.sequence'].next_by_code('event.order') or '#'

        for line in self.line_ids:
            self._create_stock_move(line, 'out')

        self.write({'state': 'confirmed'})
        return True

    def action_set_to_draft(self):
        self.ensure_one()
        if self.state == 'confirmed':
            for line in self.line_ids:
                self._create_stock_move(line, 'in')

        self.sudo().write({'state': 'draft'})
        return True

    def _create_stock_move(self, line, direction='out'):
        """Helper function moves history"""
        stock_location = self.env.ref('stock.stock_location_stock').id
        customer_location = self.env.ref('stock.stock_location_customers').id

        move = self.env['stock.move'].sudo().create({
            'name': f"Event Order: {self.name}",
            'product_id': line.product_id.id,
            'product_uom_qty': line.qty,
            'product_uom': line.product_id.uom_id.id,
            'location_id': stock_location if direction == 'out' else customer_location,
            'location_dest_id': customer_location if direction == 'out' else stock_location,
            'quantity': line.qty,
        })
        move._action_confirm()
        move._action_assign()
        move.picked = True
        move._action_done()

    def _check_order_completion(self):
        for order in self:
            if not order.line_ids.filtered(lambda l: not l.is_handed_over):
                order.write({'state': 'done'})