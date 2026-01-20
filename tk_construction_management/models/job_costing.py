# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
from odoo import fields, api, models, _
from odoo.exceptions import ValidationError


class JobCosting(models.Model):
    """Job costing / Project Phase"""
    _name = 'job.costing'
    _description = "Job Costing"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    active = fields.Boolean(default=True)
    name = fields.Char(string='Sequence', required=True,
                       readonly=True, default=lambda self: _('New'))
    title = fields.Char()
    start_date = fields.Date()
    close_date = fields.Date(string="End Date")
    status = fields.Selection([('draft', 'Draft'),
                               ('waiting_approval', 'Waiting Approval'),
                               ('approved', 'Approved'),
                               ('in_progress', 'In Progress'),
                               ('complete', 'Completed'),
                               ('cancel', 'Cancelled'),
                               ('reject', 'Rejected')], default='draft', tracking=True)

    responsible_id = fields.Many2one('res.users',
                                     default=lambda
                                     self: self.env.user and self.env.user.id or False,
                                     string="Created By")
    company_id = fields.Many2one(
        'res.company', string="Company", default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', string='Currency')
    site_id = fields.Many2one('tk.construction.site', string="Project")
    project_id = fields.Many2one(
        'tk.construction.project', string="Sub Project")
    activity_id = fields.Many2one('job.type', string="Work Type")

    # One2 many
    work_order_ids = fields.One2many('job.order', 'job_sheet_id')
    cost_material_ids = fields.One2many('cost.material.line', 'job_costing_id')
    cost_equipment_ids = fields.One2many(
        'cost.equipment.line', 'job_costing_id')
    cost_labour_ids = fields.One2many('cost.labour.line', 'job_costing_id')
    cost_overhead_ids = fields.One2many('cost.overhead.line', 'job_costing_id')

    # Total
    material_total_cost = fields.Monetary(
        string="Total Material Cost", compute="_compute_total")
    equipment_total_cost = fields.Monetary(
        string="Total Equipment Cost", compute="_compute_total")
    labour_total_cost = fields.Monetary(
        string="Total Labour Cost", compute="_compute_total")
    overhead_total_cost = fields.Monetary(
        string="Total Overhead Cost", compute="_compute_total")
    material_actual_cost = fields.Monetary(
        string="Actual Material Cost", compute="_compute_total")
    equipment_actual_cost = fields.Monetary(
        string="Actual Equipment Cost", compute="_compute_total")
    labour_actual_cost = fields.Monetary(
        string="Actual Labour Cost", compute="_compute_total")
    overhead_actual_cost = fields.Monetary(
        string="Actual Overhead Cost", compute="_compute_total")

    # Count
    job_order_count = fields.Integer(
        string="Jon Order", compute="_compute_count")
    mrq_count = fields.Integer(string="MRQ Order", compute="_compute_count")

    # Budget Qty.
    sub_work_type_ids = fields.Many2many('job.sub.category')

    # Create, Write, Unlink, Constrain

    @api.model_create_multi
    def create(self, vals_list):
        """Create"""
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New') and vals.get('project_id'):
                project_id = self.env['tk.construction.project'].browse(
                    vals.get('project_id'))
                vals['name'] = str(project_id.code) + "/" + (
                    self.env['ir.sequence'].next_by_code('job.costing') or _('New'))
        res = super().create(vals_list)
        return res

    @api.ondelete(at_uninstall=False)
    def _unlink_job_costing(self):
        for rec in self:
            if rec.work_order_ids:
                raise ValidationError(
                    _("This phase has associated work orders. Please delete the work orders to "
                      "proceed with deleting this phase."))
            if rec.status == 'complete':
                raise ValidationError(
                    _("You cannot delete completed project phase."))

    # Onchange

    @api.onchange('project_id')
    def _onchange_project_info(self):
        """Onchange product info"""
        for rec in self:
            rec.project_id = rec.project_id.id

    # Compute
    @api.depends('cost_material_ids', 'cost_equipment_ids', 'cost_labour_ids', 'cost_overhead_ids')
    def _compute_total(self):
        """Compute total"""
        material, equipment, labour, overhead = 0.0, 0.0, 0.0, 0.0
        material_actual_cost = self.env['order.material.line'].search(
            [('job_sheet_id', '=', self.id), ('state', '=', 'complete')]).mapped(
            'total_price')
        equipment_actual_cost = self.env['order.equipment.line'].search(
            [('job_sheet_id', '=', self.id), ('state', '=', 'complete')]).mapped(
            'total_cost')
        labour_actual_cost = self.env['order.labour.line'].search(
            [('job_sheet_id', '=', self.id), ('state', '=', 'complete')]).mapped(
            'sub_total')
        overhead_actual_cost = self.env['order.overhead.line'].search(
            [('job_sheet_id', '=', self.id), ('state', '=', 'complete')]).mapped(
            'sub_total')
        for rec in self:
            for data in rec.cost_material_ids:
                material = material + data.total_cost
            for data in rec.cost_equipment_ids:
                equipment = equipment + data.total_cost
            for data in rec.cost_labour_ids:
                labour = labour + data.sub_total
            for data in rec.cost_overhead_ids:
                overhead = overhead + data.sub_total
            rec.material_total_cost = material
            rec.equipment_total_cost = equipment
            rec.labour_total_cost = labour
            rec.overhead_total_cost = overhead
            rec.material_actual_cost = sum(material_actual_cost)
            rec.equipment_actual_cost = sum(equipment_actual_cost)
            rec.labour_actual_cost = sum(labour_actual_cost)
            rec.overhead_actual_cost = sum(overhead_actual_cost)

    def _compute_count(self):
        """Compute count"""
        for rec in self:
            rec.job_order_count = self.env['job.order'].search_count(
                [('job_sheet_id', '=', rec.id)])
            rec.mrq_count = self.env['material.requisition'].search_count(
                [('job_sheet_id', '=', rec.id)])

    # Smart Button
    def action_view_job_order(self):
        """View job order"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Work Order'),
            'res_model': 'job.order',
            'domain': [('job_sheet_id', '=', self.id)],
            'context': {'create': False},
            'view_mode': 'list,form',
            'target': 'current'
        }

    def action_view_mrq(self):
        """View Mreq"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Material Requisition'),
            'res_model': 'material.requisition',
            'domain': [('job_sheet_id', '=', self.id)],
            'context': {'default_job_sheet_id': self.id},
            'view_mode': 'list,form',
            'target': 'current'
        }

    def action_department_approval(self):
        """Department approval"""
        if all(not ids for ids in [self.cost_material_ids,
                                   self.cost_equipment_ids,
                                   self.cost_labour_ids,
                                   self.cost_overhead_ids]):
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'info',
                    'message': _("Please add at least one item from one of these:"
                                 "material, equipment, labour, or overhead."),
                    'sticky': False,
                }
            }
        self.status = 'waiting_approval'
        return True

    def action_approve_phase(self):
        """Status : Approved"""
        self.status = 'approved'

    def action_reject_phase(self):
        """Status : Rejected"""
        self.status = 'reject'

    def action_in_progress(self):
        """Status : In Progress"""
        self.status = 'in_progress'

    def action_reset_to_draft(self):
        """Status : Reset to Draft"""
        self.status = 'draft'

    def action_cancel_phase(self):
        """Status : Cancelled"""
        self.status = 'cancel'

    def action_complete_phase(self):
        """Complete Phase"""
        is_complete_work_order = True
        for data in self.work_order_ids:
            if data.state != 'complete':
                is_complete_work_order = False
                break
        if not is_complete_work_order:
            message = {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'info',
                    'message': "Please complete all work orders related to this phase.",
                    'sticky': False,
                }
            }
            return message
        if is_complete_work_order:
            self.status = 'complete'
            return True
        return True

    def action_create_work_order(self):
        """Create Work Order"""
        material_line = []
        equipment_line = []
        labour_line = []
        overhead_line = []
        ctx = {
            'default_site_id': self.site_id.id,
            'default_project_id': self.project_id.id,
            'default_start_date': self.start_date,
            'default_end_date': self.close_date,
            'default_work_type_id': self.activity_id.id,
            'default_job_sheet_id': self.id,
        }
        for data in self.cost_material_ids:
            material_line.append((0, 0, {
                'sub_category_id': data.sub_category_id.id,
                'material_id': data.material_id.id,
                'name': data.name,
                'qty': data.forcast_qty,
                'remain_qty': data.forcast_qty,
                'phase_forcast_qty': data.forcast_qty,
                'tax_id': data.tax_id.id,
                'price': data.cost
            }))
        for data in self.cost_equipment_ids:
            equipment_line.append((0, 0, {
                'sub_category_id': data.sub_category_id.id,
                'equipment_id': data.equipment_id.id,
                'cost_type': data.cost_type,
                'desc': data.name,
                'qty': data.forcast_qty,
                'cost': data.cost,
                'phase_forcast_qty': data.forcast_qty,
                'tax_id': data.tax_id.id,
            }))
        for data in self.cost_labour_ids:
            labour_line.append((0, 0, {
                'sub_category_id': data.sub_category_id.id,
                'product_id': data.product_id.id,
                'name': data.name,
                'hours': data.forcast_qty,
                'cost': data.cost,
                'phase_forcast_qty': data.forcast_qty,
                'tax_id': data.tax_id.id,
            }))
        for data in self.cost_overhead_ids:
            overhead_line.append((0, 0, {
                'sub_category_id': data.sub_category_id.id,
                'product_id': data.product_id.id,
                'name': data.name,
                'qty': data.forcast_qty,
                'cost': data.cost,
                'phase_forcast_qty': data.forcast_qty,
                'tax_id': data.tax_id.id,
            }))
        ctx['default_material_order_ids'] = material_line
        ctx['default_equipment_order_ids'] = equipment_line
        ctx['default_labour_order_ids'] = labour_line
        ctx['default_overhead_order_ids'] = overhead_line
        return {
            'type': 'ir.actions.act_window',
            'name': _('Work Order'),
            'res_model': 'job.order',
            'context': ctx,
            'view_mode': 'form',
            'target': 'new'
        }

    @api.model
    def process_phase_start_date(self):
        """Process Phase Start Date"""
        phases = self.env['job.costing'].search([('start_date', '=', False)])
        for phase in phases:
            phase.start_date = phase.create_date.date()


