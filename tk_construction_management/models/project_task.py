# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
from odoo import fields, api, models


class ConProject(models.Model):
    """Construction Project"""
    _inherit = 'project.project'

    construction_project_id = fields.Many2one(
        'tk.construction.project')


class ConstructionTask(models.Model):
    """Construction Project Task"""
    _inherit = 'project.task'

    job_order_id = fields.Many2one('job.order', string="Work Order")
    is_inspection_task = fields.Boolean(string="Inspection Task")
    con_project_id = fields.Many2one(
        'tk.construction.project', string="Construction Project")


class ConstructionTimesheet(models.Model):
    """Construction External Timesheet"""
    _inherit = 'account.analytic.line'

    job_order_id = fields.Many2one(
        related="task_id.job_order_id", string="Work Order", store=True)
    sub_project_id = fields.Many2one(
        related="task_id.con_project_id", string="Construction Project", store=True)
    hourly_cost = fields.Monetary(related="employee_id.hourly_cost")
    total_amount = fields.Monetary(compute="_compute_total_amount")
    bill_id = fields.Many2one('account.move', string="Bill")
    is_validate = fields.Boolean(string="Is Validated")

    @api.depends('total_amount', 'hourly_cost', 'employee_id')
    def _compute_total_amount(self):
        """Compute Total Amount"""
        for rec in self:
            total_amount = 0.0
            if rec.hourly_cost and rec.unit_amount:
                total_amount = rec.hourly_cost * rec.unit_amount
            rec.total_amount = total_amount

    def action_validate_timesheet(self):
        """Validate Timesheet"""
        self.is_validate = True

    def action_tree_validate_timesheet(self):
        """Validate Timesheet Tree"""
        timesheets = self.browse(self.ids)
        for data in timesheets:
            data.action_validate_timesheet()

    def action_create_timesheet_bill(self):
        """Create Timesheet Bills"""
        form_view_ref = self.env.ref(
            'tk_construction_management.hr_timesheet_bill_view_form').id
        return {
            'name': 'Timesheet Bill',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'timesheet.billing',
            'view_id': form_view_ref,
            'target': 'new',
            'context': {
                'active_ids': self.ids,
            },
        }
