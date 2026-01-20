# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
from odoo import fields, api, models, _
from odoo.exceptions import ValidationError


class JobOrder(models.Model):
    """Job Order"""
    _name = 'job.order'
    _description = "Work Order"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    active = fields.Boolean(default=True)
    name = fields.Char(string='Sequence', required=True,
                       readonly=True, default=lambda self: _('New'))
    title = fields.Char()
    stage = fields.Selection([('draft', 'Draft'),
                              ('waiting_approval', 'Waiting for approval'),
                              ('approved', 'Approved'),
                              ('complete', 'Completed'),
                              ('cancel', 'Cancelled')], default='draft', tracking=True)
    is_user = fields.Boolean(compute="_compute_user_role")
    is_material_requisition = fields.Boolean(compute="compute_material_req")

    # Project Details
    site_id = fields.Many2one('tk.construction.site', string="Project")
    project_id = fields.Many2one(
        'tk.construction.project', string="Sub Project")
    company_id = fields.Many2one(
        'res.company', string="Company", default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', string='Currency')
    warehouse_id = fields.Many2one(
        related="project_id.warehouse_id", string="Warehouse")

    # Other Details
    responsible_id = fields.Many2one('res.users', string="Created By",
                                     default=lambda
                                         self: self.env.user and self.env.user.id or False)
    start_date = fields.Date()
    end_date = fields.Date()

    # Work Type
    work_type_id = fields.Many2one('job.type', string="Work Type")
    job_sheet_id = fields.Many2one('job.costing', string="Project Phase(WBS)",
                                   domain="[('project_id','=',project_id)]")

    # Material
    material_req_id = fields.Many2one('material.requisition')
    mreq_status = fields.Selection(related="material_req_id.stage", string="MREQ Status")
    state = fields.Selection([('draft', 'Draft'),
                              ('material_request', 'Material Requested'),
                              ('material_arrive', 'Material Arrived'),
                              ('in_progress', 'In Progress'),
                              ('complete', 'Completed'),
                              ('cancel', 'Cancelled')], default='draft')

    # Task Details
    project_project_id = fields.Many2one(
        related="project_id.project_id", string="Project ")
    task_name = fields.Char(string="Task Title")
    task_desc = fields.Text(string="Description")
    assignees_ids = fields.Many2many('res.users', 'construction_assign_dep_rel',
                                     'assign_id', 'dep_id', string="Assignees")
    task_id = fields.Many2one('project.task', string="Task")

    # One2 many
    material_order_ids = fields.One2many('order.material.line', 'job_order_id')
    equipment_order_ids = fields.One2many(
        'order.equipment.line', 'job_order_id')
    labour_order_ids = fields.One2many('order.labour.line', 'job_order_id')
    overhead_order_ids = fields.One2many('order.overhead.line', 'job_order_id')

    # Total
    equipment_total_cost = fields.Monetary(
        string="Equipment Cost", compute="_compute_total")
    labour_total_cost = fields.Monetary(
        string="Labour Cost", compute="_compute_total")
    overhead_total_cost = fields.Monetary(
        string="Overhead Cost", compute="_compute_total")

    # Consume Order and Subcontract
    consume_order_ids = fields.One2many('material.consume', 'job_order_id')
    equipment_contract_ids = fields.One2many(
        'equipment.subcontract', 'job_order_id')
    labour_contract_ids = fields.One2many('labour.subcontract', 'job_order_id')
    overhead_contract_ids = fields.One2many(
        'overhead.subcontract', 'job_order_id')

    # Count
    po_count = fields.Integer(compute="_compute_count")
    equip_po_count = fields.Integer(compute="_compute_count")
    labour_po_count = fields.Integer(compute="_compute_count")
    overhead_po_count = fields.Integer(compute="_compute_count")
    bill_count = fields.Integer(compute="_compute_count")
    delivery_count = fields.Integer(compute="_compute_count")
    equip_contract_count = fields.Integer(compute="_compute_count")
    labour_contract_count = fields.Integer(compute="_compute_count")
    overhead_contract_count = fields.Integer(compute="_compute_count")
    material_consume_count = fields.Integer(compute="_compute_count")
    timesheet_hours = fields.Float(
        related="task_id.effective_hours", string="Time sheet Hours")

    # Is Partial Arrived
    is_partial_arrived = fields.Boolean()

    # Create, Write, Unlink, Constrain
    @api.model_create_multi
    def create(self, vals_list):
        """Create"""
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New') and vals.get('project_id'):
                project_id = self.env['tk.construction.project'].browse(
                    vals.get('project_id'))
                vals['name'] = str(project_id.code) + "/" + (
                        self.env['ir.sequence'].next_by_code('job.order') or _('New'))
        res = super().create(vals_list)
        for rec in res:
            data = {
                'name': rec.task_name,
                'description': rec.task_desc,
                'user_ids': [(6, 0, rec.assignees_ids.ids)],
                'job_order_id': rec.id,
                'con_project_id': rec.project_id.id,
                'date_deadline': rec.end_date,
                'project_id': rec.project_id.project_id.id,
            }
            task_id = self.env['project.task'].sudo().create(data)
            task_id.project_id = rec.project_id.project_id.id
            rec.task_id = task_id.id
        return res

    @api.ondelete(at_uninstall=False)
    def _unlink_job_order(self):
        for rec in self:
            if rec.state == 'complete':
                raise ValidationError(
                    _('You can not delete completed work order.'))
            if rec.material_req_id:
                raise ValidationError(
                    _("Delete the material requisition to delete this work order."))
            if rec.consume_order_ids:
                raise ValidationError(
                    _("Delete all consume order related to this work order to delete this work "
                      "order."))
            if rec.equipment_contract_ids:
                raise ValidationError(
                    _("Delete all equipment sub-contract related to this work order to delete "
                      "this work order."))
            if rec.labour_contract_ids:
                raise ValidationError(
                    _("Delete all labour sub-contract related to this work order to delete this "
                      "work order."))
            if rec.overhead_contract_ids:
                raise ValidationError(
                    _('Delete all overhead sub-contract related to this work order to delete this '
                      'work order.'))

    # Compute
    def _compute_count(self):
        """Compute count"""
        for rec in self:
            rec.po_count = self.env['purchase.order'].search_count(
                [('job_order_id', '=', rec.id)])
            rec.equip_po_count = self.env['purchase.order'].search_count(
                [('job_order_id', '=', rec.id), ('purchase_order', '=', 'equipment')])
            rec.labour_po_count = self.env['purchase.order'].search_count(
                [('job_order_id', '=', rec.id), ('purchase_order', '=', 'labour')])
            rec.overhead_po_count = self.env['purchase.order'].search_count(
                [('job_order_id', '=', rec.id), ('purchase_order', '=', 'overhead')])
            rec.bill_count = self.env['account.move'].search_count(
                [('job_order_id', '=', rec.id)])
            rec.delivery_count = self.env['stock.picking'].search_count(
                [('consume_order_id', '=', rec.id)])
            rec.equip_contract_count = self.env['equipment.subcontract'].search_count(
                [('job_order_id', '=', rec.id)])
            rec.labour_contract_count = self.env['labour.subcontract'].search_count(
                [('job_order_id', '=', rec.id)])
            rec.overhead_contract_count = self.env['overhead.subcontract'].search_count(
                [('job_order_id', '=', rec.id)])
            rec.material_consume_count = self.env['material.consume'].search_count(
                [('job_order_id', '=', rec.id)])

    def _compute_user_role(self):
        """Compute User rule"""
        if self.env.user.has_group('tk_construction_management.advance_construction_user'):
            self.is_user = True
        else:
            self.is_user = False

    @api.depends('material_order_ids')
    def compute_material_req(self):
        """Compute material requisition"""
        for rec in self:
            material_req = False
            for data in rec.material_order_ids:
                if data.qty != 0:
                    material_req = True
                    break
            rec.is_material_requisition = material_req

    @api.depends('material_order_ids', 'equipment_order_ids', 'labour_order_ids',
                 'overhead_order_ids')
    def _compute_total(self):
        """Compute total"""
        equipment, labour, overhead = 0, 0, 0
        for rec in self:
            for data in rec.equipment_order_ids:
                equipment = equipment + data.total_cost
            for data in rec.labour_order_ids:
                labour = labour + data.sub_total
            for data in rec.overhead_order_ids:
                overhead = overhead + data.sub_total
            rec.equipment_total_cost = equipment
            rec.labour_total_cost = labour
            rec.overhead_total_cost = overhead

    # Smart Button
    def action_view_purchase_order(self):
        """View purchase order"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Order'),
            'res_model': 'purchase.order',
            'domain': [('job_order_id', '=', self.id)],
            'context': {
                'default_job_order_id': self.id,
                'group_by': 'purchase_order'
            },
            'view_mode': 'list,form,kanban',
            'target': 'current'
        }

    def action_view_bills(self):
        """View Bills"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bills'),
            'res_model': 'account.move',
            'domain': [('job_order_id', '=', self.id)],
            'context': {
                'default_job_order_id': self.id
            },
            'view_mode': 'list,form,kanban',
            'target': 'current'
        }

    def action_view_delivery_order(self):
        """View Delivery Orders"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Delivery Order'),
            'res_model': 'stock.picking',
            'domain': [('consume_order_id', '=', self.id)],
            'context': {
                'default_': self.id
            },
            'view_mode': 'list,form,kanban',
            'target': 'current'
        }

    def action_view_purchase_order_equipment(self):
        """View Purchase Order Equipment"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Equipment PO'),
            'res_model': 'purchase.order',
            'domain': [('job_order_id', '=', self.id), ('purchase_order', '=', 'equipment')],
            'context': {
                'default_job_order_id': self.id,
                'purchase_order': 'equipment'
            },
            'view_mode': 'list,form,kanban',
            'target': 'current'
        }

    def action_view_contract_equipment(self):
        """View Contract Equipment"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Equipment Contract'),
            'res_model': 'equipment.subcontract',
            'domain': [('job_order_id', '=', self.id)],
            'context': {
                'create': False,
            },
            'view_mode': 'list,form',
            'target': 'current'
        }

    def action_view_contract_labour(self):
        """View Contract Labour"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Labour Contract'),
            'res_model': 'labour.subcontract',
            'domain': [('job_order_id', '=', self.id)],
            'context': {
                'create': False,
            },
            'view_mode': 'list,form',
            'target': 'current'
        }

    def action_view_contract_overhead(self):
        """View Contract Overhead"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Overhead Contract'),
            'res_model': 'overhead.subcontract',
            'domain': [('job_order_id', '=', self.id)],
            'context': {
                'create': False,
            },
            'view_mode': 'list,form',
            'target': 'current'
        }

    def action_view_material_consume_order(self):
        """View Material Consume Order"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Consume Orders'),
            'res_model': 'material.consume',
            'domain': [('job_order_id', '=', self.id)],
            'context': {
                'create': False,
            },
            'view_mode': 'list,form',
            'target': 'current'
        }

    def action_view_timesheet(self):
        """View Timesheet"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Time Sheet'),
            'res_model': 'account.analytic.line',
            'domain': [('task_id', '=', self.task_id.id)],
            'context': {
                'default_task_id': self.task_id.id,
            },
            'view_mode': 'list',
            'target': 'current'
        }

    # Button
    def action_request_material(self):
        """Request Material"""
        if not self.material_order_ids:
            message = {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'info',
                    'title': _('Add Material'),
                    'message': "Add Material to Create Material Request",
                    'sticky': False,
                }
            }
            return message
        material_request_id = self.env['material.requisition'].create({
            'title': self.title,
            'company_id': self.company_id.id,
            'desc': self.task_desc,
            'project_id': self.project_id.id,
            'work_order_id': self.id,
            'work_type_id': self.work_type_id.id,
            'site_id': self.site_id.id
        })
        for data in self.material_order_ids:
            record = {
                'material_id': data.material_id.id,
                'name': data.name,
                'qty': data.qty,
                'warehouse_id': self.warehouse_id.id,
                'material_req_id': material_request_id.id,
                'sub_category_id': data.sub_category_id.id,
                'job_sheet_id': self.job_sheet_id.id,
            }
            req_line_id = self.env['material.requisition.line'].create(record)
            data.material_req_line_id = req_line_id.id
        self.material_req_id = material_request_id.id
        self.state = 'material_request'
        return {
            'type': 'ir.actions.act_window',
            'name': _('Material Request'),
            'res_model': 'material.requisition',
            'res_id': material_request_id.id,
            'view_mode': 'form',
            'target': 'current'
        }

    def action_create_equipment_subcontract(self):
        """Equipment SubContract"""
        for rec in self.equipment_order_ids:
            if not rec.equip_sub_contract_id:
                data = {
                    'name': rec.desc,
                    'equipment_id': rec.equipment_id.id,
                    'cost_type': rec.cost_type,
                    'qty': rec.qty,
                    'remain_qty': rec.qty,
                    'cost': rec.cost,
                    'total_cost': rec.total_cost,
                    'vendor_id': rec.vendor_id.id,
                    'job_type_id': self.work_type_id.id,
                    'sub_category_id': rec.sub_category_id.id,
                    'job_order_id': self.id,
                    'remaining_amount': rec.total_cost,
                    'tax_id': rec.tax_id.id
                }
                equip_line_id = self.env['equipment.subcontract'].create(data)
                rec.equip_sub_contract_id = equip_line_id.id

    def action_create_labour_subcontract(self):
        """Labour SubContract"""
        for rec in self.labour_order_ids:
            if not rec.labour_sub_contract_id and not rec.internal_entry:
                data = {
                    'name': rec.name,
                    'product_id': rec.product_id.id,
                    'hours': rec.hours,
                    'remain_hours': rec.hours,
                    'cost': rec.cost,
                    'total_cost': rec.sub_total,
                    'vendor_id': rec.vendor_id.id,
                    'job_type_id': self.work_type_id.id,
                    'sub_category_id': rec.sub_category_id.id,
                    'job_order_id': self.id,
                    'remaining_amount': rec.sub_total,
                    'tax_id': rec.tax_id.id
                }
                labour_line_id = self.env['labour.subcontract'].create(data)
                rec.labour_sub_contract_id = labour_line_id.id

    def action_create_overhead_subcontract(self):
        """Overhead SubContract"""
        for rec in self.overhead_order_ids:
            if not rec.overhead_sub_contract_id:
                data = {
                    'name': rec.name,
                    'product_id': rec.product_id.id,
                    'qty': rec.qty,
                    'remain_qty': rec.qty,
                    'cost': rec.cost,
                    'total_cost': rec.sub_total,
                    'vendor_id': rec.vendor_id.id,
                    'job_type_id': self.work_type_id.id,
                    'sub_category_id': rec.sub_category_id.id,
                    'job_order_id': self.id,
                    'remaining_amount': rec.sub_total,
                    'tax_id': rec.tax_id.id
                }
                overhead_line_id = self.env['overhead.subcontract'].create(
                    data)
                rec.overhead_sub_contract_id = overhead_line_id.id

    def action_create_material_consume_order(self):
        """View Material Consume Order"""
        remain_qty = False
        for rec in self.material_order_ids:
            if not rec.remain_qty == 0:
                remain_qty = True
                break
        if remain_qty:
            consume_order_id = self.env['material.consume'].create({
                'job_order_id': self.id,
                'warehouse_id': self.warehouse_id.id
            })
            for rec in self.material_order_ids:
                if rec.remain_qty > 0:
                    self.env['material.consume.line'].create({
                        'material_id': rec.material_id.id,
                        'name': rec.name,
                        'qty': rec.remain_qty,
                        'remain_qty': rec.remain_qty,
                        'material_consume_id': consume_order_id.id,
                        'material_line_id': rec.id
                    })
            return {
                'type': 'ir.actions.act_window',
                'name': _('Material Consume Order'),
                'res_model': 'material.consume',
                'res_id': consume_order_id.id,
                'view_mode': 'form',
                'target': 'new'
            }
        if not remain_qty:
            message = {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'info',
                    'message': _("There is not remain qty !"),
                    'sticky': False,
                }
            }
            return message

    def action_department_approval(self):
        """Status : Department Approval"""
        self.stage = 'waiting_approval'

    def action_department_approval_approved(self):
        """Status : Department Approval Approved"""
        self.stage = 'approved'

    def action_department_approval_reject(self):
        """Status : Department Approval Rejected"""
        self.stage = 'cancel'

    def action_draft_order(self):
        """Status : Draft Order"""
        self.stage = 'draft'

    def action_cancel_order(self):
        """Status : Cancel Order"""
        self.stage = 'cancel'

    def action_in_progress(self):
        """Status : In-Progress"""
        self.state = 'in_progress'

    def action_reset_draft(self):
        """Status : Reset Draft"""
        self.state = 'draft'

    def action_complete_work_order(self):
        """Complete Work Order"""
        # Check Material
        if self.material_order_ids and not self.consume_order_ids:
            raise ValidationError(_("Please create consume order to proceed !"))
        if self.consume_order_ids:
            material = all(o.qc_status == 'approve' for o in
                           self.consume_order_ids.filtered(lambda line: line.qc_status != 'cancel'))
            if not material:
                raise ValidationError(
                    _("Please complete all consume order to complete this work order !"))
        # Check Equipment
        if self.equipment_order_ids and not self.equipment_contract_ids:
            raise ValidationError(_("Please create equipment subcontract to proceed !"))
        if self.equipment_contract_ids:
            equipment = all(c.stage == 'done' for c in self.equipment_contract_ids)
            if not equipment:
                raise ValidationError(
                    _("Please complete all equipment subcontract to complete this work order !"))
        # Check Labour
        if self.labour_order_ids and not self.labour_contract_ids:
            raise ValidationError(_("Please create labour subcontract to proceed !"))
        if self.labour_contract_ids:
            labour = all(c.stage == 'done' for c in self.labour_contract_ids)
            if not labour:
                raise ValidationError(
                    _("Please complete all labour subcontract to complete this work order !"))
        # Check Overhead
        if self.overhead_order_ids and not self.overhead_contract_ids:
            raise ValidationError(_("Please create overhead subcontract to proceed !"))
        if self.overhead_contract_ids:
            labour = all(c.stage == 'done' for c in self.overhead_contract_ids)
            if not labour:
                raise ValidationError(
                    _("Please complete all overhead subcontract to complete this work order !"))
        self.state = 'complete'

    def action_view_partial_arrive_material(self):
        """View Partial Arrive Material"""
        desc = ""
        for data in self.material_req_id.material_purchase_ids:
            if data.status == 'complete':
                desc = desc + data.name + ","
        message = {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'info',
                'title': _('Partial Arrived Material'),
                'message': desc,
                'sticky': True,
            }
        }
        return message


class OrderMaterialLine(models.Model):
    """Order Material Line"""
    _name = 'order.material.line'
    _description = "Job order material line"

    material_id = fields.Many2one(
        'product.product', string="Material", domain="[('is_material','=',True)]")
    name = fields.Char(string="Description")
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id')
    qty = fields.Integer(string="Qty.", default=1)
    remain_qty = fields.Integer(string="Remain Qty.", default=1)
    usage_qty = fields.Integer(string="Used Qty.")
    uom_id = fields.Many2one(related="material_id.uom_po_id", string="UOM")
    job_order_id = fields.Many2one('job.order', string="Work Order")
    sub_category_id = fields.Many2one(
        'job.sub.category', string="Work Sub Type")
    price = fields.Monetary()
    total_price = fields.Monetary(compute="_compute_total_price")
    material_req_line_id = fields.Many2one('material.requisition.line')
    phase_forcast_qty = fields.Float()
    tax_id = fields.Many2one('account.tax', string="Taxes")

    # Budget Field
    job_sheet_id = fields.Many2one(
        related="job_order_id.job_sheet_id", store=True)
    project_id = fields.Many2one(related="job_order_id.project_id", store=True)
    work_type_id = fields.Many2one(
        related="job_order_id.work_type_id", store=True)
    state = fields.Selection(related="job_order_id.state", store=True)

    @api.onchange('material_id')
    def _onchange_product_desc(self):
        """Onchange Product Description"""
        for rec in self:
            rec.name = rec.material_id.name
            rec.price = rec.material_id.standard_price

    @api.depends('qty', 'price', 'tax_id')
    def _compute_total_price(self):
        """Compute Total Price"""
        for rec in self:
            total = 0.0
            if rec.qty and rec.price:
                total = rec.qty * rec.price
            if rec.tax_id:
                tax_amount = rec.tax_id.amount * total / 100
                total = tax_amount + total
            rec.total_price = total

    @api.onchange('qty')
    def _onchange_remain_qty(self):
        """Compute Remaining Qty"""
        for rec in self:
            rec.remain_qty = rec.qty

    @api.depends('warehouse_id', 'material_id')
    def _compute_forcast_qty(self):
        """Compute Forcast Qty"""
        for rec in self:
            qty = 0.0
            if rec.material_id:
                qty = rec.material_id.with_context(
                    warehouse=rec.warehouse_id.id).virtual_available
            rec.forcast_qty = qty


class OrderEquipmentLine(models.Model):
    """Order Equipment Line"""
    _name = 'order.equipment.line'
    _description = 'Construction Work Order Equipment Line'
    _rec_name = 'desc'

    equipment_id = fields.Many2one(
        'product.product', string="Equipment", domain="[('is_equipment','=',True)]")
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id')
    cost_type = fields.Selection([('depreciation_cost', 'Depreciation Cost'),
                                  ('investment_cost', 'Investment/Interest Cost'),
                                  ('tax', 'Tax'), ('rent', 'Rent'), ('other', 'Other')],
                                 string="Type", default='rent')
    desc = fields.Text(string='Description')
    qty = fields.Integer(string="Qty.", default=1)
    cost = fields.Monetary(string="Estimation Cost")
    total_cost = fields.Monetary(compute="_compute_total_cost", store=True)
    vendor_id = fields.Many2one('res.partner')
    job_order_id = fields.Many2one('job.order', string="Work Order")
    purchase_order_id = fields.Many2one('purchase.order')
    is_po_create = fields.Boolean()
    sub_category_id = fields.Many2one(
        'job.sub.category', string="Work Sub Type")

    equip_sub_contract_id = fields.Many2one(
        'equipment.subcontract', string="Equip Subcontract")
    equip_sub_contract_stage = fields.Selection(related="equip_sub_contract_id.stage", store=True)
    phase_forcast_qty = fields.Float()
    tax_id = fields.Many2one('account.tax', string="Taxes")

    # Budget Field
    job_sheet_id = fields.Many2one(
        related="job_order_id.job_sheet_id", store=True)
    project_id = fields.Many2one(related="job_order_id.project_id", store=True)
    work_type_id = fields.Many2one(
        related="job_order_id.work_type_id", store=True)
    state = fields.Selection(related="job_order_id.state", store=True)

    @api.depends('qty', 'cost', 'tax_id')
    def _compute_total_cost(self):
        """Compute total cost"""
        for rec in self:
            total = 0.0
            if rec.cost and rec.qty:
                total = rec.cost * rec.qty
            if rec.tax_id:
                tax_amount = rec.tax_id.amount * total / 100
                total = tax_amount + total
            rec.total_cost = total

    @api.onchange('equipment_id')
    def _onchange_product_desc(self):
        """onchange product description"""
        for rec in self:
            rec.desc = rec.equipment_id.name
            rec.cost = rec.equipment_id.standard_price


class OrderLabourLine(models.Model):
    """Order Labour Line"""
    _name = 'order.labour.line'
    _description = "Work Order Labour Line"

    job_order_id = fields.Many2one('job.order', string="Work Order")
    product_id = fields.Many2one(
        'product.product', domain="[('is_labour','=',True)]")
    name = fields.Char(string="Description")
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id')
    hours = fields.Float()
    remain_hours = fields.Float(
        related='labour_sub_contract_id.remain_hours')
    cost = fields.Monetary(string="Cost / Hour")
    sub_total = fields.Monetary(compute="_compute_sub_total", store=True)
    vendor_id = fields.Many2one('res.partner')
    is_bill_created = fields.Boolean()
    purchase_order_id = fields.Many2one(
        'purchase.order')
    sub_category_id = fields.Many2one(
        'job.sub.category', string="Work Sub Type")
    labour_sub_contract_id = fields.Many2one(
        'labour.subcontract', string="Subcontract")
    labour_sub_contract_stage = fields.Selection(related="labour_sub_contract_id.stage", store=True)
    phase_forcast_qty = fields.Float()
    tax_id = fields.Many2one('account.tax', string="Taxes")

    # Budget Field
    job_sheet_id = fields.Many2one(
        related="job_order_id.job_sheet_id", store=True)
    project_id = fields.Many2one(related="job_order_id.project_id", store=True)
    work_type_id = fields.Many2one(
        related="job_order_id.work_type_id", store=True)
    state = fields.Selection(related="job_order_id.state", store=True)

    # Internal Team
    bill_id = fields.Many2one('account.move')
    internal_entry = fields.Boolean()
    timesheet_entry_ids = fields.Many2many(
        "account.analytic.line", string="Timesheet Entries")

    @api.onchange('product_id')
    def _onchange_product_desc(self):
        """Onchange Product Description"""
        for rec in self:
            rec.name = rec.product_id.name
            rec.cost = rec.product_id.standard_price

    @api.depends('cost', 'hours', 'tax_id')
    def _compute_sub_total(self):
        """Compute sub total"""
        for rec in self:
            total = 0.0
            if rec.cost and rec.hours:
                total = rec.cost * rec.hours
            if rec.tax_id:
                tax_amount = rec.tax_id.amount * total / 100
                total = tax_amount + total
            rec.sub_total = total

    def action_view_timesheet(self):
        """View timesheet"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Timesheets'),
            'res_model': 'account.analytic.line',
            'domain': [('id', 'in', self.timesheet_entry_ids.ids)],
            'context': {
                'create': False,
                'edit': False
            },
            'view_mode': 'list',
            'target': 'current'
        }