class CostMaterialLine(models.Model):
    """Cost Material Line"""
    _name = 'cost.material.line'
    _description = 'Construction Job Cost Material Line'

    material_id = fields.Many2one(
        'product.product', domain="[('is_material','=',True)]")
    name = fields.Char(string="Description")
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id')
    qty = fields.Integer(default=1)
    cost = fields.Float()
    total_cost = fields.Monetary(compute="_compute_total_cost", store=True)
    uom_id = fields.Many2one(
        related="material_id.uom_po_id", string="Unit of Measure")
    job_costing_id = fields.Many2one('job.costing')
    sub_category_id = fields.Many2one(
        'job.sub.category', string="Work Sub Type")
    tax_id = fields.Many2one('account.tax', string="Taxes")
    budget_qty = fields.Float(string="Budget Qty.",
                              compute="_compute_budget_qty", store=True)
    boq_per_qty = fields.Float(string="Per BOQ RA. Qty.")
    total_remain_boq_qty = fields.Float()
    forcast_qty = fields.Float(
        string="Forecast Qty.", compute="_compute_forecast_qty")
    used_qty = fields.Float(string="Used Qty.")
    used_budget_qty = fields.Float(string="Used Budget Qty.")
    remain_qty = fields.Float(string="Remain Qty.",
                              compute="_compute_remain_qty")

    @api.onchange('material_id')
    def _onchange_product_desc(self):
        """Onchange Product Info"""
        for rec in self:
            rec.name = rec.material_id.name
            rec.cost = rec.material_id.standard_price

    @api.depends('material_id', 'qty', 'cost', 'tax_id')
    def _compute_total_cost(self):
        """Compute Total Cost"""
        for rec in self:
            total_cost = 0.0
            tax_amount = 0.0
            if rec.material_id:
                total_cost = rec.qty * rec.cost
            if rec.tax_id:
                tax_amount = rec.tax_id.amount * (rec.qty * rec.cost) / 100
                total_cost = tax_amount + total_cost
            rec.total_cost = total_cost

    @api.depends('boq_per_qty', 'qty', 'sub_category_id', 'job_costing_id',
                 'job_costing_id.activity_id', 'job_costing_id.project_id.budget_id')
    def _compute_budget_qty(self):
        """Compute Budget Qty"""
        for rec in self:
            budget_qty = 0
            boq_line_id = self.env['project.budget'].search([
                ('sub_category_id', '=', rec.sub_category_id.id),
                ('job_type_id', '=', rec.job_costing_id.activity_id.id),
                ('sub_project_budget_id', '=', rec.job_costing_id.project_id.budget_id.id),
            ])
            if rec.boq_per_qty > 0:
                if len(boq_line_id) == 1:
                    if boq_line_id.rate_analysis_id.ra_type == 'total_required_qty':
                        budget_qty = boq_line_id.total_qty * rec.qty / rec.boq_per_qty
                    else:
                        budget_qty = rec.qty / rec.boq_per_qty
                else:
                    budget_qty = rec.qty / rec.boq_per_qty
            rec.budget_qty = budget_qty

    @api.depends('qty',
                 'job_costing_id.activity_id',
                 'material_id',
                 'sub_category_id',
                 'job_costing_id.work_order_ids.material_order_ids.qty')
    def _compute_forecast_qty(self):
        """Compute forecast qty"""
        for rec in self:
            forcast_qty = 0.0
            for record in rec.job_costing_id.work_order_ids:
                for data in record.material_order_ids:
                    if (data.material_id.id == rec.material_id.id
                            and data.sub_category_id.id == rec.sub_category_id.id):
                        forcast_qty = forcast_qty + data.qty
            rec.forcast_qty = rec.qty - forcast_qty

    @api.depends('job_costing_id.work_order_ids.material_order_ids.qty',
                 'job_costing_id.work_order_ids.state', 'qty')
    def _compute_remain_qty(self):
        """compute remain qty"""
        for rec in self:
            remain_qty = 0.0
            for record in rec.job_costing_id.work_order_ids:
                if record.state == 'complete':
                    for data in record.material_order_ids:
                        if (data.material_id.id == rec.material_id.id
                                and data.sub_category_id.id == rec.sub_category_id.id):
                            remain_qty = remain_qty + data.qty
            rec.remain_qty = rec.qty - remain_qty


