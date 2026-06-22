from odoo import models, fields, api


class CopLine(models.Model):
    _name = 'cop.line'
    _description = 'COP Line Item'
    _order = 'sequence, code'
    _rec_name = 'code'

    sequence = fields.Integer(default=10)
    contract_id = fields.Many2one(
        'construction.job.contract', string='Contract',
        required=True, ondelete='cascade', index=True,
    )
    boq_line_id = fields.Many2one(
        'construction.boq.line', string='BOQ Reference',
        domain="[('contract_id', '=', contract_id)]",
    )
    code = fields.Char(string='COP Code', required=True)
    cop_name = fields.Char(string='Description of Work', required=True)
    product_id = fields.Many2one('product.product', string='Odoo Product')
    uom_id = fields.Many2one('uom.uom', string='UoM', required=True)
    volume_contract = fields.Float(string='Contract Volume', digits=(16, 4))
    unit_price_contract = fields.Monetary(string='Unit Price (Contract)')
    volume_actual = fields.Float(string='Actual Volume', digits=(16, 4), default=1.0)
    unit_price_actual = fields.Monetary(string='Unit Price (Actual)')
    subtotal_cop = fields.Monetary(
        string='Subtotal COP', compute='_compute_subtotal_cop', store=True,
    )
    weight_percent = fields.Float(
        string='Weight (%)', compute='_compute_weight_percent', digits=(5, 2), readonly=True,
    )
    progress_physical = fields.Float(string='Progress (%)', digits=(5, 2), default=0.0)
    rate_analysis_id = fields.Many2one(
        'construction.rate.analysis', string='Rate Analysis'
    )
    currency_id = fields.Many2one(
        'res.currency', related='contract_id.currency_id', store=True,
    )

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = '[%s] %s' % (rec.code, rec.cop_name) if rec.code else rec.cop_name

    @api.depends('volume_actual', 'unit_price_actual')
    def _compute_subtotal_cop(self):
        for rec in self:
            rec.subtotal_cop = rec.volume_actual * rec.unit_price_actual

    @api.depends('subtotal_cop', 'contract_id.cop_total')
    def _compute_weight_percent(self):
        for rec in self:
            total = rec.contract_id.cop_total
            rec.weight_percent = (rec.subtotal_cop / total * 100) if total else 0.0
