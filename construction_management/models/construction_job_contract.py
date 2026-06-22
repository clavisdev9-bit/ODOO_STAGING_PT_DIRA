from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from dateutil.relativedelta import relativedelta


class ConstructionJobContract(models.Model):
    _name = 'construction.job.contract'
    _description = 'Construction Job Contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'

    name = fields.Char(
        string='Contract No.', required=True, copy=False,
        readonly=True, default=lambda self: _('New'), tracking=True,
    )
    project_name = fields.Char(string='Project Name', required=True, tracking=True)
    partner_id = fields.Many2one('res.partner', string='Client', required=True, tracking=True)
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one(
        'res.currency', string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    contract_value = fields.Monetary(string='Contract Value', required=True, tracking=True)
    contract_type = fields.Selection([
        ('lump_sum', 'Lump Sum Fixed Price'),
        ('unit_price', 'Unit Price'),
        ('cost_plus', 'Cost Plus'),
    ], string='Contract Type', required=True, default='lump_sum', tracking=True)
    date_spk = fields.Date(string='SPK Date', required=True)
    date_start = fields.Date(string='Start Date', required=True)
    duration_months = fields.Integer(string='Duration (months)', required=True, default=12)
    date_end = fields.Date(string='End Date', compute='_compute_date_end', store=True)
    retention_rate = fields.Float(string='Retention (%)', default=5.0)

    analytic_account_id = fields.Many2one(
        'account.analytic.account', string='Analytic Account',
        readonly=True, copy=False,
    )
    project_id = fields.Many2one(
        'project.project', string='Odoo Project',
        readonly=True, copy=False,
    )
    sale_order_id = fields.Many2one(
        'sale.order', string='Sale Order',
        readonly=True, copy=False,
    )
    budget_id = fields.Many2one(
        'budget.analytic', string='Job Budget',
        readonly=True, copy=False,
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('running', 'Running'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    boq_line_ids = fields.One2many('construction.boq.line', 'contract_id', string='BOQ Lines')
    work_order_ids = fields.One2many('construction.work.order', 'contract_id', string='Work Orders')
    material_req_ids = fields.One2many('construction.material.req', 'contract_id', string='Material Requests')
    subcontract_ids = fields.One2many('construction.subcontract', 'contract_id', string='Sub-Contractors')
    billing_ids = fields.One2many('construction.ra.billing', 'contract_id', string='RA Billings')
    scrap_ids = fields.One2many('construction.scrap', 'contract_id', string='Scrap Records')

    boq_total = fields.Monetary(string='BOQ Total', compute='_compute_boq_total', store=True)
    billing_total = fields.Monetary(string='Total Billed', compute='_compute_billing_total')
    work_order_count = fields.Integer(compute='_compute_counts')
    material_req_count = fields.Integer(compute='_compute_counts')
    billing_count = fields.Integer(compute='_compute_counts')

    notes = fields.Html(string='Terms & Notes')

    @api.depends('date_start', 'duration_months')
    def _compute_date_end(self):
        for rec in self:
            if rec.date_start and rec.duration_months:
                rec.date_end = rec.date_start + relativedelta(months=rec.duration_months)
            else:
                rec.date_end = False

    @api.depends('boq_line_ids.subtotal_contract')
    def _compute_boq_total(self):
        for rec in self:
            rec.boq_total = sum(rec.boq_line_ids.mapped('subtotal_contract'))

    def _compute_billing_total(self):
        for rec in self:
            rec.billing_total = sum(
                rec.billing_ids.filtered(
                    lambda b: b.state in ('approved', 'invoiced', 'paid')
                ).mapped('amount_untaxed')
            )

    def _compute_counts(self):
        for rec in self:
            rec.work_order_count = len(rec.work_order_ids)
            rec.material_req_count = len(rec.material_req_ids)
            rec.billing_count = len(rec.billing_ids)

    @api.constrains('contract_value')
    def _check_contract_value(self):
        for rec in self:
            if rec.contract_value <= 0:
                raise ValidationError(_('Contract value must be greater than zero.'))

    def action_confirm(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only Draft contracts can be confirmed.'))
            if not rec.boq_line_ids:
                raise UserError(_('Please add at least one BOQ line before confirming.'))

            if rec.name == _('New'):
                rec.name = self.env['ir.sequence'].next_by_code('construction.job.contract') or _('New')

            rec._create_analytic_account()
            rec._create_project()
            rec._create_sale_order()
            rec._create_budget()
            rec.state = 'confirmed'

    def action_set_running(self):
        self.filtered(lambda r: r.state == 'confirmed').write({'state': 'running'})

    def action_close(self):
        self.filtered(lambda r: r.state in ('confirmed', 'running')).write({'state': 'closed'})

    def action_cancel(self):
        for rec in self.filtered(lambda r: r.state == 'draft'):
            rec.state = 'cancelled'

    def action_reset_draft(self):
        self.filtered(lambda r: r.state == 'cancelled').write({'state': 'draft'})

    def _get_or_create_analytic_plan(self):
        plan = self.env.ref(
            'construction_management.construction_analytic_plan',
            raise_if_not_found=False,
        )
        if not plan:
            plan = self.env['account.analytic.plan'].search(
                [('name', '=', 'Construction')], limit=1
            )
        if not plan:
            plan = self.env['account.analytic.plan'].create({
                'name': 'Construction',
            })
        return plan

    def _create_analytic_account(self):
        plan = self._get_or_create_analytic_plan()
        code = 'ANA/' + self.name.replace('/', '-')
        analytic = self.env['account.analytic.account'].create({
            'name': self.project_name,
            'code': code,
            'plan_id': plan.id,
            'company_id': self.company_id.id,
        })
        self.analytic_account_id = analytic

    def _create_project(self):
        project_vals = {
            'name': self.project_name,
            'partner_id': self.partner_id.id,
            'date_start': self.date_start,
            'date': self.date_end,
            'allow_timesheets': True,
            'company_id': self.company_id.id,
        }
        if self.analytic_account_id:
            project_vals['account_id'] = self.analytic_account_id.id
        project = self.env['project.project'].create(project_vals)
        self.project_id = project
        # Sync analytic account if project created its own
        if project.account_id and not self.analytic_account_id:
            self.analytic_account_id = project.account_id

    def _create_sale_order(self):
        analytic_id = self.analytic_account_id.id
        so_lines = []
        for boq in self.boq_line_ids:
            if not boq.product_id:
                product = self.env['product.product'].create({
                    'name': boq.name,
                    'type': 'service',
                    'uom_id': boq.uom_id.id,
                    'uom_po_id': boq.uom_id.id,
                    'invoice_policy': 'order',
                })
                boq.product_id = product

            line_vals = {
                'product_id': boq.product_id.id,
                'name': '[%s] %s' % (boq.code, boq.name),
                'product_uom_qty': boq.volume_contract,
                'product_uom': boq.uom_id.id,
                'price_unit': boq.unit_price_contract,
            }
            if analytic_id:
                line_vals['analytic_distribution'] = {str(analytic_id): 100.0}
            so_lines.append((0, 0, line_vals))

        so = self.env['sale.order'].create({
            'partner_id': self.partner_id.id,
            'date_order': fields.Datetime.now(),
            'order_line': so_lines,
            'company_id': self.company_id.id,
        })
        so.action_confirm()

        # Link SO lines back to BOQ lines
        for so_line in so.order_line:
            boq_line = self.boq_line_ids.filtered(
                lambda b: b.product_id.id == so_line.product_id.id and not b.sale_order_line_id
            )
            if boq_line:
                boq_line[:1].sale_order_line_id = so_line

        self.sale_order_id = so

    def _create_budget(self):
        analytic_id = self.analytic_account_id.id

        # Aggregate budget amounts per cost type from BOQ × Rate Analysis
        amounts = {'material': 0.0, 'labor': 0.0, 'equipment': 0.0}
        for boq in self.boq_line_ids:
            if not boq.rate_analysis_id:
                continue
            ra = boq.rate_analysis_id
            vol = boq.volume_contract
            amounts['material'] += ra.total_material * vol
            amounts['labor'] += ra.total_labor * vol
            amounts['equipment'] += ra.total_equipment * vol

        lines = [
            (0, 0, {'account_id': analytic_id, 'budget_amount': amount})
            for amount in amounts.values() if amount
        ]
        # Fallback: no RA data → satu line dengan contract value
        if not lines:
            lines = [(0, 0, {'account_id': analytic_id, 'budget_amount': self.contract_value})]

        budget = self.env['budget.analytic'].create({
            'name': 'Budget — %s' % self.project_name,
            'date_from': self.date_start,
            'date_to': self.date_end,
            'budget_type': 'expense',
            'company_id': self.company_id.id,
            'budget_line_ids': lines,
        })
        self.budget_id = budget

    # Smart buttons
    def action_view_budget(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Job Budget'),
            'res_model': 'budget.analytic',
            'res_id': self.budget_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_sale_order(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_project(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'project.project',
            'res_id': self.project_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_work_orders(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Work Orders'),
            'res_model': 'construction.work.order',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id},
        }

    def action_view_billings(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('RA Billings'),
            'res_model': 'construction.ra.billing',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id},
        }

    def action_view_job_costing(self):
        self.ensure_one()
        costing = self.env['construction.job.costing'].search(
            [('contract_id', '=', self.id)], limit=1
        )
        if not costing:
            costing = self.env['construction.job.costing'].create({
                'contract_id': self.id,
            })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Job Costing'),
            'res_model': 'construction.job.costing',
            'res_id': costing.id,
            'view_mode': 'form',
            'target': 'current',
        }
