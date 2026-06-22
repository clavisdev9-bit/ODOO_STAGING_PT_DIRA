from odoo import models, fields, api


class ConstructionBudget(models.Model):
    _name = 'construction.budget'
    _description = 'Construction Job Budget'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='Budget Reference', required=True, tracking=True)
    contract_id = fields.Many2one(
        'construction.job.contract', string='Job Contract', ondelete='cascade',
    )
    analytic_account_id = fields.Many2one(
        'account.analytic.account', string='Analytic Account',
    )
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', store=True,
    )
    line_ids = fields.One2many('construction.budget.line', 'budget_id', string='Budget Lines')
    total_planned = fields.Monetary(
        string='Total Planned', compute='_compute_total_planned', store=True,
    )

    @api.onchange('contract_id')
    def _onchange_contract_id(self):
        if self.contract_id:
            self.analytic_account_id = self.contract_id.analytic_account_id
        else:
            self.analytic_account_id = False

    @api.depends('line_ids.amount_planned')
    def _compute_total_planned(self):
        for rec in self:
            rec.total_planned = sum(rec.line_ids.mapped('amount_planned'))

    def action_populate_from_ra(self):
        self.ensure_one()
        if not self.contract_id:
            return True
        contract = self.contract_id
        existing_types = self.line_ids.mapped('cost_type')
        lines_to_create = []
        for boq in contract.boq_line_ids:
            if not boq.rate_analysis_id:
                continue
            ra = boq.rate_analysis_id
            for cost_type, amount_field in [
                ('material', 'total_material'),
                ('labor', 'total_labor'),
                ('equipment', 'total_equipment'),
            ]:
                amount = getattr(ra, amount_field, 0.0) * boq.volume_contract
                if amount and cost_type not in existing_types:
                    lines_to_create.append({
                        'budget_id': self.id,
                        'cost_type': cost_type,
                        'analytic_account_id': self.analytic_account_id.id,
                        'amount_planned': amount,
                    })
        if lines_to_create:
            self.env['construction.budget.line'].create(lines_to_create)
        return True


class ConstructionBudgetLine(models.Model):
    _name = 'construction.budget.line'
    _description = 'Construction Budget Line'

    budget_id = fields.Many2one(
        'construction.budget', string='Budget', ondelete='cascade', required=True,
    )
    cost_type = fields.Selection([
        ('material', 'Material'),
        ('labor', 'Labor'),
        ('equipment', 'Equipment'),
        ('subcontract', 'Sub-Contract'),
        ('overhead', 'Overhead'),
        ('other', 'Other'),
    ], string='Cost Type', required=True)
    analytic_account_id = fields.Many2one(
        'account.analytic.account', string='Analytic Account',
    )
    amount_planned = fields.Monetary(string='Planned Amount')
    amount_committed = fields.Monetary(
        string='Committed', compute='_compute_actuals', store=True,
    )
    amount_actual = fields.Monetary(
        string='Actual', compute='_compute_actuals', store=True,
    )
    variance = fields.Monetary(
        string='Variance', compute='_compute_actuals', store=True,
    )
    progress_pct = fields.Float(
        string='Progress (%)', compute='_compute_actuals', store=True,
    )
    currency_id = fields.Many2one(
        'res.currency', related='budget_id.currency_id', store=True,
    )
    company_id = fields.Many2one(
        'res.company', related='budget_id.company_id', store=True,
    )

    @api.depends('amount_planned', 'analytic_account_id')
    def _compute_actuals(self):
        for rec in self:
            actual = 0.0
            if rec.analytic_account_id:
                lines = self.env['account.analytic.line'].search([
                    ('account_id', '=', rec.analytic_account_id.id),
                ])
                actual = abs(sum(lines.mapped('amount')))
            rec.amount_actual = actual
            rec.amount_committed = 0.0
            rec.variance = rec.amount_planned - actual
            rec.progress_pct = (actual / rec.amount_planned * 100.0) if rec.amount_planned else 0.0
