from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ConstructionJobCosting(models.Model):
    _name = 'construction.job.costing'
    _description = 'Job Costing Dashboard'
    _inherit = ['mail.thread']
    _rec_name = 'contract_id'

    contract_id = fields.Many2one(
        'construction.job.contract', string='Contract',
        required=True, ondelete='cascade',
    )
    analytic_account_id = fields.Many2one(
        'account.analytic.account', string='Analytic Account',
        related='contract_id.analytic_account_id', store=True,
    )

    @api.model
    def name_create(self, name):
        raise UserError(_('Job Costing records can only be created from a Job Contract.'))

    currency_id = fields.Many2one(
        'res.currency', related='contract_id.currency_id', store=True,
    )

    # --- Revenue ---
    contract_value = fields.Monetary(
        string='Contract Value', related='contract_id.contract_value', store=True,
    )
    revenue_billed = fields.Monetary(
        string='Revenue Billed', compute='_compute_revenue', store=False,
    )
    revenue_collected = fields.Monetary(
        string='Revenue Collected', compute='_compute_revenue', store=False,
    )

    # --- Budget (budget.analytic) ---
    budget_material = fields.Monetary(string='Budget Material', compute='_compute_budget', store=False)
    budget_labor = fields.Monetary(string='Budget Labor', compute='_compute_budget', store=False)
    budget_equipment = fields.Monetary(string='Budget Equipment', compute='_compute_budget', store=False)
    budget_subcon = fields.Monetary(string='Budget Sub-Con', compute='_compute_budget', store=False)
    budget_overhead = fields.Monetary(string='Budget Overhead', compute='_compute_budget', store=False)
    budget_total = fields.Monetary(string='Budget Total', compute='_compute_budget', store=False)

    # --- Actuals (from account.analytic.line) ---
    actual_cost = fields.Monetary(
        string='Actual Cost', compute='_compute_actuals', store=False,
    )
    actual_revenue = fields.Monetary(
        string='Actual Revenue', compute='_compute_actuals', store=False,
    )

    # --- KPI ---
    gross_margin = fields.Monetary(
        string='Gross Margin', compute='_compute_kpi', store=False,
    )
    gross_margin_pct = fields.Float(
        string='Gross Margin (%)', compute='_compute_kpi', store=False, digits=(5, 2),
    )
    eac = fields.Monetary(
        string='EAC (Estimate at Completion)', compute='_compute_kpi', store=False,
    )
    physical_progress = fields.Float(
        string='Physical Progress (%)', compute='_compute_physical_progress', digits=(5, 2),
    )

    def _get_analytic_lines(self):
        self.ensure_one()
        if not self.analytic_account_id:
            return self.env['account.analytic.line']
        return self.env['account.analytic.line'].search([
            ('account_id', '=', self.analytic_account_id.id),
        ])

    def _compute_revenue(self):
        for rec in self:
            # Revenue from approved/invoiced RA billings
            billings = rec.contract_id.billing_ids.filtered(
                lambda b: b.state in ('approved', 'invoiced', 'paid')
            )
            rec.revenue_billed = sum(billings.mapped('amount_untaxed'))

            # Collected = payments on customer invoices
            invoices = billings.mapped('invoice_id').filtered(lambda i: i.state == 'posted')
            rec.revenue_collected = sum(invoices.mapped('amount_total_signed'))

    def _compute_budget(self):
        for rec in self:
            budget = rec.contract_id.budget_id
            for f in ['budget_material', 'budget_labor', 'budget_equipment',
                      'budget_subcon', 'budget_overhead']:
                setattr(rec, f, 0.0)
            rec.budget_total = (
                sum(budget.budget_line_ids.mapped('budget_amount')) if budget else 0.0
            )

    def _compute_actuals(self):
        for rec in self:
            lines = rec._get_analytic_lines()
            rec.actual_cost = abs(sum(l.amount for l in lines if l.amount < 0))
            rec.actual_revenue = sum(l.amount for l in lines if l.amount > 0)

    def _compute_kpi(self):
        for rec in self:
            rec.gross_margin = rec.actual_revenue - rec.actual_cost
            rec.gross_margin_pct = (
                rec.gross_margin / rec.actual_revenue * 100
                if rec.actual_revenue else 0.0
            )
            # EAC = actual_cost / physical_progress (if progress > 0)
            progress = rec.physical_progress / 100
            if progress > 0 and rec.actual_cost:
                rec.eac = rec.actual_cost / progress
            else:
                rec.eac = rec.budget_total

    def _compute_physical_progress(self):
        for rec in self:
            boq_lines = rec.contract_id.boq_line_ids
            if not boq_lines:
                rec.physical_progress = 0.0
                continue
            weighted = sum(
                l.weight_percent * l.progress_physical / 100
                for l in boq_lines
            )
            rec.physical_progress = weighted

    def action_view_analytic_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Analytic Lines — %s') % self.contract_id.project_name,
            'res_model': 'account.analytic.line',
            'view_mode': 'list,form',
            'domain': [('account_id', '=', self.analytic_account_id.id)],
        }

    def action_refresh(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }
