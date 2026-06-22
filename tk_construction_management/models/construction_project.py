# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
import base64
from io import BytesIO
import xlwt
from odoo import fields, api, models, _
from odoo.exceptions import ValidationError, UserError


def is_float(str_vals):
    """Check if string is Float or not
    :param str_vals: String
    :return: True if string is Float or not
    """
    vals = str_vals.replace("-", "").replace(".", "").isnumeric()
    return bool(vals)


class ConstructionProject(models.Model):
    """Construction Sub Project"""
    _name = 'tk.construction.project'
    _description = "Construction Project"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    active = fields.Boolean(default=True)
    name = fields.Char(string="Title", tracking=True)
    start_date = fields.Date(string="Schedule Start Date", tracking=True)
    end_date = fields.Date(string="Schedule End Date", tracking=True)
    project_progress = fields.Float(
        related="budget_id.progress", string="Progress", tracking=True)
    construction_site_id = fields.Many2one(
        'tk.construction.site', string="Project ", tracking=True)
    responsible_id = fields.Many2one('res.users',
                                     default=lambda
                                         self: self.env.user and self.env.user.id or False,
                                     string="Created By")
    stage = fields.Selection([('draft', 'Draft'),
                              ('Planning', 'Planning'),
                              ('Procurement', 'Procurement'),
                              ('Construction', 'Construction'),
                              ('Handover', 'Handover')], default="draft",
                             tracking=True)
    warehouse_id = fields.Many2one(
        'stock.warehouse', tracking=True)
    code = fields.Char(tracking=True)
    project_id = fields.Many2one(
        'project.project', tracking=True)
    engineer_ids = fields.Many2many(
        'hr.employee', tracking=True)

    # Address
    zip = fields.Char(string='Pin Code')
    street = fields.Char(string='Street1')
    street2 = fields.Char()
    city = fields.Char()
    country_id = fields.Many2one('res.country')
    state_id = fields.Many2one("res.country.state", readonly=False, store=True,
                               domain="[('country_id', '=?', country_id)]")
    longitude = fields.Char()
    latitude = fields.Char()

    # BOQ Details
    is_use_measure = fields.Boolean(
        string="Is use of (LENGTH x WIDTH x HEIGHT ) ?")
    boq_budget_ids = fields.One2many(
        'boq.budget', 'project_id', string="Budget ")

    # Budget
    budget_id = fields.Many2one('sub.project.budget')
    # Standard Odoo analytic budget (account_budget module), used for PO budget control
    budget_analytic_id = fields.Many2one(
        'budget.analytic', string='Analytic Budget', copy=False, tracking=True)

    # One2Many
    document_ids = fields.One2many(
        'project.documents', 'project_id')
    policy_ids = fields.One2many(
        'project.insurance', 'project_id', string="Insurance")
    expense_ids = fields.One2many(
        'extra.expense', 'project_id')
    phase_ids = fields.One2many('job.costing', 'project_id')
    progress_billing_ids = fields.One2many(
        'progress.billing', 'project_id')

    # Count & Totals
    job_sheet_count = fields.Integer(compute="_compute_count")
    job_order_count = fields.Integer(compute="_compute_count")
    mrq_count = fields.Integer(compute="_compute_count")
    mrq_po_count = fields.Integer(compute="_compute_count")
    jo_po_count = fields.Integer(compute="_compute_count")
    inspection_task_count = fields.Integer(compute="_compute_count")
    task_count = fields.Integer(compute="_compute_count")
    budget_count = fields.Integer(compute="_compute_count")
    progress_count = fields.Integer(compute="_compute_count")

    # Company
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)

    # Create, Write, Unlink, Constrain
    @api.model_create_multi
    def create(self, vals):
        """Sub Project Create"""
        res = super().create(vals)
        for rec in res:
            data = {
                'name': rec.name + "'s Project",
                'construction_project_id': rec.id,
                'company_id': self.env.company.id,
                'privacy_visibility': 'followers'
            }
            project_id = self.env['project.project'].create(data)
            rec.project_id = project_id.id
            task_stage = self.env['project.task.type'].sudo().search(
                [('active', '=', True), ('user_id', '=', False)])
            for data in task_stage:
                ids = data.project_ids.ids
                ids.append(project_id.id)
                data.project_ids = ids
        return res

    @api.ondelete(at_uninstall=False)
    def _unlink_sub_project(self):
        """Unlink Sub Project"""
        for rec in self:
            if rec.budget_id:
                raise ValidationError(_("Budget is created for this sub project, "
                                        "delete it first."))
            if rec.phase_ids:
                raise ValidationError(_("Phases are created for this sub project,"
                                        "please delete it first."))

    @api.constrains('boq_budget_ids')
    def _check_sub_activity(self):
        """Check Sub Activity"""
        for rec in self:
            activity_counts = {}
            for activity in rec.boq_budget_ids:
                key = (activity.activity_id.id, activity.sub_activity_id.id)
                if key in activity_counts:
                    activity_counts[key] += 1
                else:
                    activity_counts[key] = 1
            duplicate = [pair for pair,
            count in activity_counts.items() if count > 1]
            if duplicate:
                raise ValidationError(_(
                    "Duplicate work type and sub work type pair found."))

    @api.onchange('construction_site_id')
    def _onchange_site_address(self):
        """Onchange Site Address"""
        for rec in self:
            if rec.construction_site_id:
                rec.zip = rec.construction_site_id.zip
                rec.street = rec.construction_site_id.street
                rec.street2 = rec.construction_site_id.street2
                rec.city = rec.construction_site_id.city
                rec.state_id = rec.construction_site_id.state_id.id
                rec.country_id = rec.construction_site_id.country_id.id
                rec.start_date = rec.construction_site_id.start_date
                rec.end_date = rec.construction_site_id.end_date

    @api.onchange('longitude', 'latitude')
    def _onchange_validate_longitude_and_latitude(self):
        """Add Validation on latitude and longitude """
        for rec in self:
            if rec.longitude and not is_float(rec.longitude):
                raise ValidationError(_("Longitude values must be float."))
            if rec.latitude and not is_float(rec.latitude):
                raise ValidationError(_("Latitude values must be float."))
            if rec.longitude and is_float(rec.longitude) and (
                    float(rec.longitude) > 180 or float(rec.longitude) < -180):
                raise ValidationError(
                    _("Longitude must be in range of -180 to 180"))
            if rec.latitude and is_float(rec.latitude) and (
                    float(rec.latitude) > 90 or float(rec.latitude) < -90):
                raise ValidationError(
                    _("Latitude must be in range of -90 to 90"))

    # Compute
    def _compute_count(self):
        """Smart Button Count"""
        for rec in self:
            rec.job_sheet_count = self.env['job.costing'].search_count(
                [('project_id', '=', rec.id)])
            rec.job_order_count = self.env['job.order'].search_count(
                [('project_id', '=', rec.id)])
            rec.mrq_count = self.env['material.requisition'].search_count(
                [('project_id', '=', rec.id)])
            rec.mrq_po_count = self.env['purchase.order'].search_count(
                [('project_id', '=', rec.id)])
            job_order_ids = self.env['job.order'].search(
                [('project_id', '=', rec.id)]).mapped('id')
            po_ids = self.env['purchase.order'].search(
                [('job_order_id', 'in', job_order_ids)]).mapped('id')
            rec.jo_po_count = len(po_ids)
            rec.task_count = self.env['project.task'].search_count(
                [('con_project_id', '=', rec.id), ('is_inspection_task', '=', False)])
            rec.inspection_task_count = self.env['project.task'].search_count(
                [('con_project_id', '=', rec.id), ('is_inspection_task', '=', True)])
            rec.budget_count = self.env['project.budget'].search_count(
                [('sub_project_budget_id', '=', rec.budget_id.id)])
            rec.progress_count = self.env['progress.billing'].search_count(
                [('project_id', '=', rec.id)])

    # Smart Button
    def action_gmap_location(self):
        """Gmap Location"""
        if self.longitude and self.latitude:
            longitude = self.longitude
            latitude = self.latitude
            http_url = 'https://maps.google.com/maps?q=loc:' + latitude + ',' + longitude
            return {
                'type': 'ir.actions.act_url',
                'target': 'new',
                'url': http_url,
            }
        raise ValidationError(
            _("! Enter Proper Longitude and Latitude Values"))

    def action_create_budget(self):
        self.ensure_one()

        # Step 1 — Prerequisites
        if not self.construction_site_id:
            raise UserError(_("Please set the Construction Site before creating a budget."))
        if not self.start_date or not self.end_date:
            raise UserError(_("Please set Start Date and End Date before creating a budget."))

        # Budget name derived from the construction project title
        budget_name = self.name or self.construction_site_id.name

        # Duplicate guard: prevent two budget.analytic records with the same name
        existing = self.env['budget.analytic'].search([('name', '=', budget_name)], limit=1)
        if existing:
            raise UserError(_("A budget named '%s' already exists.") % budget_name)

        # Step 2 — Create budget.analytic header
        # Required fields: name, date_from, date_to (state='draft', budget_type='expense' by default)
        budget = self.env['budget.analytic'].create({
            'name': budget_name,
            'date_from': self.start_date,
            'date_to': self.end_date,
            'company_id': self.env.company.id,
            'user_id': self.env.user.id,
        })

        # Step 3 — Create an initial budget.line tied to the header
        # budget_analytic_id is the only required field; budget_amount defaults to 0
        # Note: analytic account (plan field) is intentionally left unset here because
        # tk.construction.site is not an account.analytic.account record.
        # Set it manually on the budget form after creation if needed.
        self.env['budget.line'].create({
            'budget_analytic_id': budget.id,
            'budget_amount': 0.0,
        })

        # Step 4 — Link budget back so the button auto-hides
        self.budget_analytic_id = budget.id

        return {
            'type': 'ir.actions.act_window',
            'name': _('Analytic Budget'),
            'res_model': 'budget.analytic',
            'res_id': budget.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_job_sheet(self):
        """View job sheet"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Project Phase(WBS)'),
            'res_model': 'job.costing',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id, 'create': False},
            'view_mode': 'list,form',
            'target': 'current'
        }

    def action_view_job_order(self):
        """View job order"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Work Order'),
            'res_model': 'job.order',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id, 'create': False},
            'view_mode': 'list,form',
            'target': 'current'
        }

    def action_view_material_requisition(self):
        """View material requisition"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Material Requisition'),
            'res_model': 'material.requisition',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id, 'create': False},
            'view_mode': 'list,form',
            'target': 'current'
        }

    def action_view_mrq_purchase_orders(self):
        """View MREQ purchase orders"""
        ids = self.env['purchase.order'].search(
            [('project_id', '=', self.id)]).mapped('id')
        return {
            'type': 'ir.actions.act_window',
            'name': _('MRQ Purchase Order'),
            'res_model': 'purchase.order',
            'domain': [('id', 'in', ids)],
            'context': {'create': False},
            'view_mode': 'list,form',
            'target': 'current'
        }

    def action_view_jo_purchase_orders(self):
        """View Job order purchase order"""
        job_order_ids = self.env['job.order'].search(
            [('project_id', '=', self.id)]).mapped('id')
        po_ids = self.env['purchase.order'].search(
            [('job_order_id', 'in', job_order_ids)]).mapped('id')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Work Order PO'),
            'res_model': 'purchase.order',
            'domain': [('id', 'in', po_ids)],
            'context': {'create': False, 'group_by': 'purchase_order'},
            'view_mode': 'list,form',
            'target': 'current'
        }

    def action_view_project_task(self):
        """View project task"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Task'),
            'res_model': 'project.task',
            'domain': [('con_project_id', '=', self.id), ('is_inspection_task', '=', False)],
            'context': {'default_con_project_id': self.id,
                        'default_project_id': self.project_id.id,
                        'create': False},
            'view_mode': 'kanban,list,form',
            'target': 'current'
        }

    def action_view_project_task_inspection(self):
        """View Task inspection"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Inspection Task'),
            'res_model': 'project.task',
            'domain': [('con_project_id', '=', self.id), ('is_inspection_task', '=', True)],
            'context': {'default_con_project_id': self.id,
                        'default_project_id': self.project_id.id,
                        'default_is_inspection_task': True,
                        'default_priority': '1'},
            'view_mode': 'list,form,kanban',
            'target': 'current'
        }

    def action_view_budget(self):
        """View Budget"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Budget'),
            'res_model': 'project.budget',
            'domain': [('sub_project_budget_id', '=', self.budget_id.id)],
            'context': {'default_sub_project_budget_id': self.budget_id.id, 'create': False},
            'view_mode': 'list,kanban,form',
            'target': 'current'
        }

    def action_view_progress_bill(self):
        """View progress bills"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Progress Billing'),
            'res_model': 'progress.billing',
            'domain': [('project_id', '=', self.id)],
            'context': {'default_project_id': self.id},
            'view_mode': 'list,form',
            'target': 'current'
        }

    # Button
    def action_project_planning(self):
        """Project status : Planning"""
        self.stage = 'Planning'

    def action_stage_procurement(self):
        """Project status : procurement"""
        if not self.warehouse_id:
            msg = "Please choose a warehouse to proceed to the next stage of construction process"
            message = {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'info',
                    'message': msg,
                    'sticky': False,
                }
            }
            return message
        if not self.budget_id:
            msg = "Please create a budget to proceed to the next stage of construction process"
            message = {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'info',
                    'message': msg,
                    'sticky': False,
                }
            }
            return message
        self.stage = 'Procurement'
        return True

    def action_stage_construction(self):
        """Project status : Construction"""
        self.stage = 'Construction'

    def action_stage_handover(self):
        """Project status : Handover"""
        phase_completed = True
        phase_record = self.env['job.costing'].search(
            [('project_id', '=', self.id)])
        for data in phase_record:
            if data.status != 'complete':
                phase_completed = False
                break
        if not phase_completed:
            message = {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'info',
                    'message': "Please complete all the phases related to this project to "
                               "handover this project.",
                    'sticky': False,
                }
            }
            return message
        self.stage = 'Handover'
        return True

    def get_float_time(self, t):
        """Get float time"""
        hour, minute = divmod(t, 1)
        minute *= 60
        result = '{}:{}'.format(int(hour), int(minute))
        return result

    def action_print_budget_excel_report(self):
        """Print Budget excel report"""
        workbook = xlwt.Workbook(encoding='utf-8')
        sheet1 = workbook.add_sheet('Budget Details', cell_overwrite_ok=True)
        sheet1.show_grid = False
        sheet1.col(0).width = 400
        sheet1.col(3).width = 600
        sheet1.col(9).width = 600
        sheet1.row(4).height = 400
        sheet1.row(5).height = 200
        sheet1.row(6).height = 400
        sheet1.row(7).height = 200
        sheet1.row(8).height = 400
        sheet1.row(9).height = 200
        sheet1.row(10).height = 400
        sheet1.row(11).height = 200
        sheet1.row(12).height = 400
        sheet1.row(17).height = 400
        sheet1.col(12).width = 5000
        sheet1.col(13).width = 4000
        sheet1.col(14).width = 5000
        sheet1.col(15).width = 5000
        sheet1.col(16).width = 8000
        sheet1.col(17).width = 7000
        sheet1.col(18).width = 7000
        sheet1.col(19).width = 7000
        sheet1.col(20).width = 7000
        sheet1.col(21).width = 7000
        sheet1.col(22).width = 5000
        sheet1.row(14).height = 600
        border_squre = xlwt.Borders()
        border_squre.bottom = xlwt.Borders.HAIR
        border_squre.bottom_colour = xlwt.Style.colour_map["sea_green"]
        al = xlwt.Alignment()
        al.horz = xlwt.Alignment.HORZ_LEFT
        al.vert = xlwt.Alignment.VERT_CENTER
        date_format = xlwt.XFStyle()
        date_format.num_format_str = 'mm/dd/yyyy'
        date_format.font.name = "Century Gothic"
        date_format.borders = border_squre
        date_format.alignment = al
        date_format.font.colour_index = 0x36
        date_format.font.bold = 1
        sheet1.set_panes_frozen(True)
        sheet1.set_horz_split_pos(18)
        sheet1.remove_splits = True
        title = xlwt.easyxf(
            "font: height 350, name Century Gothic, bold on, color_index blue_gray;"
            " align: vert center, horz center;"
            "border: bottom thick, bottom_color sea_green;")
        values = xlwt.easyxf(
            "font:name Century Gothic, bold on, color_index blue_gray;"
            " align: vert center, horz left;"
            "border: bottom hair, bottom_color sea_green;")
        line_percentage_value = xlwt.easyxf(
            "font:name Century Gothic, bold on, color_index blue_gray;"
            " align: vert center, horz center;"
            "border: bottom hair, bottom_color blue_gray, right hair,right_color blue_gray;")
        line_values = xlwt.easyxf(
            "font:name Century Gothic;"
            " align: vert center, horz center;"
            "border: bottom hair, bottom_color blue_gray, right hair,right_color blue_gray,left hair,left_color blue_gray;")
        line_amount_values = xlwt.easyxf(
            "font:name Century Gothic;"
            " align: vert center, horz right;"
            "border: bottom hair, bottom_color blue_gray, right hair,right_color blue_gray,left hair,left_color blue_gray;")
        line_amount_sub_title = xlwt.easyxf(
            "font: height 185, name Century Gothic, bold on, color_index gray80; "
            "align: vert center, horz right; "
            "border: top hair, bottom hair, left hair, right hair, "
            "top_color gray50, bottom_color gray50, left_color gray50, right_color gray50")
        sub_title = xlwt.easyxf(
            "font: height 185, name Century Gothic, bold on, color_index gray80; "
            "align: vert center, horz center; "
            "border: top hair, bottom hair, left hair, right hair, "
            "top_color gray50, bottom_color gray50, left_color gray50, right_color gray50")
        # Budget Details
        budget_amount = str(self.budget_id.currency_id.symbol) + \
                        " " + str(self.budget_id.total_budget_amount)
        utilization_amount = str(self.budget_id.currency_id.symbol) + " " + str(
            self.budget_id.utilization_amount)
        utilization_percentage = str(self.budget_id.progress) + " %"
        sheet1.write_merge(0, 2, 1, 11, "Budget Details", title)
        sheet1.write_merge(4, 4, 1, 2, "Project", sub_title)
        sheet1.write_merge(4, 4, 4, 5, self.construction_site_id.name, values)
        sheet1.write_merge(6, 6, 1, 2, "Sub Project", sub_title)
        sheet1.write_merge(6, 6, 4, 5, self.name, values)
        sheet1.write_merge(4, 4, 7, 8, "Start Date", sub_title)
        sheet1.write_merge(
            4, 4, 10, 11, self.budget_id.start_date, date_format)
        sheet1.write_merge(6, 6, 7, 8, "End Date", sub_title)
        sheet1.write_merge(6, 6, 10, 11, self.budget_id.end_date, date_format)
        sheet1.write_merge(8, 8, 1, 2, "Total Budget Amount", sub_title)
        sheet1.write_merge(8, 8, 4, 5, budget_amount, values)
        sheet1.write_merge(10, 10, 1, 2, "Budget Utilization", sub_title)
        sheet1.write_merge(10, 10, 4, 5, utilization_amount, values)
        sheet1.write_merge(12, 12, 1, 2, "Utilization(%)", sub_title)
        sheet1.write_merge(12, 12, 4, 5, utilization_percentage, values)
        # Budget Lines
        sheet1.write_merge(14, 15, 1, 22, "Budget Lines", title)
        sheet1.write_merge(17, 17, 1, 3, "Work Type", sub_title)
        sheet1.write_merge(17, 17, 4, 6, "Work Sub Type", sub_title)
        sheet1.write(17, 7, "BOQ Qty", line_amount_sub_title)
        sheet1.write_merge(17, 17, 8, 10, "Additional Qty",
                           line_amount_sub_title)
        sheet1.write(17, 11, "Total Qty", line_amount_sub_title)
        sheet1.write(17, 12, "Rate Analysis", sub_title)
        sheet1.write(17, 13, "Price / Qty", line_amount_sub_title)
        sheet1.write(17, 14, "Untaxed", line_amount_sub_title)
        sheet1.write(17, 15, "Tax Amount", line_amount_sub_title)
        sheet1.write(17, 16, "Total Budget", line_amount_sub_title)
        sheet1.write(17, 17, "Material Spent", line_amount_sub_title)
        sheet1.write(17, 18, "Equipment Spent", line_amount_sub_title)
        sheet1.write(17, 19, "Labour Spent", line_amount_sub_title)
        sheet1.write(17, 20, "Overhead Spent", line_amount_sub_title)
        sheet1.write(17, 21, "Remaining Budget", line_amount_sub_title)
        sheet1.write(17, 22, "Utilization(%)", sub_title)
        col = 18
        for data in self.budget_id.budget_line_ids:
            sheet1.row(col).height = 400
            sheet1.write_merge(
                col, col, 1, 3, data.job_type_id.name, line_values)
            sheet1.write_merge(
                col, col, 4, 6, data.sub_category_id.name, line_values)
            sheet1.write(col, 7, data.boq_qty, line_amount_values)
            sheet1.write_merge(
                col, col, 8, 10, data.additional_qty, line_amount_values)
            sheet1.write(col, 11, (data.boq_qty +
                                   data.additional_qty), line_amount_values)
            sheet1.write(col, 12, ((data.rate_analysis_id.name)
                                   if data.rate_analysis_id else ""), line_values)
            sheet1.write(col, 13, (str(self.budget_id.currency_id.symbol) +
                                   " " + str(data.price_per_qty)), line_amount_values)
            sheet1.write(col, 14, (str(self.budget_id.currency_id.symbol) +
                                   " " + str(data.untaxed_amount)), line_amount_values)
            sheet1.write(col, 15, (str(self.budget_id.currency_id.symbol) +
                                   " " + str(data.tax_amount)), line_amount_values)
            sheet1.write(col, 16, (str(self.budget_id.currency_id.symbol) +
                                   " " + str(data.budget)), line_amount_values)
            sheet1.write(col, 17, (str(self.budget_id.currency_id.symbol) +
                                   " " + str(data.material_spent)), line_amount_values)
            sheet1.write(col, 18, (str(self.budget_id.currency_id.symbol) +
                                   " " + str(data.equipment_spent)), line_amount_values)
            sheet1.write(col, 19, (str(self.budget_id.currency_id.symbol) +
                                   " " + str(data.labour_spent)), line_amount_values)
            sheet1.write(col, 20, (str(self.budget_id.currency_id.symbol) +
                                   " " + str(data.overhead_spent)), line_amount_values)
            sheet1.write(col, 21, (str(self.budget_id.currency_id.symbol) +
                                   " " + str(data.remaining_budget)), line_amount_values)
            sheet1.write(
                col, 22, (str(data.total_spent) + " " + "%"), line_percentage_value)
            col = col + 1

        # Budget Spent
        self.get_budget_spent(workbook=workbook)

        # Print Report
        stream = BytesIO()
        workbook.save(stream)
        out = base64.encodebytes(stream.getvalue())
        attachment = self.env['ir.attachment'].sudo()
        filename = 'Budget Report' + ".xls"
        attachment_id = attachment.create(
            {'name': filename,
             'type': 'binary',
             'public': False,
             'datas': out})
        if attachment_id:
            report = {
                'type': 'ir.actions.act_url',
                'url': '/web/content/%s?download=true' % (attachment_id.id),
                'target': 'self',
            }
            return report
        return True

    def get_budget_spent(self, workbook):
        """Budget Spent Excel Report"""
        title = xlwt.easyxf(
            "font: height 300, name Century Gothic, bold on, color_index blue_gray;"
            " align: vert center, horz center;"
            "border: bottom thick, bottom_color sea_green;")
        title2 = xlwt.easyxf(
            "font: height 250, name Century Gothic, bold on, color_index blue_gray;"
            " align: vert center, horz left;"
            "border: bottom thin, bottom_color sea_green;")
        title3 = xlwt.easyxf(
            "font: height 250, name Century Gothic, bold on;"
            " align: vert center, horz right;"
            "border: bottom thin, bottom_color sea_green;")
        line_amount_sub_title = xlwt.easyxf(
            "font: height 185, name Century Gothic, bold on, color_index gray80; "
            "align: vert center, horz right; "
            "border: top hair, bottom hair, left hair, right hair, "
            "top_color gray50, bottom_color gray50, left_color gray50, right_color gray50")
        line_values = xlwt.easyxf(
            "font:name Century Gothic;"
            " align: vert center, horz center;"
            "border: bottom hair, bottom_color blue_gray, right hair,right_color blue_gray,left hair,left_color blue_gray;")
        sub_title = xlwt.easyxf(
            "font: height 185, name Century Gothic, bold on, color_index gray80; "
            "align: vert center, horz center; "
            "border: top hair, bottom hair, left hair, right hair, "
            "top_color gray50, bottom_color gray50, left_color gray50, right_color gray50")
        sub_title2 = xlwt.easyxf(
            "font: height 200, name Century Gothic, bold on, color_index gray80; "
            "align: vert center, horz left; "
            "border: bottom hair,"
            "bottom_color sea_green;")
        sub_title_amount = xlwt.easyxf(
            "font: height 200, name Century Gothic, bold on, color_index gray80; "
            "align: vert center, horz right; "
            "border: bottom hair,"
            "bottom_color sea_green;")
        horiz_double_line = xlwt.easyxf("border: top double, top_color gray50")
        import re as _re
        # xlwt checks duplicates case-insensitively; mirror that here and
        # seed the set with any sheets the caller already added to the workbook.
        _used_sheet_names = set(workbook._Workbook__worksheet_idx_from_name.keys())
        for data in self.budget_id.budget_line_ids:
            budget_phase_ids = self.env['job.costing'].search(
                [('project_id', '=', self.id), ('activity_id', '=', data.job_type_id.id)]).mapped(
                'id')
            domain = [('project_id', '=', self.id), ('work_type_id', '=', data.job_type_id.id),
                      ('sub_category_id', '=',
                       data.sub_category_id.id), ('state', '=', 'complete'),
                      ('job_sheet_id', 'in', budget_phase_ids)]
            material_spent_rec = self.env['order.material.line'].search(domain)
            equip_spent_rec = self.env['order.equipment.line'].search(domain)
            labour_spent_rec = self.env['order.labour.line'].search(domain)
            overhead_spent_rec = self.env['order.overhead.line'].search(domain)
            sheet_name = data.job_type_id.name + \
                         "(" + data.sub_category_id.name + ")"
            _sanitized = _re.sub(r'[\[\]:*?/\\]', '', sheet_name)[:31]
            _counter = 1
            while _sanitized.lower() in _used_sheet_names:
                _suffix = " (%d)" % _counter
                _sanitized = (_re.sub(r'[\[\]:*?/\\]', '', sheet_name)[:31 - len(_suffix)] + _suffix)
                _counter += 1
            _used_sheet_names.add(_sanitized.lower())
            sheet = workbook.add_sheet(_sanitized, cell_overwrite_ok=True)
            sheet.show_grid = False
            row = 0
            sheet.row(4).height = 400
            sheet.row(6).height = 400
            sheet.write_merge(0, 2, 0, 6, sheet_name, title)
            sheet.write(4, 0, "Total Budget", sub_title2)
            sheet.write(4, 1, (str(self.budget_id.currency_id.symbol) +
                               " " + str(data.budget)), sub_title_amount)
            sheet.write_merge(4, 4, 3, 4, "Used Budget Amount", sub_title2)
            sheet.write_merge(4, 4, 5, 6, (str(self.budget_id.currency_id.symbol) +
                                           " " + str((data.budget - data.remaining_budget))),
                              sub_title_amount)
            sheet.write_merge(6, 6, 3, 4, "Remaining Budget", sub_title2)
            sheet.write_merge(6, 6, 5, 6, (str(self.budget_id.currency_id.symbol) +
                                           " " + str(data.remaining_budget)), sub_title_amount)
            row = 5
            # Material Rec
            sheet.write_merge(row + 4, row + 5, 0, 4, "Material Spent", title2)
            sheet.write_merge(row + 4, row + 5, 5, 6, (str(self.budget_id.currency_id.symbol) +
                                                       " " + str(data.material_spent)), title3)
            sheet.col(0).width = 8000
            sheet.col(1).width = 8000
            sheet.col(2).width = 6500
            sheet.col(3).width = 5000
            sheet.col(4).width = 5000
            sheet.col(5).width = 5000
            sheet.col(6).width = 5000
            sheet.row(row + 6).height = 600
            sheet.write(row + 6, 0, "Project Phase(WBS)", sub_title)
            sheet.write(row + 6, 1, "Work Order", sub_title)
            sheet.write(row + 6, 2, "Material", sub_title)
            sheet.write(row + 6, 3, "Qty.", line_amount_sub_title)
            sheet.write(row + 6, 4, "Unit", sub_title)
            sheet.write(row + 6, 5, "Price/Qty", line_amount_sub_title)
            sheet.write(row + 6, 6, "Total Price", line_amount_sub_title)
            row = row + 7
            for rec in material_spent_rec:
                sheet.row(row).height = 400
                sheet.write(row, 0, (rec.job_sheet_id.name +
                                     " - " + rec.job_order_id.name), line_values)
                sheet.write(row, 1, (rec.job_order_id.name +
                                     " - " + rec.job_order_id.name), line_values)
                sheet.write(row, 2, rec.name, line_values)
                sheet.write(row, 3, rec.qty, line_amount_sub_title)
                sheet.write(row, 4, rec.uom_id.name, line_values)
                sheet.write(row, 5, (str(self.budget_id.currency_id.symbol) +
                                     " " + str(rec.price)), line_amount_sub_title)
                sheet.write(row, 6, (str(self.budget_id.currency_id.symbol) +
                                     " " + str(rec.total_price)), line_amount_sub_title)
                row = row + 1
            sheet.write_merge(row, row, 0, 6, " ", horiz_double_line)
            row = row + 1

            # Equipment Rec
            sheet.write_merge(row + 1, row + 2, 0, 4,
                              "Equipment Spent", title2)
            sheet.write_merge(row + 1, row + 2, 5, 6, (str(self.budget_id.currency_id.symbol) +
                                                       " " + str(data.equipment_spent)), title3)
            row = row + 3
            sheet.row(row).height = 600
            sheet.write(row, 0, "Project Phase(WBS)", sub_title)
            sheet.write(row, 1, "Work Order", sub_title)
            sheet.write(row, 2, "Vendor", sub_title)
            sheet.write(row, 3, "Equipment.", sub_title)
            sheet.write(row, 4, "Qty.", line_amount_sub_title)
            sheet.write(row, 5, "Price/Qty", line_amount_sub_title)
            sheet.write(row, 6, "Total Price", line_amount_sub_title)
            row = row + 1
            for rec in equip_spent_rec:
                sheet.row(row).height = 400
                sheet.write(row, 0, (rec.job_sheet_id.name +
                                     " - " + rec.job_order_id.name), line_values)
                sheet.write(row, 1, (rec.job_order_id.name +
                                     " - " + rec.job_order_id.name), line_values)
                sheet.write(row, 2, rec.vendor_id.name, line_values)
                sheet.write(row, 3, rec.desc, line_values)
                sheet.write(row, 4, rec.qty, line_amount_sub_title)
                sheet.write(row, 5, (str(self.budget_id.currency_id.symbol) +
                                     " " + str(rec.cost)), line_amount_sub_title)
                sheet.write(row, 6, (str(self.budget_id.currency_id.symbol) +
                                     " " + str(rec.total_cost)), line_amount_sub_title)
                row = row + 1
            sheet.write_merge(row, row, 0, 6, " ", horiz_double_line)
            row = row + 1

            # Labour Rec
            sheet.write_merge(row + 1, row + 2, 0, 4, "Labour Spent", title2)
            sheet.write_merge(row + 1, row + 2, 5, 6, (str(self.budget_id.currency_id.symbol) +
                                                       " " + str(data.labour_spent)), title3)
            row = row + 3
            sheet.row(row).height = 600
            sheet.write(row, 0, "Project Phase(WBS)", sub_title)
            sheet.write(row, 1, "Work Order", sub_title)
            sheet.write(row, 2, "Vendor", sub_title)
            sheet.write(row, 3, "Product", sub_title)
            sheet.write(row, 4, "Hours", line_amount_sub_title)
            sheet.write(row, 5, "Cost / Hour", line_amount_sub_title)
            sheet.write(row, 6, "Sub Total", line_amount_sub_title)
            row = row + 1
            for rec in labour_spent_rec:
                sheet.row(row).height = 400
                sheet.write(row, 0, (rec.job_sheet_id.name +
                                     " - " + rec.job_order_id.name), line_values)
                sheet.write(row, 1, (rec.job_order_id.name +
                                     " - " + rec.job_order_id.name), line_values)
                sheet.write(row, 2, rec.vendor_id.name, line_values)
                sheet.write(row, 3, rec.name, line_values)
                sheet.write(row, 4, rec.hours, line_amount_sub_title)
                sheet.write(row, 5, (str(self.budget_id.currency_id.symbol) +
                                     " " + str(rec.cost)), line_amount_sub_title)
                sheet.write(row, 6, (str(self.budget_id.currency_id.symbol) +
                                     " " + str(rec.sub_total)), line_amount_sub_title)
                row = row + 1
            sheet.write_merge(row, row, 0, 6, " ", horiz_double_line)
            row = row + 1

            # Overhead Rec
            sheet.write_merge(row + 1, row + 2, 0, 4, "Overhead Spent", title2)
            sheet.write_merge(row + 1, row + 2, 5, 6, (str(self.budget_id.currency_id.symbol) +
                                                       " " + str(data.overhead_spent)), title3)
            row = row + 3
            sheet.row(row).height = 600
            sheet.write(row, 0, "Project Phase(WBS)", sub_title)
            sheet.write(row, 1, "Work Order", sub_title)
            sheet.write(row, 2, "Vendor", sub_title)
            sheet.write(row, 3, "Product", sub_title)
            sheet.write(row, 4, "Qty.", line_amount_sub_title)
            sheet.write(row, 5, "Cost / Qty", line_amount_sub_title)
            sheet.write(row, 6, "Sub Total", line_amount_sub_title)
            row = row + 1
            for rec in overhead_spent_rec:
                sheet.row(row).height = 400
                sheet.write(row, 0, (rec.job_sheet_id.name +
                                     " - " + rec.job_order_id.name), line_values)
                sheet.write(row, 1, (rec.job_order_id.name +
                                     " - " + rec.job_order_id.name), line_values)
                sheet.write(row, 2, rec.vendor_id.name, line_values)
                sheet.write(row, 3, rec.name, line_values)
                sheet.write(row, 4, rec.qty, line_amount_sub_title)
                sheet.write(row, 5, (str(self.budget_id.currency_id.symbol) +
                                     " " + str(rec.cost)), line_amount_sub_title)
                sheet.write(row, 6, (str(self.budget_id.currency_id.symbol) +
                                     " " + str(rec.sub_total)), line_amount_sub_title)
                row = row + 1
            sheet.write_merge(row, row, 0, 6, " ", horiz_double_line)
            row = row + 1


class ProjectDocuments(models.Model):
    """Project Documents"""
    _name = 'project.documents'
    _description = "Project Documents"
    _rec_name = 'file_name'

    document_type_id = fields.Many2one('site.document.type', string="Document")
    document = fields.Binary(string='Documents', required=True)
    file_name = fields.Char()
    project_id = fields.Many2one('tk.construction.project')


class ProjectInsurance(models.Model):
    """Project Insurance"""
    _name = 'project.insurance'
    _description = "Project Insurance"

    name = fields.Char(string="Insurance")
    policy_no = fields.Char(string="Insurance No")
    risk_ids = fields.Many2many('insurance.risk', string="Risk Covered")
    document = fields.Binary(string='Documents')
    file_name = fields.Char()
    project_id = fields.Many2one('tk.construction.project')
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id')
    total_charge = fields.Monetary()
    issue_date = fields.Date(default=fields.Date.today())
    bill_id = fields.Many2one('account.move')
    payment_state = fields.Selection(related="bill_id.payment_state", store=True)
    bill_state = fields.Selection(related="bill_id.state", store=True)
    vendor_id = fields.Many2one('res.partner')

    def action_create_bil(self):
        """Create Bills"""
        record = {
            'product_id': self.env.ref('tk_construction_management.construction_product_1').id,
            'name': (self.project_id.name
                     + "\n" + "Name : "
                     + self.name
                     + "\n"
                     + "No : " + self.policy_no),
            'quantity': 1,
            'tax_ids': False,
            'price_unit': self.total_charge
        }
        line = [(0, 0, record)]
        main_data = {
            'partner_id': self.vendor_id.id,
            'move_type': 'in_invoice',
            'invoice_date': fields.Date.today(),
            'invoice_line_ids': line,
        }
        bill_id = self.env['account.move'].create(main_data)
        self.bill_id = bill_id.id


class ConstructionExtraExpense(models.Model):
    """Construction Extra expense"""
    _name = 'extra.expense'
    _description = "Extra Expense"

    product_id = fields.Many2one(
        'product.product', string="Expense", domain="[('is_expense','=',True)]")
    date = fields.Date(default=fields.Date.today())
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id')
    cost = fields.Monetary()
    bill_id = fields.Many2one('account.move')
    payment_state = fields.Selection(related="bill_id.payment_state", store=True)
    bill_state = fields.Selection(related="bill_id.state", store=True)
    note = fields.Char()
    project_id = fields.Many2one('tk.construction.project')
    qty = fields.Integer(string="Qty.", default=1)
    vendor_id = fields.Many2one('res.partner')

    def action_create_expense_bill(self):
        """Extra expense bills"""
        if self.vendor_id and self.product_id:
            data = {
                'product_id': self.product_id.id,
                'name': self.product_id.name,
                'quantity': self.qty,
                'tax_ids': False,
                'price_unit': self.cost
            }
            invoice_line = [(0, 0, data)]
            invoice_id = self.env['account.move'].create({
                'partner_id': self.vendor_id.id,
                'invoice_line_ids': invoice_line,
                'move_type': 'in_invoice',
            })
            self.bill_id = invoice_id.id

    @api.onchange('product_id')
    def _onchange_expense_cost(self):
        """Expense cost"""
        for rec in self:
            rec.cost = rec.product_id.standard_price


class BoqBudget(models.Model):
    """Boq Budget"""
    _name = 'boq.budget'
    _description = "Boq Budget"
    _rec_name = 'display_name'

    project_id = fields.Many2one(
        'tk.construction.project', string="Sub Project")
    site_id = fields.Many2one(
        related="project_id.construction_site_id", string="Project")
    activity_id = fields.Many2one('job.type', string="Work Type")
    sub_activity_ids = fields.Many2many(
        related="activity_id.sub_category_ids", string="Sub Activities")
    sub_activity_id = fields.Many2one('job.sub.category', string="Work Sub Type",
                                      domain="[('id','in',sub_activity_ids)]")
    qty = fields.Float(string="Qty.", default=1.0)
    total_qty = fields.Float(
        string="Total Qty.", compute="_compute_total_qty", store=True)
    length = fields.Float()
    width = fields.Float()
    height = fields.Float()
    is_use_measure = fields.Boolean(
        related="project_id.is_use_measure", store=True)
    budget_line_id = fields.Many2one('project.budget')

    @api.depends('project_id.is_use_measure', 'length', 'width', 'height', 'qty')
    def _compute_total_qty(self):
        """Compute total qty"""
        for rec in self:
            if rec.project_id.is_use_measure:
                total_qty = rec.height * rec.width * rec.length * rec.qty
            else:
                total_qty = rec.qty
            rec.total_qty = total_qty

    @api.constrains('length', 'width', 'height', 'qty')
    def _check_dimension(self):
        """Check Budget Dimension"""
        for record in self:
            if record.qty <= 0:
                raise ValidationError(_("Qty cannot be less than zero !"))
            if record.is_use_measure:
                if record.length <= 0:
                    raise ValidationError(_("Length cannot be less than zero !"))
                if record.width <= 0:
                    raise ValidationError(_("Width cannot be less than zero !"))
                if record.height <= 0:
                    raise ValidationError(_("Height cannot be less than zero !"))

    @api.depends('activity_id.name', 'sub_activity_id')
    def _compute_display_name(self):
        """Compute display name"""
        for rec in self:
            display_name = rec.display_name
            if rec.activity_id and rec.sub_activity_id:
                display_name = rec.activity_id.name + " : " + rec.sub_activity_id.name
            rec.display_name = display_name

    @api.onchange('activity_id')
    def _onchange_activity_id(self):
        """Empty Sub Type on work Types"""
        for rec in self:
            if rec.activity_id:
                rec.sub_activity_id = False
