# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SubProjectBudget(models.Model):
    """Sub Project Budget"""
    _name = 'sub.project.budget'
    _description = "Sub Project Budget"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    active = fields.Boolean(default=True)
    name = fields.Char(string="Title")
    progress = fields.Float(string="Budget Utilization(%)",
                            compute="_compute_used_budget")
    total_budget_amount = fields.Monetary(compute="_compute_used_budget")
    utilization_amount = fields.Monetary(
        string="Budget Utilization", compute="_compute_used_budget")
    start_date = fields.Date()
    end_date = fields.Date()
    site_id = fields.Many2one('tk.construction.site', string="Project")
    sub_project_id = fields.Many2one(
        'tk.construction.project')
    responsible_id = fields.Many2one('res.users',
                                     default=lambda
                                         self: self.env.user and self.env.user.id or False)
    company_id = fields.Many2one('res.company', string="Company",
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id')
    status = fields.Selection([('draft', 'Draft'),
                               ('waiting_approval', 'Waiting Approval'),
                               ('approved', 'Approved'),
                               ('in_progress', 'In Progress'),
                               ('complete', 'Completed'),
                               ('cancel', 'Cancelled'),
                               ('reject', 'Rejected')], default='draft')
    budget_count = fields.Integer(
        string="Budget Line Count", compute="_compute_count")
    reject_reason = fields.Text()
    budget_line_ids = fields.One2many('project.budget',
                                      'sub_project_budget_id')
    is_budget_overspend = fields.Boolean(
        compute="_compute_is_budget_overspend")

    # Budget Line Confirmation
    budget_line_confirmation_ids = fields.One2many(
        comodel_name='budget.line.confirmation', inverse_name='budget_id')

    def _unlink_budget(self):
        for rec in self:
            if rec.status in ['approved', 'in_progress', 'complete']:
                raise ValidationError(
                    _("You cannot delete budget while in 'Approved', 'In Progress' and "
                      "'Complete' stage"))

    def _compute_count(self):
        """Compute Budget Count"""
        for rec in self:
            rec.budget_count = self.env['project.budget'].search_count(
                [('sub_project_budget_id', '=', rec.id)])

    @api.depends("progress")
    def _compute_is_budget_overspend(self):
        """Budget Overspend"""
        for rec in self:
            is_budget_overspend = False
            if rec.progress > 100:
                is_budget_overspend = True
            rec.is_budget_overspend = is_budget_overspend

    def action_view_budget_line(self):
        """View Budget Lines"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Budget'),
            'res_model': 'project.budget',
            'domain': [('sub_project_budget_id', '=', self.id)],
            'context': {'default_sub_project_budget_id': self.id},
            'view_mode': 'list,kanban,form',
            'target': 'current'
        }

    def action_department_approval(self):
        """Department Approvals"""
        self.status = 'waiting_approval'

    def action_approve_budget(self):
        """Approve Budget"""
        self.status = 'approved'

    def action_reject_budget(self):
        """Reject Budget"""
        self.status = 'reject'

    def action_complete_budget(self):
        """Complete Budget"""
        self.status = 'complete'

    def action_cancel_budget(self):
        """Cancel Budget"""
        self.status = 'cancel'

    def action_reset_draft_budget(self):
        """Reset Status Draft"""
        self.status = 'draft'

    @api.depends('budget_line_ids', 'budget_line_ids.budget', 'budget_line_ids.remaining_budget')
    def _compute_used_budget(self):
        """Budget Amount Calculation"""
        for rec in self:
            utilize_budget = 0.0
            total_budget_amount = 0.0
            remaining_budget_amount = 0.0
            for data in rec.budget_line_ids:
                total_budget_amount = total_budget_amount + data.budget
                remaining_budget_amount = remaining_budget_amount + data.remaining_budget
            utilize_budget = 100 - (
                (remaining_budget_amount * 100 / total_budget_amount)
                if total_budget_amount > 0 else 100)
            rec.progress = round(utilize_budget, 1)
            rec.total_budget_amount = total_budget_amount
            rec.utilization_amount = total_budget_amount - remaining_budget_amount


class ProjectBudget(models.Model):
    """Project Budget Lines"""
    _name = 'project.budget'
    _description = "Project Budget"
    _rec_name = 'job_type_id'

    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id')
    boq_budget_line_id = fields.Many2one('boq.budget')
    sub_project_budget_id = fields.Many2one(
        'sub.project.budget')
    project_id = fields.Many2one(
        related="sub_project_budget_id.sub_project_id")
    site_id = fields.Many2one(
        related="project_id.construction_site_id")
    job_type_id = fields.Many2one('job.type', string="Work Type")
    sub_category_ids = fields.Many2many(
        related="job_type_id.sub_category_ids", string="Sub Categories")
    sub_category_id = fields.Many2one('job.sub.category', string="Work Sub Type",
                                      domain="[('id','in',sub_category_ids)]")
    boq_qty = fields.Float(string="BOQ Qty")
    additional_qty = fields.Float(string="Add. Qty", help="Additional Qty")
    total_qty = fields.Float(string="Total Qty.", compute="_compute_total_qty")
    rate_analysis_id = fields.Many2one('rate.analysis')
    price_per_qty = fields.Monetary(
        string="Price / Qty", compute="_compute_rate_analysis_info", store=True)
    untaxed_amount = fields.Monetary(compute="_compute_rate_analysis_info", store=True)
    tax_amount = fields.Monetary(compute="_compute_rate_analysis_info", store=True)
    budget = fields.Monetary(string="Total Budget Amount",
                             compute="_compute_rate_analysis_info", store=True)
    # Spent
    material_spent = fields.Monetary(compute="_compute_budget_calculation")
    equipment_spent = fields.Monetary(compute="_compute_budget_calculation")
    labour_spent = fields.Monetary(compute="_compute_budget_calculation")
    overhead_spent = fields.Monetary(compute="_compute_budget_calculation")
    remaining_budget = fields.Monetary(compute="_compute_budget_calculation")

    # Spent in Percentage
    total_spent = fields.Float(
        string="Utilization(%)", compute="_compute_budget_calculation")
    boq_used_qty = fields.Float(
        string="Used Qty", compute="_compute_budget_calculation")

    @api.depends('boq_qty', 'additional_qty')
    def _compute_total_qty(self):
        for rec in self:
            rec.total_qty = rec.boq_qty + rec.additional_qty

    @api.depends('rate_analysis_id',
                 'rate_analysis_id.ra_type',
                 'rate_analysis_id.total_amount',
                 'rate_analysis_id.untaxed_amount',
                 'rate_analysis_id.tax_amount',
                 'total_qty')
    def _compute_rate_analysis_info(self):
        """Compute Rate Analysis Info"""
        for rec in self:
            untaxed_amount = 0.0
            tax_amount = 0.0
            price_per_qty = 0.0
            budget = 0.0
            if rec.rate_analysis_id:
                if rec.rate_analysis_id.ra_type == 'qty_per_unit':
                    price_per_qty = rec.rate_analysis_id.total_amount
                    untaxed_amount = rec.rate_analysis_id.untaxed_amount
                    tax_amount = rec.rate_analysis_id.tax_amount
                    budget = rec.total_qty * price_per_qty
                if rec.rate_analysis_id.ra_type == 'total_required_qty' and rec.total_qty > 0:
                    price_per_qty = rec.rate_analysis_id.total_amount / rec.total_qty
                    untaxed_amount = rec.rate_analysis_id.untaxed_amount / rec.total_qty
                    tax_amount = rec.rate_analysis_id.tax_amount / rec.total_qty
                    budget = rec.rate_analysis_id.total_amount
            rec.untaxed_amount = untaxed_amount
            rec.tax_amount = tax_amount
            rec.price_per_qty = price_per_qty
            rec.budget = budget

    @api.depends('project_id', 'sub_category_id', 'job_type_id', 'budget', 'total_qty')
    def _compute_budget_calculation(self):
        """Compute Budget Calculation"""
        for rec in self:
            budget_phase_ids = self.env['job.costing'].search(
                [('project_id', '=', rec.project_id.id),
                 ('activity_id', '=', rec.job_type_id.id)]).mapped('id')
            domain = [('project_id', '=', rec.project_id.id),
                      ('work_type_id', '=', rec.job_type_id.id),
                      ('sub_category_id', '=',
                       rec.sub_category_id.id), ('state', '=', 'complete'),
                      ('job_sheet_id', 'in', budget_phase_ids)]
            material_spent = sum(self.env['order.material.line'].search(
                domain).mapped('total_price'))
            equipment_spent = sum(self.env['order.equipment.line'].search(
                domain).mapped('total_cost'))
            labour_spent = sum(self.env['order.labour.line'].search(
                domain).mapped('sub_total'))
            overhead_spent = sum(self.env['order.overhead.line'].search(
                domain).mapped('sub_total'))
            remaining_budget = rec.budget - \
                               (material_spent + equipment_spent + labour_spent + overhead_spent)
            total_spent = 100 - \
                          ((remaining_budget * 100 / rec.budget) if rec.budget > 0 else 100)
            boq_used_qty = rec.total_qty - (
                (remaining_budget * rec.total_qty / rec.budget)
                if rec.budget > 0 else rec.total_qty)
            rec.equipment_spent = equipment_spent
            rec.labour_spent = labour_spent
            rec.overhead_spent = overhead_spent
            rec.material_spent = material_spent
            rec.remaining_budget = remaining_budget
            rec.total_spent = round(total_spent, 1)
            rec.boq_used_qty = boq_used_qty

    def action_view_material_budget(self):
        """View Material Budget"""
        budget_phase_ids = self.env['job.costing'].search(
            [('project_id', '=', self.project_id.id),
             ('activity_id', '=', self.job_type_id.id)]).mapped('id')
        domain = [('project_id', '=', self.project_id.id),
                  ('work_type_id', '=', self.job_type_id.id),
                  ('sub_category_id', '=',
                   self.sub_category_id.id), ('state', '=', 'complete'),
                  ('job_sheet_id', 'in', budget_phase_ids)]
        ids = self.env['order.material.line'].search(domain).mapped('id')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Material'),
            'res_model': 'order.material.line',
            'domain': [('id', 'in', ids)],
            'context': {'create': False},
            'view_mode': 'list',
            'target': 'current'
        }

    def action_view_equipment_budget(self):
        """View Equipment Budget"""
        budget_phase_ids = self.env['job.costing'].search(
            [('project_id', '=', self.project_id.id),
             ('activity_id', '=', self.job_type_id.id)]).mapped('id')
        domain = [('project_id', '=', self.project_id.id),
                  ('work_type_id', '=', self.job_type_id.id),
                  ('sub_category_id', '=',
                   self.sub_category_id.id), ('state', '=', 'complete'),
                  ('job_sheet_id', 'in', budget_phase_ids)]
        ids = self.env['order.equipment.line'].search(domain).mapped('id')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Equipment'),
            'res_model': 'order.equipment.line',
            'domain': [('id', 'in', ids)],
            'context': {'create': False},
            'view_mode': 'list',
            'target': 'current'
        }

    def action_view_labour_budget(self):
        """View Labour Budget"""
        budget_phase_ids = self.env['job.costing'].search(
            [('project_id', '=', self.project_id.id),
             ('activity_id', '=', self.job_type_id.id)]).mapped('id')
        domain = [('project_id', '=', self.project_id.id),
                  ('work_type_id', '=', self.job_type_id.id),
                  ('sub_category_id', '=',
                   self.sub_category_id.id), ('state', '=', 'complete'),
                  ('job_sheet_id', 'in', budget_phase_ids)]
        ids = self.env['order.labour.line'].search(domain).mapped('id')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Labour'),
            'res_model': 'order.labour.line',
            'domain': [('id', 'in', ids)],
            'context': {'create': False},
            'view_mode': 'list',
            'target': 'current'
        }

    def action_view_overhead_budget(self):
        """View Overhead Budget"""
        budget_phase_ids = self.env['job.costing'].search(
            [('project_id', '=', self.project_id.id),
             ('activity_id', '=', self.job_type_id.id)]).mapped('id')
        domain = [('project_id', '=', self.project_id.id),
                  ('work_type_id', '=', self.job_type_id.id),
                  ('sub_category_id', '=',
                   self.sub_category_id.id), ('state', '=', 'complete'),
                  ('job_sheet_id', 'in', budget_phase_ids)]
        ids = self.env['order.overhead.line'].search(domain).mapped('id')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Overhead'),
            'res_model': 'order.overhead.line',
            'domain': [('id', 'in', ids)],
            'context': {'create': False},
            'view_mode': 'list',
            'target': 'current'
        }

    def action_create_rate_analysis(self):
        """Create rate analysis from tree view"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Rate Analysis'),
            'res_model': 'rate.analysis',
            'context': {},
            'view_mode': 'form',
            'target': 'new'
        }


