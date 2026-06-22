from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ConstructionSubcontract(models.Model):
    _name = 'construction.subcontract'
    _description = 'Sub-Contracting'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'

    name = fields.Char(
        string='Sub-Contract No.', required=True, copy=False,
        readonly=True, default=lambda self: _('New'),
    )
    contract_id = fields.Many2one(
        'construction.job.contract', string='Main Contract',
        required=True, ondelete='restrict', index=True,
    )
    currency_id = fields.Many2one(
        'res.currency', related='contract_id.currency_id', store=True,
    )
    analytic_account_id = fields.Many2one(
        'account.analytic.account', related='contract_id.analytic_account_id', store=True,
    )
    partner_id = fields.Many2one('res.partner', string='Sub-Contractor', required=True)
    scope_work = fields.Text(string='Scope of Work', required=True)
    boq_line_ids = fields.Many2many(
        'construction.boq.line', string='Related BOQ Items',
        domain="[('contract_id', '=', contract_id)]",
    )
    date_start = fields.Date(string='Start Date')
    date_end = fields.Date(string='End Date')
    contract_value = fields.Monetary(string='Sub-Contract Value', required=True)
    retention_rate = fields.Float(string='Retention (%)', default=5.0)
    progress = fields.Float(string='Progress (%)', digits=(5, 2), default=0.0)
    purchase_order_id = fields.Many2one('purchase.order', string='Purchase Order', readonly=True, copy=False)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    notes = fields.Text(string='Notes')

    def action_confirm(self):
        for rec in self:
            if rec.name == _('New'):
                rec.name = self.env['ir.sequence'].next_by_code('construction.subcontract') or _('New')
            rec._create_purchase_order()
            rec.state = 'confirmed'

    def _create_purchase_order(self):
        self.ensure_one()
        analytic_id = self.analytic_account_id.id

        product = self.env.ref(
            'construction_management.product_subcontract_service',
            raise_if_not_found=False,
        )
        line_vals = {
            'name': self.scope_work[:200] if self.scope_work else _('Sub-Contract Work'),
            'product_qty': 1,
            'price_unit': self.contract_value,
            'date_planned': self.date_start or fields.Date.today(),
        }
        if product:
            line_vals['product_id'] = product.id
            line_vals['product_uom'] = product.uom_po_id.id
        if analytic_id:
            line_vals['analytic_distribution'] = {str(analytic_id): 100.0}

        po = self.env['purchase.order'].create({
            'partner_id': self.partner_id.id,
            'date_order': fields.Datetime.now(),
            'order_line': [(0, 0, line_vals)],
            'notes': _('Sub-Contract: %s\nMain Contract: %s') % (self.name, self.contract_id.name),
            'company_id': self.contract_id.company_id.id,
        })
        self.purchase_order_id = po

    def action_set_ongoing(self):
        self.filtered(lambda r: r.state == 'confirmed').write({'state': 'ongoing'})

    def action_complete(self):
        self.filtered(lambda r: r.state == 'ongoing').write({'state': 'completed', 'progress': 100.0})

    def action_cancel(self):
        self.filtered(lambda r: r.state in ('draft', 'confirmed')).write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.filtered(lambda r: r.state == 'cancelled').write({'state': 'draft'})

    def action_view_po(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'purchase.order',
            'res_id': self.purchase_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
