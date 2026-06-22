from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ConstructionMaterialReq(models.Model):
    _name = 'construction.material.req'
    _description = 'Material Purchase Requisition (MPR)'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'

    name = fields.Char(
        string='MPR No.', required=True, copy=False,
        readonly=True, default=lambda self: _('New'),
    )
    contract_id = fields.Many2one(
        'construction.job.contract', string='Contract',
        required=True, ondelete='restrict', index=True,
    )
    currency_id = fields.Many2one(
        'res.currency', related='contract_id.currency_id', store=True,
    )
    analytic_account_id = fields.Many2one(
        'account.analytic.account', related='contract_id.analytic_account_id', store=True,
    )
    site = fields.Char(string='Site Location')
    purpose = fields.Char(string='Purpose / Use')
    date_required = fields.Date(string='Required Date', required=True)
    requested_by = fields.Many2one('res.users', string='Requested By', default=lambda self: self.env.user)

    line_ids = fields.One2many('construction.material.req.line', 'req_id', string='Material Lines')
    purchase_order_ids = fields.Many2many('purchase.order', string='Purchase Orders')

    total_estimated = fields.Monetary(string='Total Estimated', compute='_compute_total', store=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('purchased', 'PO Created'),
        ('received', 'Received'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    notes = fields.Text(string='Notes')

    @api.depends('line_ids.estimated_total')
    def _compute_total(self):
        for rec in self:
            rec.total_estimated = sum(rec.line_ids.mapped('estimated_total'))

    def action_submit(self):
        for rec in self:
            if not rec.line_ids:
                raise UserError(_('Please add material lines before submitting.'))
            if rec.name == _('New'):
                rec.name = self.env['ir.sequence'].next_by_code('construction.material.req') or _('New')
            rec.state = 'submitted'

    def action_approve(self):
        self.filtered(lambda r: r.state == 'submitted').write({'state': 'approved'})

    def action_create_po(self):
        for rec in self.filtered(lambda r: r.state == 'approved'):
            po = rec._make_purchase_order()
            if not po:
                raise UserError(_('No purchase order could be created. Please check the material lines.'))
            rec.purchase_order_ids = [(4, po.id)]
            rec.state = 'purchased'

    def _make_purchase_order(self):
        self.ensure_one()
        analytic_id = self.analytic_account_id.id

        # Group lines by vendor
        vendor_lines = {}
        for line in self.line_ids.filtered(lambda l: l.qty_to_order > 0):
            vendor = line.vendor_id
            if vendor not in vendor_lines:
                vendor_lines[vendor] = []
            vendor_lines[vendor].append(line)

        if not vendor_lines:
            raise UserError(_('No material lines with quantity to order. Please check the lines.'))

        po = None
        for vendor, lines in vendor_lines.items():
            if not vendor.id:
                raise UserError(_('All material lines must have a vendor set before creating a PO.'))
            po_line_vals = []
            for line in lines:
                pol = {
                    'product_id': line.product_id.id,
                    'name': line.product_id.name if line.product_id else line.name,
                    'product_qty': line.qty_to_order,
                    'product_uom': line.uom_id.id,
                    'price_unit': line.estimated_price,
                    'date_planned': self.date_required,
                }
                if analytic_id:
                    pol['analytic_distribution'] = {str(analytic_id): 100.0}
                po_line_vals.append((0, 0, pol))

            po = self.env['purchase.order'].create({
                'partner_id': vendor.id,
                'date_order': fields.Datetime.now(),
                'order_line': po_line_vals,
                'notes': _('MPR: %s\nSite: %s\nPurpose: %s') % (
                    self.name, self.site or '', self.purpose or '',
                ),
                'company_id': self.contract_id.company_id.id,
            })

            # Link PO lines back
            for po_line, line in zip(po.order_line, lines):
                line.po_line_id = po_line

        return po

    def action_cancel(self):
        self.filtered(lambda r: r.state not in ('purchased', 'received')).write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.filtered(lambda r: r.state == 'cancelled').write({'state': 'draft'})

    def action_view_po(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Orders'),
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.purchase_order_ids.ids)],
        }


class ConstructionMaterialReqLine(models.Model):
    _name = 'construction.material.req.line'
    _description = 'MPR Line'
    _order = 'sequence'

    sequence = fields.Integer(default=10)
    req_id = fields.Many2one('construction.material.req', required=True, ondelete='cascade')
    currency_id = fields.Many2one(
        'res.currency', related='req_id.currency_id', store=True,
    )
    product_id = fields.Many2one('product.product', string='Material')
    name = fields.Char(string='Description', required=True)
    uom_id = fields.Many2one('uom.uom', string='UoM')
    qty_required = fields.Float(string='Qty Required', digits=(16, 4), default=1.0)
    qty_on_hand = fields.Float(
        string='On Hand', compute='_compute_qty_on_hand', digits=(16, 4),
    )
    qty_to_order = fields.Float(
        string='Qty to Order', compute='_compute_qty_to_order', store=True, digits=(16, 4),
    )
    vendor_id = fields.Many2one('res.partner', string='Preferred Vendor')
    estimated_price = fields.Monetary(string='Est. Unit Price')
    estimated_total = fields.Monetary(
        string='Est. Total', compute='_compute_estimated_total', store=True,
    )
    po_line_id = fields.Many2one('purchase.order.line', string='PO Line', readonly=True)
    status = fields.Selection(
        related='po_line_id.order_id.state', string='PO Status',
    )

    def _compute_qty_on_hand(self):
        for rec in self:
            if rec.product_id:
                rec.qty_on_hand = rec.product_id.qty_available
            else:
                rec.qty_on_hand = 0.0

    @api.depends('qty_required', 'qty_on_hand')
    def _compute_qty_to_order(self):
        for rec in self:
            rec.qty_to_order = max(rec.qty_required - rec.qty_on_hand, 0.0)

    @api.depends('qty_to_order', 'estimated_price')
    def _compute_estimated_total(self):
        for rec in self:
            rec.estimated_total = rec.qty_to_order * rec.estimated_price

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.name
            self.uom_id = self.product_id.uom_id
            self.estimated_price = self.product_id.standard_price