class BudgetLineConfirmation(models.Model):
    """Budget Line Confirmation"""
    _name = 'budget.line.confirmation'
    _description = 'Budget line confirmation'
    _rec_name = 'budget_id'

    budget_id = fields.Many2one(
        comodel_name='sub.project.budget')
    type = fields.Selection([('insert', 'Insert BOQ Line'),
                             ('update', 'Update BOQ Line Qty'),
                             ('remove', 'Remove BOQ Line')], default='insert',
                            string="Action Type")
    responsible_id = fields.Many2one('res.users', string="Requested By",
                                     default=lambda
                                         self: self.env.user and self.env.user.id or False)
    status = fields.Selection([('requested', 'Requested'),
                               ('approved', 'Approved'), ('rejected', 'Rejected')],
                              default='requested')
    date = fields.Date()
    is_use_measure = fields.Boolean()
    boq_budget_line_id = fields.Many2one('boq.budget', string="BOQ Line")
    work_type_id = fields.Many2one('job.type')
    work_subtype_id = fields.Many2one('job.sub.category')
    qty = fields.Float(string="Qty.", default=1.0)
    length = fields.Float()
    width = fields.Float()
    height = fields.Float()
    total_qty = fields.Float()

    old_qty = fields.Float(default=1.0)
    old_length = fields.Float()
    old_width = fields.Float()
    old_height = fields.Float()
    old_total_qty = fields.Float()

    # Reject
    reject_reason = fields.Text()

    def action_approve_budget_line(self):
        """Approve Budget Line"""
        if self.type == 'insert':
            self._process_inset_operation()
        if self.type == 'update':
            self._process_update_operation()
        if self.type == 'remove':
            self._process_remove_operation()
        self.status = 'approved'

    def action_reject_budget_line(self):
        """Reject Budget Line"""
        self.status = 'rejected'

    def action_reset_draft(self):
        """Reset Budget Line"""
        self.status = 'requested'

    def _process_inset_operation(self):
        """Process Budget Line Insert Operation"""
        existing_boq_lines = self.budget_id.budget_line_ids.filtered(
            lambda line: line.job_type_id.id == self.work_type_id.id
                         and line.sub_category_id.id == self.work_subtype_id.id
        )
        if existing_boq_lines:
            raise ValidationError(_(
                "A line with work type '%s' and subtype '%s' already exists."
            ) % (self.work_type_id.name, self.work_subtype_id.name))
        boq_line_id = self.env['boq.budget'].create({
            'activity_id': self.work_type_id.id,
            'sub_activity_id': self.work_subtype_id.id,
            'qty': self.qty,
            'length': self.length,
            'height': self.height,
            'width': self.width,
            'project_id': self.budget_id.sub_project_id.id
        })
        new_budget_line_id = self.env['project.budget'].create({
            'sub_project_budget_id': self.budget_id.id,
            'job_type_id': self.work_type_id.id,
            'sub_category_id': self.work_subtype_id.id,
            'boq_qty': boq_line_id.total_qty,
            'boq_budget_line_id': boq_line_id.id
        })
        boq_line_id.budget_line_id = new_budget_line_id.id

    def _process_update_operation(self):
        """Process Budget update line operation"""
        if self.boq_budget_line_id.budget_line_id:
            self.boq_budget_line_id.budget_line_id.boq_qty = self.total_qty
            self.boq_budget_line_id.write({
                'length': self.length,
                'height': self.height,
                'width': self.width,
                'qty': self.qty,
            })
        else:
            record = self.env['project.budget'].sudo().search(
                [('job_type_id', '=', self.work_type_id.id),
                 ('sub_category_id', '=', self.work_subtype_id.id),
                 ('sub_project_budget_id', '=', self.budget_id.id)], limit=1)
            if record:
                record.boq_qty = self.total_qty
                self.boq_budget_line_id.write({
                    'length': self.length,
                    'height': self.height,
                    'width': self.width,
                    'qty': self.qty,
                    'budget_line_id': record.id
                })

    def _process_remove_operation(self):
        """Process Budget Remove Operation"""
        if self.boq_budget_line_id.budget_line_id:
            self.boq_budget_line_id.budget_line_id.unlink()
            self.boq_budget_line_id.unlink()
        else:
            record = self.env['project.budget'].sudo().search(
                [('job_type_id', '=', self.work_type_id.id),
                 ('sub_category_id', '=', self.work_subtype_id.id),
                 ('sub_project_budget_id', '=', self.budget_id.id)], limit=1)
            if record:
                record.unlink()
                self.boq_budget_line_id.unlink()
