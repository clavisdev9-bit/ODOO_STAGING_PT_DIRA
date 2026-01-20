# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class EquipmentSubcontract(models.Model):
    """Equipment Subcontract"""
    _name = 'equipment.subcontract'
    _description = "Equipment Subcontract"
    _rec_name = 'seq'

    active = fields.Boolean(default=True)
    seq = fields.Char(string='Sequence', required=True,
                      readonly=True, default=lambda self: _('New'))
    name = fields.Char(string="Title")
    equipment_id = fields.Many2one(
        'product.product', string="Equipment", domain="[('is_equipment','=',True)]")
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id')
    cost_type = fields.Selection([('depreciation_cost', 'Depreciation Cost'),
                                  ('investment_cost', 'Investment/Interest Cost'),
                                  ('tax', 'Tax'),
                                  ('rent', 'Rent'),
                                  ('other', 'Other')], string="Type ", default='rent')
    cost = fields.Monetary(string="Estimation Cost")
    vendor_id = fields.Many2one('res.partner')
    purchase_order_id = fields.Many2one('purchase.order')
    job_type_id = fields.Many2one('job.type', string="Work Type")
    sub_category_id = fields.Many2one(
        'job.sub.category', string="Work Sub Type")
    stage = fields.Selection(
        [('draft', 'Draft'), ('in_progress', 'In Progress'), ('done', 'Done')],
        default='draft')
    po_bill = fields.Selection(
        [('bill', 'Bill'), ('purchase_order', 'Purchase Order')], string="Type",
        default='bill')
    ra_bill_ids = fields.One2many(
        'equip.contract.line', 'contract_id')
    completion_date = fields.Date(compute="_compute_completion_date")

    # Calculation
    qty = fields.Integer(string="Qty.", default=1)
    remain_qty = fields.Integer(string="Remaining Qty")
    total_cost = fields.Monetary()
    remaining_amount = fields.Monetary()
    progress = fields.Float(string="Complete Billing",
                            compute="_compute_payment_progress")
    tax_id = fields.Many2one('account.tax')

    # Project Details
    job_order_id = fields.Many2one('job.order', string="Work Order")
    phase_id = fields.Many2one(
        related="job_order_id.job_sheet_id", string="Project Phase(WBS)", store=True)
    project_id = fields.Many2one(
        related='job_order_id.project_id', string="Sub Project", store=True)
    task_id = fields.Many2one(
        related="job_order_id.task_id", store=True)

    # Resposible
    responsible_id = fields.Many2one(related="job_order_id.responsible_id")

    @api.model_create_multi
    def create(self, vals_list):
        """Create"""
        for vals in vals_list:
            if vals.get('seq', _('New')) == _('New'):
                vals['seq'] = self.env['ir.sequence'].next_by_code(
                    'equip.sub') or _('New')
        res = super().create(vals_list)
        return res

    @api.ondelete(at_uninstall=False)
    def _unlink_equip_subcontract(self):
        for rec in self:
            if rec.ra_bill_ids:
                if rec.po_bill == 'purchase_order' and rec.ra_bill_ids.filtered(
                        lambda r: r.purchase_order_id):
                    raise ValidationError(_("Purchase order are created "
                                            "for this sub contract please "
                                            "delete it first."))
                if rec.po_bill == 'bill' and rec.ra_bill_ids.filtered(
                        lambda r: r.bill_id):
                    raise ValidationError(
                        _("Bills are created for this sub contract please delete it "
                          "first."))

    def action_in_progress(self):
        """Status : In Progress"""
        self.stage = 'in_progress'

    def action_state_done(self):
        """Status : Done"""
        self.stage = 'done'

    @api.constrains('ra_bill_ids', 'qty')
    def _check_ra_bill_qty(self):
        """Check ra bill qty"""
        qty = 0
        for record in self.ra_bill_ids:
            if record.qc_status != 'reject':
                qty = qty + record.qty
        if qty > self.qty:
            raise ValidationError(_("Quantity should be less than total qty."))

    @api.depends('total_cost', 'remaining_amount')
    def _compute_payment_progress(self):
        """Compute payment progress"""
        for rec in self:
            progress = 0.0
            if rec.total_cost and rec.remaining_amount:
                progress = (rec.remaining_amount * 100) / rec.total_cost
            rec.progress = 100 - progress

    @api.depends('stage', 'ra_bill_ids')
    def _compute_completion_date(self):
        """Compute completion date"""
        for rec in self:
            date = None
            if rec.stage == "done":
                dates = rec.ra_bill_ids.mapped('date')
                if dates:
                    date = dates[-1]
            rec.completion_date = date