class OrderOverheadLine(models.Model):
    """Order Overhead Line"""
    _name = 'order.overhead.line'
    _description = "Work Order Overhead Line"

    job_order_id = fields.Many2one('job.order', string="Work Order")
    product_id = fields.Many2one(
        'product.product', domain="[('is_overhead','=',True)]")
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id')
    name = fields.Char(string="Description")
    qty = fields.Integer(string="Qty.", default=1)
    uom_id = fields.Many2one(
        related="product_id.uom_po_id", string="Unit of Measure")
    cost = fields.Monetary(string="Cost / Unit")
    sub_total = fields.Monetary(compute="_compute_sub_total", store=True)
    vendor_id = fields.Many2one('res.partner')
    is_bill_created = fields.Boolean()
    purchase_order_id = fields.Many2one('purchase.order')
    sub_category_id = fields.Many2one(
        'job.sub.category', string="Work Sub Type")
    overhead_sub_contract_id = fields.Many2one(
        'overhead.subcontract', string="Subcontract")
    overhead_sub_contract_stage = fields.Selection(related="overhead_sub_contract_id.stage",
                                                   store=True)

    phase_forcast_qty = fields.Float()
    tax_id = fields.Many2one('account.tax', string="Taxes")

    # Budget Field
    job_sheet_id = fields.Many2one(
        related="job_order_id.job_sheet_id", store=True)
    project_id = fields.Many2one(related="job_order_id.project_id", store=True)
    work_type_id = fields.Many2one(
        related="job_order_id.work_type_id", store=True)
    state = fields.Selection(related="job_order_id.state", store=True)

    @api.depends('cost', 'qty', 'tax_id')
    def _compute_sub_total(self):
        """Compute sub total"""
        for rec in self:
            total = 0.0
            if rec.cost and rec.qty:
                total = rec.cost * rec.qty
            if rec.tax_id:
                tax_amount = rec.tax_id.amount * total / 100
                total = tax_amount + total
            rec.sub_total = total

    @api.onchange('product_id')
    def _onchange_product_desc(self):
        """Onchange Product Description"""
        for rec in self:
            rec.name = rec.product_id.name
            rec.cost = rec.product_id.standard_price
