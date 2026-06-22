from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ConstructionScrap(models.Model):
    _name = 'construction.scrap'
    _description = 'Construction Scrap & Waste'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'

    name = fields.Char(
        string='Scrap No.', required=True, copy=False,
        readonly=True, default=lambda self: _('New'),
    )
    contract_id = fields.Many2one(
        'construction.job.contract', string='Contract',
        required=True, ondelete='restrict', index=True,
    )
    currency_id = fields.Many2one(
        'res.currency', related='contract_id.currency_id', store=True,
    )
    product_id = fields.Many2one('product.product', string='Material', required=True)
    uom_id = fields.Many2one('uom.uom', string='UoM', required=True)
    qty_scrap = fields.Float(string='Qty Scrap', digits=(16, 4), default=1.0)
    scrap_type = fields.Selection([
        ('sell', 'Saleable (Dijual)'),
        ('b3', 'Hazardous Waste (B3)'),
        ('normal', 'General Waste'),
    ], string='Scrap Type', required=True, default='normal')
    scrap_value = fields.Monetary(string='Estimated Value')

    from_location_id = fields.Many2one(
        'stock.location', string='From Location',
        domain=[('usage', '=', 'internal')],
    )
    scrap_location_id = fields.Many2one('stock.location', string='Scrap Location')

    scrap_id = fields.Many2one('stock.scrap', string='Stock Scrap', readonly=True, copy=False)
    description = fields.Text(string='Description / Remarks')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('validated', 'Validated'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    def action_validate(self):
        for rec in self:
            if rec.name == _('New'):
                rec.name = self.env['ir.sequence'].next_by_code('construction.scrap') or _('New')
            rec._create_stock_scrap()
            rec.state = 'validated'

    def _create_stock_scrap(self):
        self.ensure_one()
        scrap_vals = {
            'product_id': self.product_id.id,
            'product_uom_id': self.uom_id.id,
            'scrap_qty': self.qty_scrap,
        }
        if self.from_location_id:
            scrap_vals['location_id'] = self.from_location_id.id
        if self.scrap_location_id:
            scrap_vals['scrap_location_id'] = self.scrap_location_id.id

        scrap = self.env['stock.scrap'].create(scrap_vals)
        self.scrap_id = scrap

    def action_done(self):
        for rec in self.filtered(lambda r: r.state == 'validated'):
            if rec.scrap_id and rec.scrap_id.state == 'draft':
                rec.scrap_id.action_validate()
            rec.state = 'done'

    def action_cancel(self):
        self.filtered(lambda r: r.state in ('draft', 'validated')).write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.filtered(lambda r: r.state == 'cancelled').write({'state': 'draft'})

    def action_view_scrap(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.scrap',
            'res_id': self.scrap_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id