class EquipContractLine(models.Model):
    """Equipment Contract Line"""
    _name = 'equip.contract.line'
    _description = "Equip Contract Line"
    _rec_name = 'display_name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    active = fields.Boolean(default=True)
    contract_id = fields.Many2one(
        'equipment.subcontract', string="Subcontract", ondelete='cascade')
    percentage = fields.Float(tracking=True, compute="_compute_percentage")
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id')
    amount = fields.Monetary(
        tracking=True, compute="_compute_percentage_amount")
    date = fields.Date(
        default=fields.Date.today(), tracking=True)
    remark = fields.Char(tracking=True)
    purchase_order_id = fields.Many2one(
        'purchase.order')
    bill_id = fields.Many2one('account.move')
    payment_state = fields.Selection(
        related="bill_id.payment_state", tracking=True)
    state = fields.Selection(
        related="purchase_order_id.state", tracking=True)
    po_bill = fields.Selection(related="contract_id.po_bill")
    qty = fields.Integer()
    retention_percentage = fields.Float(string="Retention(%)")
    retention_amount = fields.Monetary(
        compute="_compute_retention_amount")
    final_amount = fields.Monetary(
        string="Total Amount", compute="_compute_final_amount")

    # QC Check
    qc_user_id = fields.Many2one(
        'res.users', string="QC Responsible", tracking=True)
    qc_status = fields.Selection(
        [('draft', 'Draft'),
         ('request', 'Department Approval'),
         ('approve', 'Approved'),
         ('reject', 'Rejected')], default='draft', string="Quality Check Status", tracking=True)
    reject_reason = fields.Text(tracking=True)

    @api.ondelete(at_uninstall=False)
    def _unlink_equip_contract_line(self):
        for rec in self:
            if rec.qc_status != 'draft':
                raise ValidationError(
                    _("You can't delete until Quality Check status is in Draft"))

    @api.depends('contract_id')
    def _compute_display_name(self):
        """Compute display name"""
        for rec in self:
            rec.display_name = (
                f"{rec.contract_id.job_order_id.name}-{rec.contract_id.seq}")

    @api.constrains('qty')
    def _check_ra_bill_qty(self):
        """Compute Ra Bill Qty"""
        ra_bill_ids = self.env['equip.contract.line'].search(
            [('contract_id', '=', self.contract_id.id)])
        qty = 0
        for record in ra_bill_ids:
            if record.qc_status != 'reject':
                qty = qty + record.qty
        if qty > self.contract_id.qty:
            raise ValidationError(_("Quantity should be less than total qty."))
        if self.qty <= 0:
            raise ValidationError(_("Quantity should be greater than 0 !"))

    @api.constrains("retention_percentage")
    def _check_retention_percentage(self):
        """Check retention_percentage value"""
        for rec in self:
            if rec.retention_percentage < 0:
                raise ValidationError(_("Retention Percentage cannot be negative"))

    @api.depends('contract_id', 'qty', 'contract_id.tax_id')
    def _compute_percentage_amount(self):
        """Compute percentage amount"""
        for rec in self:
            amount = 0.0
            if rec.qty and rec.contract_id:
                amount = (rec.contract_id.cost + (rec.contract_id.tax_id.amount *
                                                  rec.contract_id.cost / 100)) * rec.qty
            rec.amount = amount

    @api.depends('qty', 'retention_amount')
    def _compute_final_amount(self):
        """Compute final amount"""
        for rec in self:
            total = 0.0
            if rec.amount:
                total = rec.amount - rec.retention_amount
            rec.final_amount = total

    @api.depends('amount', 'retention_percentage')
    def _compute_retention_amount(self):
        """Compute retention amount"""
        for rec in self:
            retention_amount = 0.0
            if rec.retention_percentage:
                retention_amount = rec.amount * rec.retention_percentage / 100
            rec.retention_amount = retention_amount

    @api.depends('contract_id', 'amount')
    def _compute_percentage(self):
        """Compute percentage"""
        for rec in self:
            percentage = 0.0
            if rec.contract_id and rec.amount > 0:
                percentage = (100 * rec.amount) / rec.contract_id.total_cost
            rec.percentage = percentage

    def action_quality_check(self):
        """Status : Request"""
        self.qc_status = 'request'

    def action_quality_check_approve(self):
        """Status : Approve"""
        if not self.contract_id.remain_qty >= self.qty:
            raise ValidationError(
                _("Please check remain qty before creating bill / purchase order !"))
        qty = self.contract_id.remain_qty
        self.contract_id.remain_qty = qty - self.qty
        self.qc_status = 'approve'
        self.qc_user_id = self.env.user.id

    def action_quality_check_reject(self):
        """Status : Reject"""
        self.qc_status = 'reject'
        self.qc_user_id = self.env.user.id

    def action_reset_to_draft(self):
        """Status : Reset to Draft"""
        self.qc_status = 'draft'

    def action_create_ra_bill(self):
        """Create Ra Bill"""
        if self.po_bill == 'bill':
            record = {
                'product_id': self.contract_id.equipment_id.id,
                'name': self.contract_id.name,
                'quantity': 1,
                'price_unit': self.final_amount,
                'tax_ids': False
            }
            invoice_lines = [(0, 0, record)]
            data = {
                'partner_id': self.contract_id.vendor_id.id,
                'invoice_date': self.date,
                'invoice_line_ids': invoice_lines,
                'move_type': 'in_invoice',
                'equipment_subcontract_id': self.contract_id.id,
                'job_order_id': self.contract_id.job_order_id.id,
                'purchase_order': 'equipment'
            }
            invoice_id = self.env['account.move'].sudo().create(data)
            self.bill_id = invoice_id.id
            remaining_amount = self.contract_id.remaining_amount
            self.contract_id.remaining_amount = remaining_amount - self.amount
            # qty = self.contract_id.remain_qty
            # self.contract_id.remain_qty = qty - self.qty
        elif self.po_bill == 'purchase_order':
            purchase_record = {
                'product_id': self.contract_id.equipment_id.id,
                'name': self.contract_id.name,
                'product_qty': 1,
                'price_unit': self.final_amount,
            }
            purchase_lines = [(0, 0, purchase_record)]
            purchase_data = {
                'partner_id': self.contract_id.vendor_id.id,
                'order_line': purchase_lines,
                'job_order_id': self.contract_id.job_order_id.id,
                'equipment_subcontract_id': self.contract_id.id,
                'purchase_order': 'equipment'
            }
            purchase_order_id = self.env['purchase.order'].create(
                purchase_data)
            self.purchase_order_id = purchase_order_id.id
            remaining_amount = self.contract_id.remaining_amount
            self.contract_id.remaining_amount = remaining_amount - self.amount
            # qty = self.contract_id.remain_qty
            # self.contract_id.remain_qty = qty - self.qty


class LabourSubcontract(models.Model):
    """Labour subcontract"""
    _name = 'labour.subcontract'
    _description = "Labour Sub Contract"
    _rec_name = 'seq'

    active = fields.Boolean(default=True)
    seq = fields.Char(string='Sequence', required=True,
                      readonly=True, default=lambda self: _('New'))
    name = fields.Char(string="Title")
    product_id = fields.Many2one(
        'product.product', string="Product", domain="[('is_labour','=',True)]")
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id')
    cost = fields.Monetary(string="Cost / Hour")
    po_bill = fields.Selection([('bill', 'Bill'), ('purchase_order', 'Purchase Order')],
                               string="Type",
                               default='bill')
    stage = fields.Selection([('draft', 'Draft'), ('in_progress', 'In Progress'), ('done', 'Done')],
                             default='draft')
    vendor_id = fields.Many2one('res.partner', string="Contractor")
    job_type_id = fields.Many2one('job.type', string="Work Type")
    sub_category_id = fields.Many2one(
        'job.sub.category', string="Work Sub Type")
    ra_bill_ids = fields.One2many(
        'labour.contract.line', 'contract_id')
    completion_date = fields.Date(compute="_compute_completion_date")

    # Project Details
    job_order_id = fields.Many2one('job.order', string="Work Order")
    phase_id = fields.Many2one(
        related="job_order_id.job_sheet_id", string="Project Phase(WBS)", store=True)
    project_id = fields.Many2one(
        related='job_order_id.project_id', string="Sub Project", store=True)
    task_id = fields.Many2one(
        related="job_order_id.task_id", store=True)

    # Calculation
    hours = fields.Float()
    remain_hours = fields.Float(string="Remaining Hours")
    total_cost = fields.Monetary()
    remaining_amount = fields.Monetary()
    progress = fields.Float(string="Completed Billing",
                            compute="_compute_payment_progress")
    tax_id = fields.Many2one('account.tax')

    # Resposible
    responsible_id = fields.Many2one(related="job_order_id.responsible_id")

    @api.model_create_multi
    def create(self, vals_list):
        """Create"""
        for vals in vals_list:
            if vals.get('seq', _('New')) == _('New'):
                vals['seq'] = self.env['ir.sequence'].next_by_code(
                    'labour.sub') or _('New')
        res = super().create(vals_list)
        return res

    @api.ondelete(at_uninstall=False)
    def _unlink_labour_subcontract(self):
        for rec in self:
            if rec.ra_bill_ids:
                if rec.po_bill == 'purchase_order' and rec.ra_bill_ids.filtered(
                        lambda r: r.purchase_order_id):
                    raise ValidationError(_("Purchase order are created "
                                            "for this sub contract please "
                                            "delete it first."))
                if rec.po_bill == 'bill' and rec.ra_bill_ids.filtered(
                        lambda r: r.bill_id):
                    raise ValidationError(
                        _("Bills are created for this sub contract please delete it "
                          "first."))

    def action_in_progress(self):
        """Status : In Progress"""
        self.stage = 'in_progress'

    def action_state_done(self):
        """Status : Done"""
        self.stage = 'done'

    @api.constrains('ra_bill_ids', 'hours')
    def _check_ra_bill_hours(self):
        """Status : Ra Bill Hours"""
        hours = 0
        for record in self.ra_bill_ids:
            if record.qc_status != 'reject':
                hours = hours + record.hours
        if hours > self.hours:
            raise ValidationError(_("Hours should be less than total hours"))

    @api.depends('total_cost', 'remaining_amount')
    def _compute_payment_progress(self):
        """Compute payment progress"""
        for rec in self:
            progress = 0.0
            if rec.total_cost and rec.remaining_amount:
                progress = (rec.remaining_amount * 100) / rec.total_cost
            rec.progress = 100 - progress

    @api.depends('stage', 'ra_bill_ids')
    def _compute_completion_date(self):
        """Compute completion date"""
        for rec in self:
            date = None
            if rec.stage == "done":
                dates = rec.ra_bill_ids.mapped('date')
                if dates:
                    date = dates[-1]
            rec.completion_date = date


class LabourContractLine(models.Model):
    """Labour Contract Line"""
    _name = 'labour.contract.line'
    _description = "Labour Contract Line"
    _rec_name = 'display_name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    active = fields.Boolean(default=True)
    contract_id = fields.Many2one(
        'labour.subcontract', string="Labour Subcontract", ondelete='cascade')
    percentage = fields.Float(tracking=True, compute="_compute_percentage")
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id')
    amount = fields.Monetary(
        tracking=True, compute="_compute_percentage_amount")
    date = fields.Date(
        default=fields.Date.today(), tracking=True)
    remark = fields.Char(tracking=True)
    purchase_order_id = fields.Many2one(
        'purchase.order')
    bill_id = fields.Many2one('account.move')
    payment_state = fields.Selection(
        related="bill_id.payment_state", tracking=True)
    state = fields.Selection(
        related="purchase_order_id.state", tracking=True)
    po_bill = fields.Selection(related="contract_id.po_bill")
    hours = fields.Float()
    retention_percentage = fields.Float(string="Retention(%)")
    retention_amount = fields.Monetary(
        compute="_compute_retention_amount")
    final_amount = fields.Monetary(
        string="Total Amount", compute="_compute_final_amount")

    # QC Check
    qc_user_id = fields.Many2one(
        'res.users', string="QC Responsible", tracking=True)
    qc_status = fields.Selection([('draft', 'Draft'),
                                  ('request', 'Department Approval'),
                                  ('approve', 'Approved'),
                                  ('reject', 'Rejected')],
                                 default='draft', string="Quality Check Status", tracking=True)
    reject_reason = fields.Text(tracking=True)

    @api.ondelete(at_uninstall=False)
    def _unlink_labour_contract_line(self):
        for rec in self:
            if rec.qc_status != 'draft':
                raise ValidationError(_("You can't delete until Quality Check status is in Draft"))

    @api.depends('contract_id')
    def _compute_display_name(self):
        """Compute display name"""
        for rec in self:
            rec.display_name = (
                f"{rec.contract_id.job_order_id.name}-{rec.contract_id.seq}")

    @api.constrains("retention_percentage")
    def _check_retention_percentage(self):
        """Check retention_percentage value"""
        for rec in self:
            if rec.retention_percentage < 0:
                raise ValidationError(_("Retention Percentage cannot be negative"))

    @api.constrains('hours')
    def _check_ra_bill_hours(self):
        """Check ra bill hours"""
        ra_bill_ids = self.env['labour.contract.line'].search(
            [('contract_id', '=', self.contract_id.id)])
        hours = 0
        for record in ra_bill_ids:
            if record.qc_status != 'reject':
                hours = hours + record.hours
        if hours > self.contract_id.hours:
            raise ValidationError(_("Hours should be less than total hours"))
        if self.hours <= 0:
            raise ValidationError(_("Hours should be greater than 0 !"))

    @api.depends('contract_id', 'hours', 'contract_id.tax_id')
    def _compute_percentage_amount(self):
        """Compute percentage amount"""
        for rec in self:
            amount = 0.0
            if rec.hours and rec.contract_id:
                amount = (rec.contract_id.cost + (
                        rec.contract_id.tax_id.amount * rec.contract_id.cost / 100)) * rec.hours
            rec.amount = amount

    @api.depends('hours', 'retention_amount')
    def _compute_final_amount(self):
        """Compute final Amount"""
        for rec in self:
            total = 0.0
            if rec.amount:
                total = rec.amount - rec.retention_amount
            rec.final_amount = total

    @api.depends('amount', 'retention_percentage')
    def _compute_retention_amount(self):
        """Compute retention amount"""
        for rec in self:
            retention_amount = rec.amount * rec.retention_percentage / 100
            rec.retention_amount = retention_amount

    @api.depends('contract_id', 'amount')
    def _compute_percentage(self):
        """Compute percentage"""
        for rec in self:
            percentage = 0.0
            if rec.contract_id and rec.amount > 0:
                percentage = (100 * rec.amount) / rec.contract_id.total_cost
            rec.percentage = percentage

    def action_quality_check(self):
        """Status : Request"""
        self.qc_status = 'request'

    def action_quality_check_approve(self):
        """Status : Approve"""
        if not self.contract_id.remain_hours >= self.hours:
            raise ValidationError(
                _("Please check remain qty before creating bill / purchase order !"))
        qty = self.contract_id.remain_hours
        self.contract_id.remain_hours = qty - self.hours
        self.qc_status = 'approve'
        self.qc_user_id = self.env.user.id

    def action_quality_check_reject(self):
        """Status : Reject"""
        self.qc_status = 'reject'
        self.qc_user_id = self.env.user.id

    def action_reset_to_draft(self):
        """Status : Reset to Draft"""
        self.qc_status = 'draft'

    def action_create_ra_bill(self):
        """Create RA Bills"""
        if self.po_bill == 'bill':
            record = {
                'product_id': self.contract_id.product_id.id,
                'name': self.contract_id.name,
                'quantity': 1,
                'price_unit': self.final_amount,
                'tax_ids': False
            }
            invoice_lines = [(0, 0, record)]
            data = {
                'partner_id': self.contract_id.vendor_id.id,
                'invoice_date': self.date,
                'invoice_line_ids': invoice_lines,
                'move_type': 'in_invoice',
                'labour_subcontract_id': self.contract_id.id,
                'job_order_id': self.contract_id.job_order_id.id,
                'purchase_order': 'equipment'
            }
            invoice_id = self.env['account.move'].sudo().create(data)
            remaining_amount = self.contract_id.remaining_amount
            self.contract_id.remaining_amount = remaining_amount - self.amount
            self.bill_id = invoice_id.id
            # qty = self.contract_id.remain_hours
            # self.contract_id.remain_hours = qty - self.hours
        elif self.po_bill == 'purchase_order':
            purchase_record = {
                'product_id': self.contract_id.product_id.id,
                'name': self.contract_id.name,
                'product_qty': 1,
                'price_unit': self.final_amount,
            }
            purchase_lines = [(0, 0, purchase_record)]
            purchase_data = {
                'partner_id': self.contract_id.vendor_id.id,
                'order_line': purchase_lines,
                'job_order_id': self.contract_id.job_order_id.id,
                'labour_subcontract_id': self.contract_id.id,
                'purchase_order': 'equipment'
            }
            purchase_order_id = self.env['purchase.order'].create(
                purchase_data)
            self.purchase_order_id = purchase_order_id.id
            remaining_amount = self.contract_id.remaining_amount
            self.contract_id.remaining_amount = remaining_amount - self.amount
            # qty = self.contract_id.remain_hours
            # self.contract_id.remain_hours = qty - self.hours


class OverheadSubcontract(models.Model):
    """Overhead Subcontract"""
    _name = 'overhead.subcontract'
    _description = "Overhead Subcontract"
    _rec_name = 'seq'

    active = fields.Boolean(default=True)
    seq = fields.Char(string='Sequence', required=True,
                      readonly=True, default=lambda self: _('New'))
    name = fields.Char(string="Title")
    product_id = fields.Many2one(
        'product.product', string="Product", domain="[('is_overhead','=',True)]")
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id')
    uom_id = fields.Many2one(
        related="product_id.uom_po_id", string="Unit of Measure")
    cost = fields.Monetary(string="Cost / Unit")
    po_bill = fields.Selection(
        [('bill', 'Bill'), ('purchase_order', 'Purchase Order')], string="Type", default='bill')
    stage = fields.Selection(
        [('draft', 'Draft'), ('in_progress', 'In Progress'), ('done', 'Done')], default='draft')
    vendor_id = fields.Many2one('res.partner')
    job_type_id = fields.Many2one('job.type', string="Work Type")
    sub_category_id = fields.Many2one(
        'job.sub.category', string="Work Sub Type")
    ra_bill_ids = fields.One2many(
        'overhead.contract.line', 'contract_id')
    completion_date = fields.Date(compute="_compute_completion_date")

    # Project Details
    job_order_id = fields.Many2one('job.order', string="Work Order")
    phase_id = fields.Many2one(
        related="job_order_id.job_sheet_id", string="Project Phase(WBS)", store=True)
    project_id = fields.Many2one(
        related='job_order_id.project_id', string="Sub Project", store=True)
    task_id = fields.Many2one(
        related="job_order_id.task_id", store=True)

    # Calculation
    qty = fields.Integer(string="Qty.", default=1)
    remain_qty = fields.Integer(string="Remaining Qty")
    total_cost = fields.Monetary()
    remaining_amount = fields.Monetary()
    progress = fields.Float(string="Completed Billing",
                            compute="_compute_payment_progress")
    tax_id = fields.Many2one('account.tax')

    # Responsible
    responsible_id = fields.Many2one(related="job_order_id.responsible_id")

    @api.model_create_multi
    def create(self, vals_list):
        """Create"""
        for vals in vals_list:
            if vals.get('seq', _('New')) == _('New'):
                vals['seq'] = self.env['ir.sequence'].next_by_code(
                    'overhead.sub') or _('New')
        res = super().create(vals_list)
        return res

    @api.ondelete(at_uninstall=False)
    def _unlink_equip_subcontract(self):
        for rec in self:
            if rec.ra_bill_ids:
                if rec.po_bill == 'purchase_order' and rec.ra_bill_ids.filtered(
                        lambda r: r.purchase_order_id):
                    raise ValidationError(_("Purchase order are created "
                                            "for this sub contract please "
                                            "delete it first."))
                if rec.po_bill == 'bill' and rec.ra_bill_ids.filtered(
                        lambda r: r.bill_id):
                    raise ValidationError(
                        _("Bills are created for this sub contract please delete it "
                          "first."))

    def action_in_progress(self):
        """Status : In Progress"""
        self.stage = 'in_progress'

    def action_state_done(self):
        """Status : Done"""
        self.stage = 'done'

    @api.constrains('ra_bill_ids', 'qty')
    def _check_ra_bill_qty(self):
        """Check RA Bill Qty"""
        qty = 0
        for record in self.ra_bill_ids:
            if record.qc_status != 'reject':
                qty = qty + record.qty
        if qty > self.qty:
            raise ValidationError(_("Quantity should be less than total qty."))

    @api.depends('total_cost', 'remaining_amount')
    def _compute_payment_progress(self):
        """Compute Payment Progress"""
        for rec in self:
            progress = 0.0
            if rec.total_cost and rec.remaining_amount:
                progress = (rec.remaining_amount * 100) / rec.total_cost
            rec.progress = 100 - progress

    @api.depends('stage', 'ra_bill_ids')
    def _compute_completion_date(self):
        """Compute completion date"""
        for rec in self:
            date = None
            if rec.stage == "done":
                dates = rec.ra_bill_ids.mapped('date')
                if dates:
                    date = dates[-1]
            rec.completion_date = date


class OverheadContractLine(models.Model):
    """Overhead Contract Line"""
    _name = 'overhead.contract.line'
    _description = "Overhead Contract Line"
    _rec_name = 'display_name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    active = fields.Boolean(default=True)
    contract_id = fields.Many2one(
        'overhead.subcontract', string="Overhead Subcontract", ondelete='cascade')
    percentage = fields.Float(tracking=True, compute="_compute_percentage")
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id')
    amount = fields.Monetary(
        tracking=True, compute="_compute_percentage_amount")
    date = fields.Date(
        default=fields.Date.today(), tracking=True)
    remark = fields.Char(tracking=True)
    purchase_order_id = fields.Many2one(
        'purchase.order')
    bill_id = fields.Many2one('account.move')
    payment_state = fields.Selection(
        related="bill_id.payment_state", tracking=True)
    state = fields.Selection(
        related="purchase_order_id.state", tracking=True)
    po_bill = fields.Selection(related="contract_id.po_bill")
    qty = fields.Integer()
    retention_percentage = fields.Float(string="Retention(%)")
    retention_amount = fields.Monetary(
        compute="_compute_retention_amount")
    final_amount = fields.Monetary(
        string="Total Amount", compute="_compute_final_amount")

    # QC Check
    qc_user_id = fields.Many2one(
        'res.users', string="QC Responsible", tracking=True)
    qc_status = fields.Selection([('draft', 'Draft'),
                                  ('request', 'Department Approval'),
                                  ('approve', 'Approved'),
                                  ('reject', 'Rejected')], default='draft',
                                 string="Quality Check Status", tracking=True)
    reject_reason = fields.Text(tracking=True)

    @api.ondelete(at_uninstall=False)
    def _unlink_overhead_line(self):
        """Unlink"""
        for rec in self:
            if rec.qc_status != 'draft':
                raise ValidationError(
                    _("You can't delete until Quality Check status is in Draft"))

    @api.depends('contract_id')
    def _compute_display_name(self):
        """Compute Display Name"""
        for rec in self:
            rec.display_name = (
                f"{rec.contract_id.job_order_id.name}-{rec.contract_id.seq}")

    @api.constrains("retention_percentage")
    def _check_retention_percentage(self):
        """Check retention_percentage value"""
        for rec in self:
            if rec.retention_percentage < 0:
                raise ValidationError(_("Retention Percentage cannot be negative"))

    @api.constrains('qty')
    def _check_ra_bill_qty(self):
        """Check ra bill qty"""
        ra_bill_ids = self.env['overhead.contract.line'].search(
            [('contract_id', '=', self.contract_id.id)])
        qty = 0
        for record in ra_bill_ids:
            if record.qc_status != 'reject':
                qty = qty + record.qty
        if qty > self.contract_id.qty:
            raise ValidationError(_("Quantity should be less than total qty."))
        if self.qty <= 0:
            raise ValidationError(_("Quantity should be greater than 0 !"))

    @api.depends('contract_id', 'qty', 'contract_id.tax_id')
    def _compute_percentage_amount(self):
        """Compute percentage amount"""
        for rec in self:
            amount = 0.0
            if rec.qty and rec.contract_id:
                amount = (rec.contract_id.cost + (rec.contract_id.tax_id.amount *
                                                  rec.contract_id.cost / 100)) * rec.qty
            rec.amount = amount

    @api.depends('qty', 'retention_amount')
    def _compute_final_amount(self):
        """Compute final amount"""
        for rec in self:
            total = 0.0
            if rec.amount:
                total = rec.amount - rec.retention_amount
            rec.final_amount = total

    @api.depends('amount', 'retention_percentage')
    def _compute_retention_amount(self):
        """Compute retention amount"""
        for rec in self:
            retention_amount = 0.0
            if rec.retention_percentage:
                retention_amount = rec.amount * rec.retention_percentage / 100
            rec.retention_amount = retention_amount

    @api.depends('contract_id', 'amount')
    def _compute_percentage(self):
        """compute percentage"""
        for rec in self:
            percentage = 0.0
            if rec.contract_id and rec.amount > 0:
                percentage = (100 * rec.amount) / rec.contract_id.total_cost
            rec.percentage = percentage

    def action_quality_check(self):
        """Status : Request"""
        self.qc_status = 'request'

    def action_quality_check_approve(self):
        """Status : Approve"""
        if not self.contract_id.remain_qty >= self.qty:
            raise ValidationError(
                _("Please check remain qty before creating bill / purchase order !"))
        self.qc_status = 'approve'
        self.contract_id.remain_qty = self.contract_id.remain_qty - self.qty
        self.qc_user_id = self.env.user.id

    def action_quality_check_reject(self):
        """Status : Reject"""
        self.qc_status = 'reject'
        self.qc_user_id = self.env.user.id

    def action_reset_to_draft(self):
        """Status : Draft"""
        self.qc_status = 'draft'

    def action_create_ra_bill(self):
        """Create RA Bills"""
        if self.po_bill == 'bill':
            record = {
                'product_id': self.contract_id.product_id.id,
                'name': self.contract_id.name,
                'quantity': 1,
                'price_unit': self.final_amount,
                'tax_ids': False
            }
            invoice_lines = [(0, 0, record)]
            data = {
                'partner_id': self.contract_id.vendor_id.id,
                'invoice_date': self.date,
                'invoice_line_ids': invoice_lines,
                'move_type': 'in_invoice',
                'overhead_subcontract_id': self.contract_id.id,
                'job_order_id': self.contract_id.job_order_id.id,
                'purchase_order': 'overhead'
            }
            invoice_id = self.env['account.move'].sudo().create(data)
            remaining_amount = self.contract_id.remaining_amount
            self.contract_id.remaining_amount = remaining_amount - self.amount
            self.bill_id = invoice_id.id
            # qty = self.contract_id.remain_qty
            # self.contract_id.remain_qty = qty - self.qty
        elif self.po_bill == 'purchase_order':
            purchase_record = {
                'product_id': self.contract_id.product_id.id,
                'name': self.contract_id.name,
                'product_qty': 1,
                'price_unit': self.final_amount,
            }
            purchase_lines = [(0, 0, purchase_record)]
            purchase_data = {
                'partner_id': self.contract_id.vendor_id.id,
                'order_line': purchase_lines,
                'job_order_id': self.contract_id.job_order_id.id,
                'overhead_subcontract_id': self.contract_id.id,
                'purchase_order': 'overhead'
            }
            purchase_order_id = self.env['purchase.order'].create(
                purchase_data)
            self.purchase_order_id = purchase_order_id.id
            remaining_amount = self.contract_id.remaining_amount
            self.contract_id.remaining_amount = remaining_amount - self.amount
            # qty = self.contract_id.remain_qty
            # self.contract_id.remain_qty = qty - self.qty


