from odoo import models, fields, api, _


class ConstructionBoqLine(models.Model):
    _name = 'construction.boq.line'
    _description = 'BOQ Line Item'
    _order = 'sequence, code'

    sequence = fields.Integer(default=10)
    contract_id = fields.Many2one(
        'construction.job.contract', string='Contract',
        required=True, ondelete='cascade', index=True,
    )
    code = fields.Char(string='BOQ Code', required=True)
    name = fields.Many2one(
        'product.template',
        string='Description of Work',
        required=True,
        domain=[('product_tag_ids.name', '=', 'COP')],
    )
    product_id = fields.Many2one('product.product', string='Odoo Product')
    uom_id = fields.Many2one('uom.uom', string='UoM', required=True)
    volume_contract = fields.Float(string='Contract Volume', digits=(16, 4), default=1.0)
    unit_price_contract = fields.Monetary(string='Unit Price (Contract)')
    currency_id = fields.Many2one(
        'res.currency', related='contract_id.currency_id', store=True,
    )
    subtotal_contract = fields.Monetary(
        string='Subtotal', compute='_compute_subtotal', store=True,
    )
    weight_percent = fields.Float(
        string='Weight (%)', compute='_compute_weight', store=True, digits=(5, 2),
    )
    sale_order_line_id = fields.Many2one('sale.order.line', string='SO Line', readonly=True)
    rate_analysis_id = fields.Many2one('construction.rate.analysis', string='Rate Analysis')

    # Progress tracking
    progress_physical = fields.Float(string='Progress (%)', digits=(5, 2), default=0.0)
    volume_actual = fields.Float(string='Volume Actual', digits=(16, 4), default=0.0)
    volume_billed = fields.Float(
        string='Volume Billed (%)', compute='_compute_volume_billed', store=True,
    )

    ra_billing_line_ids = fields.One2many(
        'construction.ra.billing.line', 'boq_line_id', string='Billing Lines',
    )

    def _compute_display_name(self):
        for rec in self:
            tmpl_name = rec.name.name if rec.name else ''
            rec.display_name = '[%s] %s' % (rec.code, tmpl_name) if rec.code else tmpl_name

    @api.model
    def _name_search(self, name='', domain=None, operator='ilike', limit=100, order=None):
        if name:
            domain = ['|', ('code', operator, name), ('name.name', operator, name)] + (domain or [])
        return super()._name_search(name='', domain=domain, operator=operator, limit=limit, order=order)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            tmpl = self.product_id.product_tmpl_id
            if 'COP' in tmpl.product_tag_ids.mapped('name'):
                self.name = tmpl

    @api.depends('volume_contract', 'unit_price_contract')
    def _compute_subtotal(self):
        for rec in self:
            rec.subtotal_contract = rec.volume_contract * rec.unit_price_contract

    @api.depends('subtotal_contract', 'contract_id.boq_total')
    def _compute_weight(self):
        for rec in self:
            total = rec.contract_id.boq_total
            rec.weight_percent = (rec.subtotal_contract / total * 100) if total else 0.0

    @api.depends('ra_billing_line_ids.progress_cumulative')
    def _compute_volume_billed(self):
        for rec in self:
            lines = rec.ra_billing_line_ids.filtered(
                lambda l: l.billing_id.state in ('approved', 'invoiced', 'paid')
            )
            rec.volume_billed = max(lines.mapped('progress_cumulative'), default=0.0)