class CostEquipmentLine(models.Model):
    """Cost Equipment Line"""
    _name = 'cost.equipment.line'
    _description = 'Construction Job Cost Equipment Line'

    equipment_id = fields.Many2one(
        'product.product', domain="[('is_equipment','=',True)]")
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id')
    cost_type = fields.Selection(
        [('depreciation_cost', 'Depreciation Cost'),
         ('investment_cost', 'Investment/Interest Cost'),
         ('tax', 'Tax'), ('rent', 'Rent'), ('other', 'Other')], string="Type", default='rent')
    name = fields.Char(string='Description')
    qty = fields.Integer(string="Qty.", default=1)
    cost = fields.Monetary(string="Estimation Cost")
    total_cost = fields.Monetary(compute="_compute_total_cost", store=True)
    job_costing_id = fields.Many2one('job.costing')
    sub_category_id = fields.Many2one(
        'job.sub.category', string="Work Sub Type")
    tax_id = fields.Many2one('account.tax', string="Taxes")
    budget_qty = fields.Float(string="Budget Qty.",
                              compute="_compute_budget_qty", store=True)
    boq_per_qty = fields.Float(string="Per BOQ RA. Qty.")
    total_remain_boq_qty = fields.Float()
    forcast_qty = fields.Float(
        string="Forecast Qty.", compute="_compute_forcast_qty")
    used_qty = fields.Float(string="Used Qty.")
    used_budget_qty = fields.Float(string="Used Budget Qty.")
    remain_qty = fields.Float(string="Remain Qty.",
                              compute="_compute_remain_qty")

    @api.depends('equipment_id', 'qty', 'cost', 'tax_id')
    def _compute_total_cost(self):
        """Compute total cost"""
        for rec in self:
            total_cost = 0.0
            if rec.equipment_id:
                total_cost = rec.qty * rec.cost
            if rec.tax_id:
                tax_amount = rec.tax_id.amount * (rec.qty * rec.cost) / 100
                total_cost = tax_amount + total_cost
            rec.total_cost = total_cost

    @api.onchange('equipment_id')
    def _onchange_product_desc(self):
        """onchange product description"""
        for rec in self:
            rec.name = rec.equipment_id.name
            rec.cost = rec.equipment_id.standard_price

    @api.depends('boq_per_qty', 'qty', 'sub_category_id', 'job_costing_id',
                 'job_costing_id.activity_id', 'job_costing_id.project_id.budget_id')
    def _compute_budget_qty(self):
        """Compute Budget Qty"""
        for rec in self:
            budget_qty = 0
            boq_line_id = self.env['project.budget'].search([
                ('sub_category_id', '=', rec.sub_category_id.id),
                ('job_type_id', '=', rec.job_costing_id.activity_id.id),
                ('sub_project_budget_id', '=', rec.job_costing_id.project_id.budget_id.id),
            ])
            if rec.boq_per_qty > 0:
                if len(boq_line_id) == 1:
                    if boq_line_id.rate_analysis_id.ra_type == 'total_required_qty':
                        budget_qty = boq_line_id.total_qty * rec.qty / rec.boq_per_qty
                    else:
                        budget_qty = rec.qty / rec.boq_per_qty
                else:
                    budget_qty = rec.qty / rec.boq_per_qty
            rec.budget_qty = budget_qty

    @api.depends('qty',
                 'job_costing_id.activity_id',
                 'equipment_id',
                 'sub_category_id',
                 'job_costing_id.work_order_ids.equipment_order_ids.qty')
    def _compute_forcast_qty(self):
        """Compute forcast qty"""
        for rec in self:
            forcast_qty = 0.0
            for record in rec.job_costing_id.work_order_ids:
                for data in record.equipment_order_ids:
                    if (data.equipment_id.id == rec.equipment_id.id
                            and data.sub_category_id.id == rec.sub_category_id.id):
                        forcast_qty = forcast_qty + data.qty
            rec.forcast_qty = rec.qty - forcast_qty

    @api.depends('job_costing_id.work_order_ids.equipment_order_ids.qty',
                 'job_costing_id.work_order_ids.state', 'qty')
    def _compute_remain_qty(self):
        """Compute remain qty"""
        for rec in self:
            remain_qty = 0.0
            for record in rec.job_costing_id.work_order_ids:
                if record.state == 'complete':
                    for data in record.equipment_order_ids:
                        if (data.equipment_id.id == rec.equipment_id.id
                                and data.sub_category_id.id == rec.sub_category_id.id):
                            remain_qty = remain_qty + data.qty
            rec.remain_qty = rec.qty - remain_qty