class MaterialConsume(models.Model):
    """Material Consume"""
    _name = 'material.consume'
    _description = "Material Consume Order"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'seq'

    active = fields.Boolean(default=True)
    seq = fields.Char(string='Sequence', required=True,
                      readonly=True, default=lambda self: _('New'))
    date = fields.Date(default=fields.Date.today())
    remark = fields.Char()
    warehouse_id = fields.Many2one('stock.warehouse')
    consume_order_id = fields.Many2one('stock.picking')
    state = fields.Selection(related="consume_order_id.state", string="Status")
    consume_order_ids = fields.One2many(
        'material.consume.line', 'material_consume_id', string="Material Consume")

    # Project Details
    job_order_id = fields.Many2one('job.order', string="Work Order")
    phase_id = fields.Many2one(
        related="job_order_id.job_sheet_id", string="Project Phase(WBS)", store=True)
    project_id = fields.Many2one(
        related='job_order_id.project_id', string="Sub Project", store=True)
    task_id = fields.Many2one(
        related="job_order_id.task_id", store=True)

    # Quality Check
    qc_user_id = fields.Many2one(
        'res.users', string="QC Responsible", tracking=True)
    qc_status = fields.Selection(
        [('draft', 'Draft'), ('request', 'Department Approval'), ('approve', 'Approved'),
         ('reject', 'Rejected'), ('cancel', 'Cancel')], default='draft',
        string="Quality Check Status", tracking=True)
    reject_reason = fields.Text(tracking=True)

    # Company
    company_id = fields.Many2one('res.company',
                                 default=lambda self: self.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        """Create"""
        for vals in vals_list:
            if vals.get('seq', _('New')) == _('New'):
                vals['seq'] = self.env['ir.sequence'].next_by_code(
                    'material.consume') or _('New')
        res = super().create(vals_list)
        return res

    def write(self, vals):
        """Write"""
        res = super().write(vals)
        if not self.consume_order_ids:
            raise ValidationError(_("Please add material consume line !"))
        return res

    @api.ondelete(at_uninstall=False)
    def _unlink_consume_order(self):
        """Unlink"""
        for rec in self:
            if rec.qc_status != 'draft':
                raise ValidationError(
                    _("You can't delete until Consume order status is in Draft"))

    @api.constrains('consume_order_ids')
    def _check_material_line_qty(self):
        """Material Line qty"""
        for rec in self.consume_order_ids:
            if rec.qty > rec.material_line_id.remain_qty:
                raise ValidationError(_("Qty should be less than remain Qty."))

    def action_quality_check(self):
        """Status : Request"""
        self.qc_status = 'request'

    def action_quality_check_approve(self):
        """Status : Approve"""
        for rec in self.consume_order_ids:
            remain_qty = rec.material_line_id.remain_qty
            usage_qty = rec.material_line_id.usage_qty
            actual_remain_qty = remain_qty - rec.qty
            if actual_remain_qty < 0:
                raise ValidationError(_("Check material remain qty before processing !"))
            rec.material_line_id.remain_qty = remain_qty - rec.qty
            rec.material_line_id.usage_qty = usage_qty + rec.qty
        self.qc_status = 'approve'
        self.qc_user_id = self.env.user.id

    def action_quality_check_reject(self):
        """Status : Reject"""
        self.qc_status = 'reject'
        self.qc_user_id = self.env.user.id

    def action_reset_to_draft(self):
        """Status : Draft"""
        self.qc_status = 'draft'

    def action_cancel_consume_order(self):
        """Status : Cancel"""
        self.qc_status = 'cancel'

    def action_create_consume_order(self):
        """Create Consume Order"""
        stock_picking_type_id = self.env['stock.picking.type'].search(
            [('code', '=', 'outgoing'), ('warehouse_id', '=', self.warehouse_id.id)], limit=1)
        if not stock_picking_type_id:
            message = {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'info',
                    'title': _('Invalid Warehouse Operation Type !'),
                    'message': self.warehouse_id.name + " : Delivery operation type not found",
                    'sticky': False,
                }
            }
            return message
        dest_location_id = False
        if self.warehouse_id.consume_stock_location_id:
            dest_location_id = self.warehouse_id.consume_stock_location_id
        else:
            dest_location_id = self.env['stock.location'].create(
                {'name': "Consume Location/" + str(self.warehouse_id.name), 'usage': 'production'})
            self.warehouse_id.consume_stock_location_id = dest_location_id.id
        lines = []
        for rec in self.consume_order_ids:
            lines.append((0, 0, {
                'product_id': rec.material_id.id,
                'product_uom_qty': rec.qty,
                'product_uom': rec.uom_id.id,
                'location_id': self.warehouse_id.lot_stock_id.id,
                'location_dest_id': dest_location_id.id,
                'name': rec.name
            }))
        source_id = self.warehouse_id.lot_stock_id
        delivery_record = {
            'picking_type_id': stock_picking_type_id.id,
            'location_id': source_id.id,
            'location_dest_id': dest_location_id.id,
            'move_ids_without_package': lines,
            'consume_order_id': self.job_order_id.id,
            'material_consume_id': self.id,
            'move_type': 'one'
        }
        delivery_id = self.env['stock.picking'].create(delivery_record)
        self.consume_order_id = delivery_id.id

        return {
            'type': 'ir.actions.act_window',
            'name': _('Consume Order'),
            'res_model': 'stock.picking',
            'res_id': delivery_id.id,
            'view_mode': 'form',
            'target': 'current'
        }


class MaterialConsumeLine(models.Model):
    """Materila Consume Line"""
    _name = 'material.consume.line'
    _description = "Material Consume Line"

    active = fields.Boolean(default=True)
    material_id = fields.Many2one(
        'product.product', string="Material", domain="[('is_material','=',True)]")
    uom_id = fields.Many2one(related="material_id.uom_id", string="UOM")
    name = fields.Char(string="Description")
    qty = fields.Integer()
    material_consume_id = fields.Many2one(
        'material.consume', string="Material Consume")
    qc_status = fields.Selection(related="material_consume_id.qc_status")
    material_line_id = fields.Many2one('order.material.line')
    remain_qty = fields.Integer(string="Remain Qty.")

    @api.onchange("qty", "remain_qty")
    def _onchange_remain_qty(self):
        """Onchnage remain qty"""
        for rec in self:
            if rec.qty > rec.remain_qty:
                raise ValidationError(
                    _("Qty should be lesser thn remain qty !"))
