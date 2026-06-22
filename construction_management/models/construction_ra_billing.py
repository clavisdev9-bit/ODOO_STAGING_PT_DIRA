from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ConstructionRaBilling(models.Model):
    _name = 'construction.ra.billing'
    _description = 'RA Billing / Progress Invoice'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'

    name = fields.Char(
        string='Billing No.', required=True, copy=False,
        readonly=True, default=lambda self: _('New'),
    )
    contract_id = fields.Many2one(
        'construction.job.contract', string='Contract',
        required=True, ondelete='restrict', index=True,
    )
    partner_id = fields.Many2one(
        'res.partner', related='contract_id.partner_id', store=True,
    )
    currency_id = fields.Many2one(
        'res.currency', related='contract_id.currency_id', store=True,
    )
    analytic_account_id = fields.Many2one(
        'account.analytic.account', related='contract_id.analytic_account_id', store=True,
    )
    period_date = fields.Date(string='Period Date', required=True)
    billing_date = fields.Date(string='Invoice Date')

    billing_line_ids = fields.One2many(
        'construction.ra.billing.line', 'billing_id', string='Billing Lines',
    )
    invoice_id = fields.Many2one('account.move', string='Customer Invoice', readonly=True, copy=False)

    amount_untaxed = fields.Monetary(string='Untaxed Amount', compute='_compute_amounts', store=True)
    retention_amount = fields.Monetary(string='Retention Amount', compute='_compute_amounts', store=True)
    amount_net = fields.Monetary(string='Net Billing', compute='_compute_amounts', store=True)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('invoiced', 'Invoiced'),
        ('paid', 'Paid'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    notes = fields.Text(string='Notes')

    @api.depends('billing_line_ids.value_this', 'contract_id.retention_rate')
    def _compute_amounts(self):
        for rec in self:
            total = sum(rec.billing_line_ids.mapped('value_this'))
            retention = total * rec.contract_id.retention_rate / 100
            rec.amount_untaxed = total
            rec.retention_amount = retention
            rec.amount_net = total - retention

    def action_submit(self):
        for rec in self:
            if not rec.billing_line_ids:
                raise UserError(_('Please add billing lines before submitting.'))
            if rec.name == _('New'):
                rec.name = self.env['ir.sequence'].next_by_code('construction.ra.billing') or _('New')
            rec.state = 'submitted'

    def action_approve(self):
        self.filtered(lambda r: r.state == 'submitted').write({'state': 'approved'})

    def action_create_invoice(self):
        for rec in self.filtered(lambda r: r.state == 'approved'):
            invoice = rec._make_invoice()
            rec.invoice_id = invoice
            rec.state = 'invoiced'

    def _make_invoice(self):
        self.ensure_one()
        analytic_id = self.analytic_account_id.id
        invoice_lines = []
        for line in self.billing_line_ids:
            line_vals = {
                'name': '[%s] %s — %s%%' % (
                    line.boq_line_id.code,
                    line.boq_line_id.name.name,
                    line.progress_this,
                ),
                'quantity': 1,
                'price_unit': line.value_this,
                'product_id': line.boq_line_id.product_id.id,
            }
            if analytic_id:
                line_vals['analytic_distribution'] = {str(analytic_id): 100.0}
            invoice_lines.append((0, 0, line_vals))

        # Retention deduction line
        if self.retention_amount:
            ret_product = self.env.ref(
                'construction_management.product_retention', raise_if_not_found=False,
            )
            ret_line = {
                'name': _('Retention %.1f%%') % self.contract_id.retention_rate,
                'quantity': 1,
                'price_unit': -self.retention_amount,
            }
            if ret_product:
                ret_line['product_id'] = ret_product.id
            invoice_lines.append((0, 0, ret_line))

        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'invoice_date': self.billing_date or fields.Date.today(),
            'invoice_line_ids': invoice_lines,
            'narration': _('RA Billing: %s — Contract: %s') % (self.name, self.contract_id.name),
        })
        return invoice

    def action_view_invoice(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.invoice_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_cancel(self):
        for rec in self:
            if rec.state == 'invoiced':
                raise UserError(_('Cannot cancel a billing that has already been invoiced.'))
            rec.state = 'cancelled'

    def action_reset_draft(self):
        self.filtered(lambda r: r.state == 'cancelled').write({'state': 'draft'})


class ConstructionRaBillingLine(models.Model):
    _name = 'construction.ra.billing.line'
    _description = 'RA Billing Line'
    _order = 'sequence'

    sequence = fields.Integer(default=10)
    billing_id = fields.Many2one(
        'construction.ra.billing', required=True, ondelete='cascade',
    )
    boq_line_id = fields.Many2one(
        'construction.boq.line', string='BOQ Item',
        required=True,
        domain="[('contract_id', '=', parent.contract_id)]",
    )
    currency_id = fields.Many2one(
        'res.currency', related='billing_id.currency_id', store=True,
    )
    volume_contract = fields.Float(
        string='Contract Vol.', related='boq_line_id.volume_contract', store=True,
    )
    unit_price = fields.Monetary(
        string='Unit Price', related='boq_line_id.unit_price_contract', store=True,
    )
    subtotal_contract = fields.Monetary(
        string='Contract Value', related='boq_line_id.subtotal_contract', store=True,
    )

    progress_prev = fields.Float(string='Prev. Progress (%)', digits=(5, 2), default=0.0)
    progress_this = fields.Float(string='This Period (%)', digits=(5, 2), default=0.0)
    progress_cumulative = fields.Float(
        string='Cumulative (%)', compute='_compute_cumulative', store=True, digits=(5, 2),
    )
    value_prev = fields.Monetary(string='Prev. Value', compute='_compute_values', store=True)
    value_cumulative = fields.Monetary(string='Cumul. Value', compute='_compute_values', store=True)
    value_this = fields.Monetary(string='This Period Value', compute='_compute_values', store=True)

    @api.depends('progress_prev', 'progress_this')
    def _compute_cumulative(self):
        for rec in self:
            rec.progress_cumulative = rec.progress_prev + rec.progress_this

    @api.depends('subtotal_contract', 'progress_prev', 'progress_cumulative')
    def _compute_values(self):
        for rec in self:
            rec.value_prev = rec.subtotal_contract * rec.progress_prev / 100
            rec.value_cumulative = rec.subtotal_contract * rec.progress_cumulative / 100
            rec.value_this = rec.value_cumulative - rec.value_prev
