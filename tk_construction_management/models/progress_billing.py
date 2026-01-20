# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
from odoo import fields, api, models, _
from odoo.exceptions import ValidationError


class ProgressBilling(models.Model):
    """Progress Billing"""
    _name = 'progress.billing'
    _description = "Customer Progress Billing"

    active = fields.Boolean(default=True)
    project_id = fields.Many2one(
        'tk.construction.project', string="Construction Project")
    date = fields.Date(default=fields.Date.today())
    name = fields.Char()
    status = fields.Selection([('draft', 'Draft'),
                               ('in_progress', 'In Progress'),
                               ('complete', 'Completed'),
                               ('cancel', 'Cancelled')], default='draft')
    phase_ids = fields.Many2many('job.costing',
                                 domain="[('project_id','=',project_id)]")
    work_order_ids = fields.Many2many('job.order',
                                      domain="[('job_sheet_id','in',phase_ids)]")
    customer_id = fields.Many2one('res.partner')
    invoice_type = fields.Selection(
        [('separate_invoice', 'Type Wise Invoice'),
         ('single_invoice', 'Single Invoice')],
        default='separate_invoice')

    # Include Line
    material_line = fields.Boolean(string="Material Lines")
    equipment_line = fields.Boolean(string="Equipment Lines")
    labour_line = fields.Boolean(string="Labour Lines")
    overhead_line = fields.Boolean(string="Overhead Lines")

    # Billing Lines
    material_billing_line_ids = fields.One2many(
        'billing.material.line', 'progress_bill_id')
    equipment_billing_line_ids = fields.One2many(
        'billing.equipment.line', 'progress_bill_id')
    labour_billing_line_ids = fields.One2many(
        'billing.labour.line', 'progress_bill_id')
    overhead_billing_line_ids = fields.One2many(
        'billing.overhead.line', 'progress_bill_id')
    other_billing_line_ids = fields.One2many(
        'billing.other.lines', 'progress_bill_id')

    # Total Amount
    company_id = fields.Many2one('res.company',
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id')
    material_total_amount = fields.Monetary(
        string="Material Total", compute="_compute_total_amount")
    equipment_total_amount = fields.Monetary(string="Equipment Total",
                                             compute="_compute_total_amount")
    labour_total_amount = fields.Monetary(
        string="Labour Total", compute="_compute_total_amount")
    overhead_total_amount = fields.Monetary(
        string="Overhead Total", compute="_compute_total_amount")
    other_total_amount = fields.Monetary(
        string="Other Total", compute="_compute_total_amount")
    total_amount = fields.Monetary(compute="_compute_total_amount")

    # Count
    invoice_count = fields.Integer(compute="_compute_count")

    @api.ondelete(at_uninstall=False)
    def _unlink_progress_billing(self):
        for rec in self:
            validation = None
            invoices = self.env['account.move'].sudo().search(
                [('progress_bill_id', '=', rec.id)])
            if rec.status == 'complete' and invoices:
                validation = "You cannot delete completed bill entry."
            if validation:
                raise ValidationError(_(validation))

    # View Invoice
    def action_view_invoice(self):
        """View Invoice"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Billing Invoice'),
            'res_model': 'account.move',
            'domain': [('progress_bill_id', '=', self.id)],
            'context': {'create': self.id},
            'view_mode': 'list,kanban,form',
            'target': 'current'
        }

    def action_update_status(self):
        """Update Status"""
        if self._context.get('to') == 'in_progress':
            self.status = 'in_progress'
        if self._context.get('to') == 'complete':
            self.status = 'complete'
        if self._context.get('to') == 'cancel':
            self.status = 'cancel'
        if self._context.get('to') == 'reset_draft':
            self.status = 'draft'

    def _compute_count(self):
        """Compute Count"""
        for rec in self:
            rec.invoice_count = self.env['account.move'].search_count(
                [('progress_bill_id', '=', rec.id)])

    @api.depends('material_billing_line_ids',
                 'equipment_billing_line_ids',
                 'labour_billing_line_ids',
                 'overhead_billing_line_ids',
                 'other_billing_line_ids')
    def _compute_total_amount(self):
        """Compute Total Amount"""
        for rec in self:
            material_total = sum(
                rec.material_billing_line_ids.mapped('total_amount'))
            equipment_total = sum(
                rec.equipment_billing_line_ids.mapped('total_amount'))
            labour_total = sum(
                rec.labour_billing_line_ids.mapped('total_amount'))
            overhead_total = sum(
                rec.overhead_billing_line_ids.mapped('total_amount'))
            other_total = sum(
                rec.other_billing_line_ids.mapped('total_amount'))
            total = material_total + equipment_total + \
                labour_total + overhead_total + other_total
            rec.total_amount = total
            rec.material_total_amount = material_total
            rec.equipment_total_amount = equipment_total
            rec.labour_total_amount = labour_total
            rec.overhead_total_amount = overhead_total
            rec.other_total_amount = other_total

    @api.onchange('material_line', 'work_order_ids')
    def onchange_work_order_material_items(self):
        """onchange work order material items"""
        for rec in self:
            lines = []
            rec.material_billing_line_ids = [(5, 0, 0)]
            if rec.material_line:
                for data in rec.work_order_ids:
                    if data.material_order_ids:
                        lines.append((0, 0, {
                            'name': 'Material',
                            'display_type': 'line_section'
                        }))
                        for material in data.material_order_ids:
                            lines.append((0, 0, {
                                'product_id': material.material_id.id,
                                'name': material.name,
                                'qty': material.qty,
                                'price': material.price,
                                'tax_ids': [
                                    (6, 0, [material.tax_id.id])] if material.tax_id else False,
                                'display_type': False,
                                'phase_ref': material.job_sheet_id.name,
                                'work_order_ref': data.name,
                            }))
            rec.material_billing_line_ids = lines

    @api.onchange('equipment_line', 'work_order_ids')
    def onchange_work_order_equipment_items(self):
        """onchange work order equipment items"""
        for rec in self:
            lines = []
            rec.equipment_billing_line_ids = [(5, 0, 0)]
            if rec.equipment_line:
                for data in rec.work_order_ids:
                    if data.equipment_order_ids:
                        lines.append((0, 0, {
                            'name': 'Equipment',
                            'display_type': 'line_section'
                        }))
                        for equip in data.equipment_order_ids:
                            lines.append((0, 0, {
                                'product_id': equip.equipment_id.id,
                                'name': equip.desc,
                                'qty': equip.qty,
                                'price': equip.cost,
                                'tax_ids': [(6, 0, [equip.tax_id.id])] if equip.tax_id else False,
                                'display_type': False,
                                'phase_ref': equip.job_sheet_id.name,
                                'work_order_ref': data.name,
                            }))
            rec.equipment_billing_line_ids = lines

    #
    @api.onchange('labour_line', 'work_order_ids')
    def onchange_work_order_labour_items(self):
        """onchange work order labour items"""
        for rec in self:
            lines = []
            rec.labour_billing_line_ids = [(5, 0, 0)]
            if rec.labour_line:
                for data in rec.work_order_ids:
                    if data.labour_order_ids:
                        lines.append((0, 0, {
                            'name': 'Labour',
                            'display_type': 'line_section'
                        }))
                        for labour in data.labour_order_ids:
                            lines.append((0, 0, {
                                'product_id': labour.product_id.id,
                                'name': labour.name,
                                'qty': labour.hours,
                                'price': labour.cost,
                                'tax_ids': [(6, 0, [labour.tax_id.id])] if labour.tax_id else False,
                                'display_type': False,
                                'phase_ref': labour.job_sheet_id.name,
                                'work_order_ref': labour.name,
                            }))
            rec.labour_billing_line_ids = lines

    @api.onchange('overhead_line', 'work_order_ids')
    def onchange_work_order_overhead_items(self):
        """onchange work order overhead items"""
        for rec in self:
            lines = []
            rec.overhead_billing_line_ids = [(5, 0, 0)]
            if rec.overhead_line:
                for data in rec.work_order_ids:
                    if data.overhead_order_ids:
                        lines.append((0, 0, {
                            'name': 'Overhead',
                            'display_type': 'line_section'
                        }))
                        for overhead in data.overhead_order_ids:
                            lines.append((0, 0, {
                                'product_id': overhead.product_id.id,
                                'name': overhead.name,
                                'qty': overhead.qty,
                                'price': overhead.cost,
                                'tax_ids': [
                                    (6, 0, [overhead.tax_id.id])] if overhead.tax_id else False,
                                'display_type': False,
                                'phase_ref': overhead.job_sheet_id.name,
                                'work_order_ref': overhead.name,
                            }))
            rec.overhead_billing_line_ids = lines

    def action_create_invoice(self):
        """Create Invoice"""
        if self.invoice_type == 'separate_invoice':
            if self.material_billing_line_ids:
                material_lines = self.action_prepare_invoice_line(
                    self.material_billing_line_ids)
                self.action_create_move_invoice(
                    material_lines, "Material", self.customer_id.id)
            if self.equipment_billing_line_ids:
                equip_lines = self.action_prepare_invoice_line(
                    self.equipment_billing_line_ids)
                self.action_create_move_invoice(
                    equip_lines, "Equipment", self.customer_id.id)
            if self.labour_billing_line_ids:
                labour_lines = self.action_prepare_invoice_line(
                    self.labour_billing_line_ids)
                self.action_create_move_invoice(
                    labour_lines, "Labour", self.customer_id.id)
            if self.overhead_billing_line_ids:
                overhead_lines = self.action_prepare_invoice_line(
                    self.overhead_billing_line_ids)
                self.action_create_move_invoice(
                    overhead_lines, "Overhead", self.customer_id.id)
            if self.other_billing_line_ids:
                other_lines = self.action_prepare_invoice_line(
                    self.other_billing_line_ids)
                self.action_create_move_invoice(
                    other_lines, "Other", self.customer_id.id)
        if self.invoice_type == 'single_invoice':
            lines = self.action_create_single_invoice()
            self.action_create_move_invoice(lines, False, self.customer_id.id)
        self.status = 'complete'

    def action_create_move_invoice(self, lines, source, customer_id):
        """Create Move Invoice"""
        self.env['account.move'].create({
            'partner_id': customer_id,
            'move_type': 'out_invoice',
            'invoice_date': self.date,
            'progress_bill_id': self.id,
            'bill_of': source,
            'invoice_line_ids': lines,
        })

    def action_prepare_invoice_line(self, lines_data):
        """Prepare Invoice Lines"""
        lines = []
        for data in lines_data:
            if not data.display_type:
                lines.append((0, 0, {
                    'product_id': data.product_id.id,
                    'name': data.name,
                    'quantity': data.qty,
                    'price_unit': data.price,
                    'tax_ids': [(6, 0, data.tax_ids.ids)]
                }))
        return lines

    def action_create_single_invoice(self):
        """Create Single Invoice"""
        lines = []
        if self.material_billing_line_ids:
            lines.append(
                (0, 0, {'display_type': 'line_section', 'name': 'Material'}))
            lines = (lines
                     + self.action_prepare_invoice_line(self.material_billing_line_ids))
        if self.equipment_billing_line_ids:
            lines.append((0, 0,
                          {'display_type': 'line_section',
                           'name': 'Equipment'}))
            lines = (lines
                     + self.action_prepare_invoice_line(self.equipment_billing_line_ids))
        if self.labour_billing_line_ids:
            lines.append((0, 0,
                          {'display_type': 'line_section',
                           'name': 'Labour'}))
            lines = (lines
                     + self.action_prepare_invoice_line(self.labour_billing_line_ids))
        if self.overhead_billing_line_ids:
            lines.append((0, 0,
                          {'display_type': 'line_section',
                           'name': 'Overhead'}))
            lines = (lines
                     + self.action_prepare_invoice_line(self.overhead_billing_line_ids))
        if self.other_billing_line_ids:
            lines.append((0, 0,
                          {'display_type': 'line_section',
                           'name': 'Other'}))
            lines = (lines
                     + self.action_prepare_invoice_line(self.other_billing_line_ids))
        return lines


class BillingOtherLine(models.Model):
    """Billing Order Lines"""
    _name = 'billing.other.lines'
    _description = "Progress Billing Other Lines"

    sequence = fields.Integer()
    product_id = fields.Many2one('product.product')
    qty = fields.Float(string="Qty.", default=1)
    uom_id = fields.Many2one(
        related="product_id.uom_po_id", string="Unit of Measure")
    name = fields.Text(string="Description")
    progress_bill_id = fields.Many2one(
        'progress.billing', string="Progress Billing")
    display_type = fields.Selection(selection=[('line_section', "Section"),
                                               ('line_note', "Note")], default=False)
    company_id = fields.Many2one('res.company',
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id')
    price = fields.Monetary(string="Unit Price")
    tax_ids = fields.Many2many('account.tax', string="Taxes")
    untaxed_amount = fields.Monetary(compute="_compute_total")
    tax_amount = fields.Monetary(compute="_compute_total")
    total_amount = fields.Monetary(compute="_compute_total")

    @api.depends('price', 'qty', 'tax_ids', 'display_type')
    def _compute_total(self):
        """Compute Total"""
        for rec in self:
            untaxed_amount = 0.0
            tax_amount = 0.0
            total_amount = 0.0
            if not rec.display_type:
                tax_total = sum(rec.tax_ids.mapped('amount'))
                untaxed_amount = rec.qty * rec.price
                tax_amount = tax_total * untaxed_amount / 100
                total_amount = untaxed_amount + tax_amount
            rec.untaxed_amount = untaxed_amount
            rec.tax_amount = tax_amount
            rec.total_amount = total_amount

    @api.onchange('product_id')
    def _onchange_product_info(self):
        """Onchange Product Info"""
        for rec in self:
            if rec.product_id:
                rec.name = rec.product_id.name
                rec.price = rec.product_id.lst_price


class BillingMaterialLine(models.Model):
    """Billing Material Lines"""
    _name = 'billing.material.line'
    _description = "Customer Progress Billing Material Lines"

    sequence = fields.Integer()
    product_id = fields.Many2one('product.product',
                                 domain="[('is_material','=',True)]")
    qty = fields.Float(string="Qty.", default=1)
    uom_id = fields.Many2one(
        related="product_id.uom_po_id", string="Unit of Measure")
    name = fields.Text(string="Description")
    progress_bill_id = fields.Many2one(
        'progress.billing', string="Progress Billing")
    display_type = fields.Selection(selection=[('line_section', "Section"),
                                               ('line_note', "Note")], default=False)
    phase_ref = fields.Char(string="Phase Ref.")
    work_order_ref = fields.Char(string="Work Order Ref.")
    company_id = fields.Many2one('res.company',
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency',
                                  related='company_id.currency_id')
    price = fields.Monetary(string="Unit Price")
    tax_ids = fields.Many2many('account.tax', string="Taxes")
    untaxed_amount = fields.Monetary(compute="_compute_total")
    tax_amount = fields.Monetary(compute="_compute_total")
    total_amount = fields.Monetary(compute="_compute_total")

    @api.depends('price', 'qty', 'tax_ids', 'display_type')
    def _compute_total(self):
        """Compute Total"""
        for rec in self:
            untaxed_amount = 0.0
            tax_amount = 0.0
            total_amount = 0.0
            if not rec.display_type:
                tax_total = sum(rec.tax_ids.mapped('amount'))
                untaxed_amount = rec.qty * rec.price
                tax_amount = tax_total * untaxed_amount / 100
                total_amount = untaxed_amount + tax_amount
            rec.untaxed_amount = untaxed_amount
            rec.tax_amount = tax_amount
            rec.total_amount = total_amount

    @api.onchange('product_id')
    def _onchange_product_info(self):
        """Onchange Product Info"""
        for rec in self:
            if rec.product_id:
                rec.name = rec.product_id.name
                rec.price = rec.product_id.lst_price


class BillingEquipmentLine(models.Model):
    """Billing Equipment Lines"""
    _name = 'billing.equipment.line'
    _description = "Customer Progress Billing Equipments Lines"

    sequence = fields.Integer()
    product_id = fields.Many2one('product.product',
                                 domain="[('is_equipment','=',True)]")
    qty = fields.Float(string="Qty.", default=1)
    uom_id = fields.Many2one(
        related="product_id.uom_po_id", string="Unit of Measure")
    name = fields.Text(string="Description")
    progress_bill_id = fields.Many2one(
        'progress.billing', string="Progress Billing")
    display_type = fields.Selection(selection=[('line_section', "Section"),
                                               ('line_note', "Note")], default=False)
    phase_ref = fields.Char(string="Phase Ref.")
    work_order_ref = fields.Char(string="Work Order Ref.")
    company_id = fields.Many2one('res.company',
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    price = fields.Monetary(string="Unit Price")
    tax_ids = fields.Many2many('account.tax', string="Taxes")
    untaxed_amount = fields.Monetary(compute="_compute_total")
    tax_amount = fields.Monetary(compute="_compute_total")
    total_amount = fields.Monetary(compute="_compute_total")

    @api.depends('price', 'qty', 'tax_ids', 'display_type')
    def _compute_total(self):
        """Compute total"""
        for rec in self:
            untaxed_amount = 0.0
            tax_amount = 0.0
            total_amount = 0.0
            if not rec.display_type:
                tax_total = sum(rec.tax_ids.mapped('amount'))
                untaxed_amount = rec.qty * rec.price
                tax_amount = tax_total * untaxed_amount / 100
                total_amount = untaxed_amount + tax_amount
            rec.untaxed_amount = untaxed_amount
            rec.tax_amount = tax_amount
            rec.total_amount = total_amount

    @api.onchange('product_id')
    def _onchange_product_info(self):
        """onchange Product Info"""
        for rec in self:
            if rec.product_id:
                rec.name = rec.product_id.name
                rec.price = rec.product_id.lst_price


class BillingLabourLine(models.Model):
    """Billing Labour Lines"""
    _name = 'billing.labour.line'
    _description = "Customer Progress Billing Labour Lines"

    sequence = fields.Integer()
    product_id = fields.Many2one('product.product',
                                 domain="[('is_labour','=',True)]")
    qty = fields.Float(string="Qty.", default=1)
    uom_id = fields.Many2one(
        related="product_id.uom_po_id", string="Unit of Measure")
    name = fields.Text(string="Description")
    progress_bill_id = fields.Many2one(
        'progress.billing', string="Progress Billing")
    display_type = fields.Selection(selection=[('line_section', "Section"),
                                               ('line_note', "Note")], default=False)
    phase_ref = fields.Char(string="Phase Ref.")
    work_order_ref = fields.Char(string="Work Order Ref.")
    company_id = fields.Many2one('res.company',
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    price = fields.Monetary(string="Unit Price")
    tax_ids = fields.Many2many('account.tax', string="Taxes")
    untaxed_amount = fields.Monetary(compute="_compute_total")
    tax_amount = fields.Monetary(compute="_compute_total")
    total_amount = fields.Monetary(compute="_compute_total")

    @api.depends('price', 'qty', 'tax_ids', 'display_type')
    def _compute_total(self):
        """Compute total"""
        for rec in self:
            untaxed_amount = 0.0
            tax_amount = 0.0
            total_amount = 0.0
            if not rec.display_type:
                tax_total = sum(rec.tax_ids.mapped('amount'))
                untaxed_amount = rec.qty * rec.price
                tax_amount = tax_total * untaxed_amount / 100
                total_amount = untaxed_amount + tax_amount
            rec.untaxed_amount = untaxed_amount
            rec.tax_amount = tax_amount
            rec.total_amount = total_amount

    @api.onchange('product_id')
    def _onchange_product_info(self):
        """Onchange product info"""
        for rec in self:
            if rec.product_id:
                rec.name = rec.product_id.name
                rec.price = rec.product_id.lst_price


class BillingOverheadLine(models.Model):
    """Billing Overhead Lines"""
    _name = 'billing.overhead.line'
    _description = "Customer Progress Billing Overhead Lines"

    sequence = fields.Integer()
    product_id = fields.Many2one('product.product',
                                 domain="[('is_overhead','=',True)]")
    qty = fields.Float(string="Qty.", default=1)
    uom_id = fields.Many2one(
        related="product_id.uom_po_id", string="Unit of Measure")
    name = fields.Text(string="Description")
    progress_bill_id = fields.Many2one(
        'progress.billing', string="Progress Billing")
    display_type = fields.Selection(selection=[('line_section', "Section"),
                                               ('line_note', "Note")], default=False)
    phase_ref = fields.Char(string="Phase Ref.")
    work_order_ref = fields.Char(string="Work Order Ref.")
    company_id = fields.Many2one('res.company',
                                 default=lambda self: self.env.company)
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    price = fields.Monetary(string="Unit Price")
    tax_ids = fields.Many2many('account.tax', string="Taxes")
    untaxed_amount = fields.Monetary(compute="_compute_total")
    tax_amount = fields.Monetary(compute="_compute_total")
    total_amount = fields.Monetary(compute="_compute_total")

    @api.depends('price', 'qty', 'tax_ids', 'display_type')
    def _compute_total(self):
        """Compute total"""
        for rec in self:
            untaxed_amount = 0.0
            tax_amount = 0.0
            total_amount = 0.0
            if not rec.display_type:
                tax_total = sum(rec.tax_ids.mapped('amount'))
                untaxed_amount = rec.qty * rec.price
                tax_amount = tax_total * untaxed_amount / 100
                total_amount = untaxed_amount + tax_amount
            rec.untaxed_amount = untaxed_amount
            rec.tax_amount = tax_amount
            rec.total_amount = total_amount

    @api.onchange('product_id')
    def _onchange_product_info(self):
        """Onchange product info"""
        for rec in self:
            if rec.product_id:
                rec.name = rec.product_id.name
                rec.price = rec.product_id.lst_price