class CostLabourLine(models.Model):
    """Compute Labour Line"""
    _name = 'cost.labour.line'
    _description = "Cost Labour Line"

    job_costing_id = fields.Many2one('job.costing')
    product_id = fields.Many2one(
        'product.product', domain="[('is_labour','=',True)]")
    name = fields.Char(string="Description")
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id')
    hours = fields.Float()
    remain_hours = fields.Float(string="Remaining Hours")
    cost = fields.Monetary(string="Cost / Hour")
    sub_total = fields.Monetary(compute="_compute_total_cost", store=True)
    sub_category_id = fields.Many2one(
        'job.sub.category', string="Work Sub Type")
    tax_id = fields.Many2one('account.tax', string="Taxes")
    budget_qty = fields.Float(string="Budget Qty.",
                              compute="_compute_budget_qty", store=True)
    boq_per_qty = fields.Float(string="Per BOQ RA. Qty.")
    total_remain_boq_qty = fields.Float()
    forcast_qty = fields.Float(
        string="Forecast Hours", compute="_compute_forcast_qty")
    used_qty = fields.Float(string="Used Qty.")
    used_budget_qty = fields.Float(string="Used Budget Qty.")
    remain_qty = fields.Float(string="Remain Hours",
                              compute="_compute_remain_qty")

    @api.onchange('product_id')
    def _onchange_product_desc(self):
        """onchange product description"""
        for rec in self:
            rec.name = rec.product_id.name
            rec.cost = rec.product_id.standard_price

    @api.depends('product_id', 'hours', 'cost', 'tax_id')
    def _compute_total_cost(self):
        """compute total cost"""
        for rec in self:
            total_cost = 0.0
            if rec.product_id:
                total_cost = rec.hours * rec.cost
            if rec.tax_id:
                tax_amount = rec.tax_id.amount * (rec.hours * rec.cost) / 100
                total_cost = tax_amount + total_cost
            rec.sub_total = total_cost

    @api.depends('boq_per_qty', 'hours', 'sub_category_id', 'job_costing_id',
                 'job_costing_id.activity_id', 'job_costing_id.project_id.budget_id')
    def _compute_budget_qty(self):
        """Compute Budget Qty"""
        for rec in self:
            budget_qty = 0
            boq_line_id = self.env['project.budget'].search([
                ('sub_category_id', '=', rec.sub_category_id.id),
                ('job_type_id', '=', rec.job_costing_id.activity_id.id),
                ('sub_project_budget_id', '=', rec.job_costing_id.project_id.budget_id.id),
            ])
            if rec.boq_per_qty > 0:
                if len(boq_line_id) == 1:
                    if boq_line_id.rate_analysis_id.ra_type == 'total_required_qty':
                        budget_qty = boq_line_id.total_qty * rec.hours / rec.boq_per_qty
                    else:
                        budget_qty = rec.hours / rec.boq_per_qty
                else:
                    budget_qty = rec.hours / rec.boq_per_qty
            rec.budget_qty = budget_qty
    @api.depends('hours',
                 'job_costing_id.activity_id',
                 'product_id',
                 'sub_category_id',
                 'job_costing_id.work_order_ids.labour_order_ids.hours')
    def _compute_forcast_qty(self):
        """Compute forcast qty"""
        for rec in self:
            forcast_qty = 0.0
            for record in rec.job_costing_id.work_order_ids:
                for data in record.labour_order_ids:
                    if (data.product_id.id == rec.product_id.id
                            and data.sub_category_id.id == rec.sub_category_id.id):
                        forcast_qty = forcast_qty + data.hours
            rec.forcast_qty = rec.hours - forcast_qty

    @api.depends('job_costing_id.work_order_ids.labour_order_ids.hours',
                 'job_costing_id.work_order_ids.state', 'hours')
    def _compute_remain_qty(self):
        """compute remain qty"""
        for rec in self:
            remain_qty = 0.0
            for record in rec.job_costing_id.work_order_ids:
                if record.state == 'complete':
                    for data in record.labour_order_ids:
                        if (data.product_id.id == rec.product_id.id
                                and data.sub_category_id.id == rec.sub_category_id.id):
                            remain_qty = remain_qty + data.hours
            rec.remain_qty = rec.hours - remain_qty


class CostOverheadLine(models.Model):
    """Cost Overhead Line"""
    _name = 'cost.overhead.line'
    _description = "Cost Overhead Line"

    job_costing_id = fields.Many2one('job.costing')
    product_id = fields.Many2one(
        'product.product', domain="[('is_overhead','=',True)]")
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id')
    name = fields.Char(string="Description")
    qty = fields.Integer(string="Qty.", default=1)
    uom_id = fields.Many2one(related="product_id.uom_po_id", string="UOM")
    cost = fields.Monetary(string="Cost / Unit")
    sub_total = fields.Monetary(compute="_compute_total_cost", store=True)
    sub_category_id = fields.Many2one(
        'job.sub.category', string="Work Sub Type")
    tax_id = fields.Many2one('account.tax', string="Taxes")
    budget_qty = fields.Float(string="Budget Qty.",
                              compute="_compute_budget_qty", store=True)
    boq_per_qty = fields.Float(string="Per BOQ RA. Qty.")
    total_remain_boq_qty = fields.Float()
    forcast_qty = fields.Float(
        string="Forecast Qty.", compute="_compute_forcast_qty")
    used_qty = fields.Float(string="Used Qty.")
    used_budget_qty = fields.Float(string="Used Budget Qty.")
    remain_qty = fields.Float(string="Remain Qty.",
                              compute="_compute_remain_qty")

    @api.depends('product_id', 'qty', 'cost', 'tax_id')
    def _compute_total_cost(self):
        """Compute totla cost"""
        for rec in self:
            total_cost = 0.0
            if rec.product_id:
                total_cost = rec.qty * rec.cost
            if rec.tax_id:
                tax_amount = rec.tax_id.amount * (rec.qty * rec.cost) / 100
                total_cost = tax_amount + total_cost
            rec.sub_total = total_cost

    @api.onchange('product_id')
    def _onchange_product_desc(self):
        """onchange product description"""
        for rec in self:
            rec.name = rec.product_id.name
            rec.cost = rec.product_id.standard_price

    @api.depends('boq_per_qty', 'qty', 'sub_category_id', 'job_costing_id',
                 'job_costing_id.activity_id', 'job_costing_id.project_id.budget_id')
    def _compute_budget_qty(self):
        """Compute Budget Qty"""
        for rec in self:
            budget_qty = 0
            boq_line_id = self.env['project.budget'].search([
                ('sub_category_id', '=', rec.sub_category_id.id),
                ('job_type_id', '=', rec.job_costing_id.activity_id.id),
                ('sub_project_budget_id', '=', rec.job_costing_id.project_id.budget_id.id),
            ])
            if rec.boq_per_qty > 0:
                if len(boq_line_id) == 1:
                    if boq_line_id.rate_analysis_id.ra_type == 'total_required_qty':
                        budget_qty = boq_line_id.total_qty * rec.qty / rec.boq_per_qty
                    else:
                        budget_qty = rec.qty / rec.boq_per_qty
                else:
                    budget_qty = rec.qty / rec.boq_per_qty
            rec.budget_qty = budget_qty

    @api.depends('qty',
                 'job_costing_id.activity_id',
                 'product_id',
                 'sub_category_id',
                 'job_costing_id.work_order_ids.overhead_order_ids.qty')
    def _compute_forcast_qty(self):
        """compute forcast qty"""
        for rec in self:
            forcast_qty = 0.0
            for record in rec.job_costing_id.work_order_ids:
                for data in record.overhead_order_ids:
                    if (data.product_id.id == rec.product_id.id
                            and data.sub_category_id.id == rec.sub_category_id.id):
                        forcast_qty = forcast_qty + data.qty
            rec.forcast_qty = rec.qty - forcast_qty

    @api.depends('job_costing_id.work_order_ids.overhead_order_ids.qty',
                 'job_costing_id.work_order_ids.state', 'qty')
    def _compute_remain_qty(self):
        """Compute remain qty"""
        for rec in self:
            remain_qty = 0.0
            for record in rec.job_costing_id.work_order_ids:
                if record.state == 'complete':
                    for data in record.overhead_order_ids:
                        if (data.product_id.id == rec.product_id.id
                                and data.sub_category_id.id == rec.sub_category_id.id):
                            remain_qty = remain_qty + data.qty
            rec.remain_qty = rec.qty - remain_qty
