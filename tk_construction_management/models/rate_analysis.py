# -*- coding: utf-8 -*-
# Copyright 2022-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class RateAnalysis(models.Model):
    """Rate analysis"""
    _name = 'rate.analysis'
    _description = "Rate Analysis"
    _rec_name = 'name'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string="Title")
    site_id = fields.Many2one(
        'tk.construction.site', string="Project", domain="[('status','=','in_progress')]")
    project_id = fields.Many2one('tk.construction.project', string="Sub Project",
                                 domain="[('construction_site_id','=',site_id)]")
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id')
    activity_id = fields.Many2one('job.type', string="Work Type")
    sub_activity_ids = fields.Many2many(
        related="activity_id.sub_category_ids", string="Sub Activities")
    sub_activity_id = fields.Many2one('job.sub.category', string="Work Sub Type",
                                      domain="[('id','in',sub_activity_ids)]")
    date = fields.Date(default=fields.Date.today())
    unit_id = fields.Many2one('uom.uom')
    ra_template_id = fields.Many2one(
        'ra.template', string="Template",
        domain="[('activity_id','=',activity_id),('sub_activity_id','=',sub_activity_id)]"
    )

    # Rate Analysis Type
    is_material = fields.Boolean(string="Material", default=True)
    is_equipment = fields.Boolean(string="Equipment", default=True)
    is_labour = fields.Boolean(string="Labour", default=True)
    is_overhead = fields.Boolean(string="Overhead", default=True)

    material_analysis_ids = fields.One2many(
        'rate.analysis.material', 'rate_analysis_id',
        string="Rate Analysis Material")
    equipment_analysis_ids = fields.One2many(
        'rate.analysis.equipment', 'rate_analysis_id',
        string="Rate Analysis Equipment")
    labour_analysis_ids = fields.One2many(
        'rate.analysis.labour', 'rate_analysis_id',
        string="Rate Analysis Labour")
    overhead_analysis_ids = fields.One2many(
        'rate.analysis.overhead', 'rate_analysis_id',
        string="Rate Analysis Overhead")

    # Sale Amount
    tax_amount = fields.Monetary(compute="_compute_total_amount")
    untaxed_amount = fields.Monetary(compute="_compute_total_amount")
    total_amount = fields.Monetary(compute="_compute_total_amount")

    # Cost Amount
    cost_tax_amount = fields.Monetary(
        string="Tax Amount(Cost)", compute="_compute_total_amount")
    cost_untaxed_amount = fields.Monetary(
        string="Untaxed Amount(Cost)", compute="_compute_total_amount")
    cost_total_amount = fields.Monetary(
        string="Total Amount(Cost)", compute="_compute_total_amount")

    # Ra Hours
    ra_hours_ids = fields.One2many(
        comodel_name='ra.employee.hours', inverse_name='rate_analysis_id')

    # Project Status
    project_status = fields.Selection(related="site_id.status")

    ra_type = fields.Selection([('qty_per_unit', 'Qty per Unit'),
                                ('total_required_qty', 'Total Required Qty')],
                               default='qty_per_unit')
    is_ra_used = fields.Boolean(compute="_compute_is_ra_used")

    @api.depends("ra_type")
    def _compute_is_ra_used(self):
        """Check if rate analysis is used in boq budget line or not"""
        for rec in self:
            rec.is_ra_used = bool(self.env["project.budget"].search(
                [('rate_analysis_id', '=', rec.id)], limit=1))

    @api.depends('material_analysis_ids',
                 'equipment_analysis_ids',
                 'labour_analysis_ids',
                 'overhead_analysis_ids',
                 'is_material',
                 'is_equipment',
                 'is_labour',
                 'is_overhead')
    def _compute_total_amount(self):
        """Compute total amount"""
        for rec in self:
            tax_amount = 0.0
            untaxed_amount = 0.0
            total_amount = 0.0
            cost_tax_amount = 0.0
            cost_untaxed_amount = 0.0
            cost_total_amount = 0.0
            if rec.is_material:
                for data in rec.material_analysis_ids:
                    tax_amount = tax_amount + data.tax_amount
                    untaxed_amount = untaxed_amount + data.untaxed_amount
                    total_amount = total_amount + data.total_amount
                    cost_tax_amount = cost_tax_amount + data.cost_tax_amount
                    cost_untaxed_amount = cost_untaxed_amount + data.cost_untaxed_amount
                    cost_total_amount = cost_total_amount + data.cost_total_amount
            if rec.is_equipment:
                for data in rec.equipment_analysis_ids:
                    tax_amount = tax_amount + data.tax_amount
                    untaxed_amount = untaxed_amount + data.untaxed_amount
                    total_amount = total_amount + data.total_amount
                    cost_tax_amount = cost_tax_amount + data.cost_tax_amount
                    cost_untaxed_amount = cost_untaxed_amount + data.cost_untaxed_amount
                    cost_total_amount = cost_total_amount + data.cost_total_amount
            if rec.is_labour:
                for data in rec.labour_analysis_ids:
                    tax_amount = tax_amount + data.tax_amount
                    untaxed_amount = untaxed_amount + data.untaxed_amount
                    total_amount = total_amount + data.total_amount
                    cost_tax_amount = cost_tax_amount + data.cost_tax_amount
                    cost_untaxed_amount = cost_untaxed_amount + data.cost_untaxed_amount
                    cost_total_amount = cost_total_amount + data.cost_total_amount
            if rec.is_overhead:
                for data in rec.overhead_analysis_ids:
                    tax_amount = tax_amount + data.tax_amount
                    untaxed_amount = untaxed_amount + data.untaxed_amount
                    total_amount = total_amount + data.total_amount
                    cost_tax_amount = cost_tax_amount + data.cost_tax_amount
                    cost_untaxed_amount = cost_untaxed_amount + data.cost_untaxed_amount
                    cost_total_amount = cost_total_amount + data.cost_total_amount
            rec.tax_amount = tax_amount
            rec.untaxed_amount = untaxed_amount
            rec.total_amount = total_amount
            rec.cost_tax_amount = cost_tax_amount
            rec.cost_untaxed_amount = cost_untaxed_amount
            rec.cost_total_amount = cost_total_amount

    @api.constrains('material_analysis_ids')
    def _check_cost_material_uniq_product(self):
        """Check material uniq product"""
        for record in self.material_analysis_ids:
            duplicates = self.material_analysis_ids.filtered(
                lambda r: r.id != record.id and r.product_id.id == record.product_id.id)
            if duplicates:
                raise ValidationError(_("Material already added !"))

    @api.constrains('equipment_analysis_ids')
    def _check_cost_equipment_uniq_product(self):
        """Check equipment uniq product"""
        for record in self.equipment_analysis_ids:
            duplicates = self.equipment_analysis_ids.filtered(
                lambda r: r.id != record.id and r.product_id.id == record.product_id.id)
            if duplicates:
                raise ValidationError(_("Equipment already added !"))

    @api.constrains('labour_analysis_ids')
    def _check_cost_labour_uniq_product(self):
        """Check labour uniq product"""
        for record in self.labour_analysis_ids:
            duplicates = self.labour_analysis_ids.filtered(
                lambda r: r.id != record.id and r.product_id.id == record.product_id.id)
            if duplicates:
                raise ValidationError(_("Labour already added !"))

    @api.constrains('overhead_analysis_ids')
    def _check_cost_overhead_uniq_product(self):
        """Check overhead uniq product"""
        for record in self.overhead_analysis_ids:
            duplicates = self.overhead_analysis_ids.filtered(
                lambda r: r.id != record.id and r.product_id.id == record.product_id.id)
            if duplicates:
                raise ValidationError(_("Overhead already added !"))

    @api.constrains("is_material", "is_equipment", "is_labour", "is_overhead")
    def _check_ra_template_availability(self):
        """Ensure at least one RA Template type is selected."""
        for rec in self:
            if not any([rec.is_material, rec.is_equipment, rec.is_labour, rec.is_overhead]):
                raise ValidationError(
                    _("Please select at least one: Material, Equipment, Labour, or Overhead."))

    # Onchange
    @api.onchange('ra_template_id')
    def onchange_ra_products(self):
        """onchange ra products"""
        for rec in self:
            material_lines = []
            equip_lines = []
            labour_lines = []
            overhead_lines = []
            if rec.ra_template_id.is_material:
                for data in rec.ra_template_id.material_analysis_ids:
                    material_lines.append((0, 0, {
                        'product_id': data.product_id.id,
                        'name': data.name,
                        'qty': data.qty,
                        'price': data.price,
                        'cost': data.product_id.standard_price,
                        'tax_id': data.tax_id,
                    }))
            if rec.ra_template_id.is_equipment:
                for data in rec.ra_template_id.equipment_analysis_ids:
                    equip_lines.append((0, 0, {
                        'product_id': data.product_id.id,
                        'name': data.name,
                        'qty': data.qty,
                        'price': data.price,
                        'cost': data.product_id.standard_price,
                        'tax_id': data.tax_id.id
                    }))
            if rec.ra_template_id.is_labour:
                for data in rec.ra_template_id.labour_analysis_ids:
                    labour_lines.append((0, 0, {
                        'product_id': data.product_id.id,
                        'name': data.name,
                        'qty': data.qty,
                        'price': data.price,
                        'cost': data.product_id.standard_price,
                        'tax_id': data.tax_id.id
                    }))
            if rec.ra_template_id.is_overhead:
                for data in rec.ra_template_id.overhead_analysis_ids:
                    overhead_lines.append((0, 0, {
                        'product_id': data.product_id.id,
                        'name': data.name,
                        'qty': data.qty,
                        'price': data.price,
                        'cost': data.product_id.standard_price,
                        'tax_id': data.tax_id.id
                    }))
            rec.is_material = rec.ra_template_id.is_material
            rec.is_equipment = rec.ra_template_id.is_equipment
            rec.is_labour = rec.ra_template_id.is_labour
            rec.is_overhead = rec.ra_template_id.is_overhead
            rec.unit_id = rec.ra_template_id.unit_id.id
            rec.material_analysis_ids = [(5, 0, 0)] + material_lines
            rec.equipment_analysis_ids = [(5, 0, 0)] + equip_lines
            rec.labour_analysis_ids = [(5, 0, 0)] + labour_lines
            rec.overhead_analysis_ids = [(5, 0, 0)] + overhead_lines

    @api.onchange('activity_id')
    def _onchange_activity_id(self):
        """Empty Sub Type on work Types"""
        for rec in self:
            if rec.activity_id:
                rec.sub_activity_id = False

    @api.onchange('sub_activity_id')
    def _onchange_sub_activity_id(self):
        """Empty Sub Type on work Types"""
        for rec in self:
            rec.ra_template_id = False

    @api.onchange('site_id')
    def _onchange_site_id(self):
        """Empty Sub Type on work Types"""
        for rec in self:
            if rec.site_id:
                rec.project_id = False


class RateAnalysisMaterial(models.Model):
    """Rate Analysis Material"""
    _name = "rate.analysis.material"
    _description = "Rate Analysis Material Line"

    rate_analysis_id = fields.Many2one('rate.analysis')
    product_id = fields.Many2one(
        'product.product', string="Material", domain="[('is_material','=',True)]")
    name = fields.Char(string="Description")
    code = fields.Char(related="product_id.default_code")
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id')
    qty = fields.Float(string="Qty.", default=1)
    uom_id = fields.Many2one(related="product_id.uom_po_id", string="UOM")
    tax_id = fields.Many2one('account.tax', string="Tax")
    untaxed_amount = fields.Monetary(compute="_compute_total")
    tax_amount = fields.Monetary(compute="_compute_total")
    total_amount = fields.Monetary(compute="_compute_total")
    cost = fields.Monetary(string="Cost Price")
    price = fields.Monetary(string="Sale Price")
    cost_untaxed_amount = fields.Monetary(
        string="Untaxed Amount(Cost)", compute="_compute_total")
    cost_tax_amount = fields.Monetary(
        string="Tax Amount(Cost)", compute="_compute_total")
    cost_total_amount = fields.Monetary(
        string="Total Amount(Cost)", compute="_compute_total")

    @api.onchange('product_id')
    def onchange_product_info(self):
        """Product Info"""
        for rec in self:
            if rec.product_id:
                rec.name = rec.product_id.name
                rec.price = rec.product_id.lst_price
                rec.cost = rec.product_id.standard_price

    @api.depends('price', 'qty', 'tax_id.amount', 'tax_id', 'cost')
    def _compute_total(self):
        """Compute Total"""
        for rec in self:
            # Sale
            untaxed_amount = rec.qty * rec.price
            tax_amount = (rec.tax_id.amount * untaxed_amount /
                          100) if rec.tax_id else 0.0
            total_amount = untaxed_amount + tax_amount
            rec.untaxed_amount = untaxed_amount
            rec.tax_amount = tax_amount
            rec.total_amount = total_amount
            # Cost
            cost_untaxed_amount = rec.qty * rec.cost
            cost_tax_amount = (rec.tax_id.amount *
                               cost_untaxed_amount / 100) if rec.tax_id else 0.0
            cost_total_amount = cost_untaxed_amount + cost_tax_amount
            rec.cost_untaxed_amount = cost_untaxed_amount
            rec.cost_tax_amount = cost_tax_amount
            rec.cost_total_amount = cost_total_amount


class RateAnalysisEquipment(models.Model):
    """Rate Analysis Equipment"""
    _name = "rate.analysis.equipment"
    _description = "Rate Analysis Equipment Line"

    rate_analysis_id = fields.Many2one('rate.analysis')
    product_id = fields.Many2one(
        'product.product', string="Equipment", domain="[('is_equipment','=',True)]")
    name = fields.Char(string="Description")
    code = fields.Char(related="product_id.default_code")
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id')
    qty = fields.Float(string="Qty.", default=1)
    uom_id = fields.Many2one(related="product_id.uom_po_id", string="UOM")
    tax_id = fields.Many2one('account.tax', string="Tax")
    untaxed_amount = fields.Monetary(compute="_compute_total")
    tax_amount = fields.Monetary(compute="_compute_total")
    total_amount = fields.Monetary(compute="_compute_total")
    cost = fields.Monetary(string="Cost Price")
    price = fields.Monetary(string="Sale Price")
    cost_untaxed_amount = fields.Monetary(
        string="Untaxed Amount(Cost)", compute="_compute_total")
    cost_tax_amount = fields.Monetary(
        string="Tax Amount(Cost)", compute="_compute_total")
    cost_total_amount = fields.Monetary(
        string="Total Amount(Cost)", compute="_compute_total")

    @api.onchange('product_id')
    def onchange_product_info(self):
        """Product Info"""
        for rec in self:
            if rec.product_id:
                rec.name = rec.product_id.name
                rec.price = rec.product_id.lst_price
                rec.cost = rec.product_id.standard_price

    @api.depends('price', 'qty', 'tax_id.amount', 'tax_id', 'cost')
    def _compute_total(self):
        """Compute Total"""
        for rec in self:
            # Sale
            untaxed_amount = rec.qty * rec.price
            tax_amount = (rec.tax_id.amount * untaxed_amount /
                          100) if rec.tax_id else 0.0
            total_amount = untaxed_amount + tax_amount
            rec.untaxed_amount = untaxed_amount
            rec.tax_amount = tax_amount
            rec.total_amount = total_amount
            # Cost
            cost_untaxed_amount = rec.qty * rec.cost
            cost_tax_amount = (rec.tax_id.amount *
                               cost_untaxed_amount / 100) if rec.tax_id else 0.0
            cost_total_amount = cost_untaxed_amount + cost_tax_amount
            rec.cost_untaxed_amount = cost_untaxed_amount
            rec.cost_tax_amount = cost_tax_amount
            rec.cost_total_amount = cost_total_amount


class RateAnalysisLabour(models.Model):
    """Rate Analysis Labour"""
    _name = "rate.analysis.labour"
    _description = "Rate Analysis Labour Line"

    rate_analysis_id = fields.Many2one('rate.analysis')
    product_id = fields.Many2one('product.product', string="Labour",
                                 domain="[('is_labour','=',True)]")
    name = fields.Char(string="Description")
    code = fields.Char(related="product_id.default_code")
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id')
    qty = fields.Float(string="Qty.", default=1)
    uom_id = fields.Many2one(related="product_id.uom_po_id", string="UOM")
    tax_id = fields.Many2one('account.tax', string="Tax")
    untaxed_amount = fields.Monetary(compute="_compute_total")
    tax_amount = fields.Monetary(compute="_compute_total")
    total_amount = fields.Monetary(compute="_compute_total")
    cost = fields.Monetary(string="Cost Price")
    price = fields.Monetary(string="Sale Price")
    cost_untaxed_amount = fields.Monetary(
        string="Untaxed Amount(Cost)", compute="_compute_total")
    cost_tax_amount = fields.Monetary(
        string="Tax Amount(Cost)", compute="_compute_total")
    cost_total_amount = fields.Monetary(
        string="Total Amount(Cost)", compute="_compute_total")

    @api.onchange('product_id')
    def onchange_product_info(self):
        """Product Info"""
        for rec in self:
            if rec.product_id:
                rec.name = rec.product_id.name
                rec.price = rec.product_id.lst_price
                rec.cost = rec.product_id.standard_price

    @api.depends('price', 'qty', 'tax_id.amount', 'tax_id', 'cost')
    def _compute_total(self):
        """Compute Total"""
        for rec in self:
            # Sale
            untaxed_amount = rec.qty * rec.price
            tax_amount = (rec.tax_id.amount * untaxed_amount /
                          100) if rec.tax_id else 0.0
            total_amount = untaxed_amount + tax_amount
            rec.untaxed_amount = untaxed_amount
            rec.tax_amount = tax_amount
            rec.total_amount = total_amount
            # Cost
            cost_untaxed_amount = rec.qty * rec.cost
            cost_tax_amount = (rec.tax_id.amount *
                               cost_untaxed_amount / 100) if rec.tax_id else 0.0
            cost_total_amount = cost_untaxed_amount + cost_tax_amount
            rec.cost_untaxed_amount = cost_untaxed_amount
            rec.cost_tax_amount = cost_tax_amount
            rec.cost_total_amount = cost_total_amount


class RateAnalysisOverhead(models.Model):
    """Rate Analysis Overhead"""
    _name = "rate.analysis.overhead"
    _description = "Rate Analysis Overhead Line"

    rate_analysis_id = fields.Many2one('rate.analysis', string="Rate Analysis")
    product_id = fields.Many2one(
        'product.product', string="Overhead", domain="[('is_overhead','=',True)]")
    name = fields.Char(string="Description")
    code = fields.Char(related="product_id.default_code")
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id')
    qty = fields.Float(string="Qty.", default=1)
    uom_id = fields.Many2one(related="product_id.uom_po_id", string="UOM")
    tax_id = fields.Many2one('account.tax', string="Tax")
    untaxed_amount = fields.Monetary(compute="_compute_total")
    tax_amount = fields.Monetary(compute="_compute_total")
    total_amount = fields.Monetary(
        compute="_compute_total")
    cost = fields.Monetary(string="Cost Price")
    price = fields.Monetary(string="Sale Price")
    cost_untaxed_amount = fields.Monetary(
        string="Untaxed Amount(Cost)", compute="_compute_total")
    cost_tax_amount = fields.Monetary(
        string="Tax Amount(Cost)", compute="_compute_total")
    cost_total_amount = fields.Monetary(
        string="Total Amount(Cost)", compute="_compute_total")

    @api.onchange('product_id')
    def onchange_product_info(self):
        """Product Info"""
        for rec in self:
            if rec.product_id:
                rec.name = rec.product_id.name
                rec.price = rec.product_id.lst_price
                rec.cost = rec.product_id.standard_price

    @api.depends('price', 'qty', 'tax_id.amount', 'tax_id', 'cost')
    def _compute_total(self):
        """Compute Total"""
        for rec in self:
            # Sale
            untaxed_amount = rec.qty * rec.price
            tax_amount = (rec.tax_id.amount * untaxed_amount /
                          100) if rec.tax_id else 0.0
            total_amount = untaxed_amount + tax_amount
            rec.untaxed_amount = untaxed_amount
            rec.tax_amount = tax_amount
            rec.total_amount = total_amount
            # Cost
            cost_untaxed_amount = rec.qty * rec.cost
            cost_tax_amount = (rec.tax_id.amount *
                               cost_untaxed_amount / 100) if rec.tax_id else 0.0
            cost_total_amount = cost_untaxed_amount + cost_tax_amount
            rec.cost_untaxed_amount = cost_untaxed_amount
            rec.cost_tax_amount = cost_tax_amount
            rec.cost_total_amount = cost_total_amount


# Rate Analysis Template
class RateAnalysisTemplate(models.Model):
    """Rate Anaysis Template"""
    _name = 'ra.template'
    _description = "Rate Analysis Template"

    name = fields.Char(string="Title")
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id')
    activity_id = fields.Many2one('job.type', string="Work Type")
    sub_activity_ids = fields.Many2many(
        related="activity_id.sub_category_ids", string="Sub Activities")
    sub_activity_id = fields.Many2one('job.sub.category', string="Work Sub Type",
                                      domain="[('id','in',sub_activity_ids)]")
    unit_id = fields.Many2one('uom.uom', string="Unit")

    # Lines
    is_material = fields.Boolean(string="Material", default=True)
    is_equipment = fields.Boolean(string="Equipment", default=True)
    is_labour = fields.Boolean(string="Labour", default=True)
    is_overhead = fields.Boolean(string="Overhead", default=True)
    material_analysis_ids = fields.One2many('ra.material.template',
                                            'rate_analysis_id',
                                            string="Rate Analysis Material")
    equipment_analysis_ids = fields.One2many('ra.equipment.template',
                                             'rate_analysis_id',
                                             string="Rate Analysis Equipment")
    labour_analysis_ids = fields.One2many('ra.labour.template',
                                          'rate_analysis_id',
                                          string="Rate Analysis Labour")
    overhead_analysis_ids = fields.One2many('ra.overhead.template',
                                            'rate_analysis_id',
                                            string="Rate Analysis Overhead")

    # Amount
    tax_amount = fields.Monetary(
        compute="_compute_total_amount")
    untaxed_amount = fields.Monetary(compute="_compute_total_amount")
    total_amount = fields.Monetary(
        compute="_compute_total_amount")

    @api.model_create_multi
    def create(self, vals_list):
        """Create"""
        res = super().create(vals_list)
        for vals in vals_list:
            if vals.get('is_material') and not vals.get('material_analysis_ids'):
                raise ValidationError(_("Please add material !"))
            if vals.get('is_equipment') and not vals.get('equipment_analysis_ids'):
                raise ValidationError(_("Please add equipment !"))
            if vals.get('is_labour') and not vals.get('labour_analysis_ids'):
                raise ValidationError(_("Please add labour !"))
            if vals.get('is_overhead') and not vals.get('overhead_analysis_ids'):
                raise ValidationError(_("Please add overhead !"))
        return res

    def write(self, vals):
        """Write"""
        res = super().write(vals)
        if self.is_material and not self.material_analysis_ids:
            raise ValidationError(_("Please add material !"))
        if self.is_equipment and not self.equipment_analysis_ids:
            raise ValidationError(_("Please add equipment !"))
        if self.is_labour and not self.labour_analysis_ids:
            raise ValidationError(_("Please add labour !"))
        if self.is_overhead and not self.overhead_analysis_ids:
            raise ValidationError(_("Please add overhead !"))
        return res

    @api.depends('material_analysis_ids',
                 'equipment_analysis_ids',
                 'labour_analysis_ids',
                 'overhead_analysis_ids',
                 'is_material',
                 'is_equipment',
                 'is_labour',
                 'is_overhead')
    def _compute_total_amount(self):
        """Compute Total Amount"""
        for rec in self:
            tax_amount = 0.0
            untaxed_amount = 0.0
            total_amount = 0.0
            if rec.is_material:
                for data in rec.material_analysis_ids:
                    tax_amount = tax_amount + data.tax_amount
                    untaxed_amount = untaxed_amount + data.untaxed_amount
                    total_amount = total_amount + data.total_amount
            if rec.is_equipment:
                for data in rec.equipment_analysis_ids:
                    tax_amount = tax_amount + data.tax_amount
                    untaxed_amount = untaxed_amount + data.untaxed_amount
                    total_amount = total_amount + data.total_amount
            if rec.is_labour:
                for data in rec.labour_analysis_ids:
                    tax_amount = tax_amount + data.tax_amount
                    untaxed_amount = untaxed_amount + data.untaxed_amount
                    total_amount = total_amount + data.total_amount
            if rec.is_overhead:
                for data in rec.overhead_analysis_ids:
                    tax_amount = tax_amount + data.tax_amount
                    untaxed_amount = untaxed_amount + data.untaxed_amount
                    total_amount = total_amount + data.total_amount
            rec.tax_amount = tax_amount
            rec.untaxed_amount = untaxed_amount
            rec.total_amount = total_amount

    # Constrain
    @api.constrains('material_analysis_ids')
    def _check_cost_material_uniq_product_template(self):
        """Check Cost Material Uniq Product"""
        for record in self.material_analysis_ids:
            duplicates = self.material_analysis_ids.filtered(
                lambda r: r.id != record.id and r.product_id.id == record.product_id.id)
            if duplicates:
                raise ValidationError(_("Material already added !"))

    @api.constrains('equipment_analysis_ids')
    def _check_cost_equipment_uniq_product_template(self):
        """Check Cost Equipment Uniq Product"""
        for record in self.equipment_analysis_ids:
            duplicates = self.equipment_analysis_ids.filtered(
                lambda r: r.id != record.id and r.product_id.id == record.product_id.id)
            if duplicates:
                raise ValidationError(_("Equipment already added !"))

    @api.constrains('labour_analysis_ids')
    def _check_cost_labour_uniq_product_template(self):
        """Check Cost Labour Uniq Product"""
        for record in self.labour_analysis_ids:
            duplicates = self.labour_analysis_ids.filtered(
                lambda r: r.id != record.id and r.product_id.id == record.product_id.id)
            if duplicates:
                raise ValidationError(_("Labour already added !"))

    @api.constrains('overhead_analysis_ids')
    def _check_cost_overhead_uniq_product_template(self):
        """Check Cost Overhead Uniq Product"""
        for record in self.overhead_analysis_ids:
            duplicates = self.overhead_analysis_ids.filtered(
                lambda r: r.id != record.id and r.product_id.id == record.product_id.id)
            if duplicates:
                raise ValidationError(_("Overhead already added !"))

    @api.constrains("is_material", "is_equipment", "is_labour", "is_overhead")
    def _check_ra_template_availability(self):
        """Ensure at least one RA Template type is selected."""
        for rec in self:
            if not any([rec.is_material, rec.is_equipment, rec.is_labour, rec.is_overhead]):
                raise ValidationError(
                    _("Please select at least one: Material, Equipment, Labour, or Overhead."))

    @api.onchange('activity_id')
    def _onchange_activity_id(self):
        """Empty Sub Type on work Types"""
        for rec in self:
            if rec.activity_id:
                rec.sub_activity_id = False


class RaMaterialTemplate(models.Model):
    """Rate Analysis Material Template"""
    _name = "ra.material.template"
    _description = "Rate Analysis Template Material Line"

    rate_analysis_id = fields.Many2one(
        'ra.template', string="Rate Analysis Template")
    product_id = fields.Many2one(
        'product.product', string="Material", domain="[('is_material','=',True)]")
    name = fields.Char(string="Description")
    code = fields.Char(related="product_id.default_code")
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id')
    qty = fields.Float(string="Qty.", default=1)
    uom_id = fields.Many2one(related="product_id.uom_po_id", string="UOM")
    price = fields.Monetary(string="Sale Price")
    tax_id = fields.Many2one('account.tax', string="Tax")
    untaxed_amount = fields.Monetary(compute="_compute_total")
    tax_amount = fields.Monetary(compute="_compute_total")
    total_amount = fields.Monetary(
        compute="_compute_total")

    @api.onchange('product_id')
    def onchange_product_info(self):
        """Product Info"""
        for rec in self:
            if rec.product_id:
                rec.name = rec.product_id.name
                rec.price = rec.product_id.lst_price

    @api.depends('price', 'qty', 'tax_id.amount', 'tax_id')
    def _compute_total(self):
        """Compute Total"""
        for rec in self:
            untaxed_amount = rec.qty * rec.price
            tax_amount = (rec.tax_id.amount * untaxed_amount /
                          100) if rec.tax_id else 0.0
            total_amount = untaxed_amount + tax_amount
            rec.untaxed_amount = untaxed_amount
            rec.tax_amount = tax_amount
            rec.total_amount = total_amount


class RaEquipmentTemplate(models.Model):
    """Rate Analysis Equipment Template"""
    _name = "ra.equipment.template"
    _description = "Rate Analysis Template Equipment Line"

    rate_analysis_id = fields.Many2one(
        'ra.template', string="Rate Analysis Template")
    product_id = fields.Many2one(
        'product.product', string="Equipment", domain="[('is_equipment','=',True)]")
    name = fields.Char(string="Description")
    code = fields.Char(related="product_id.default_code")
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id')
    qty = fields.Float(string="Qty.", default=1)
    uom_id = fields.Many2one(related="product_id.uom_po_id", string="UOM")
    price = fields.Monetary(string="Sale Price")
    tax_id = fields.Many2one('account.tax', string="Tax")
    untaxed_amount = fields.Monetary(compute="_compute_total")
    tax_amount = fields.Monetary(compute="_compute_total")
    total_amount = fields.Monetary(
        compute="_compute_total")

    @api.onchange('product_id')
    def onchange_product_info(self):
        """Product Info"""
        for rec in self:
            if rec.product_id:
                rec.name = rec.product_id.name
                rec.price = rec.product_id.lst_price

    @api.depends('price', 'qty', 'tax_id.amount', 'tax_id')
    def _compute_total(self):
        """Compute Total"""
        for rec in self:
            untaxed_amount = rec.qty * rec.price
            tax_amount = (rec.tax_id.amount * untaxed_amount /
                          100) if rec.tax_id else 0.0
            total_amount = untaxed_amount + tax_amount
            rec.untaxed_amount = untaxed_amount
            rec.tax_amount = tax_amount
            rec.total_amount = total_amount


class RaLabourTemplate(models.Model):
    """Rate Analysis Labour Template"""
    _name = "ra.labour.template"
    _description = "Rate Analysis Template Labour Line"

    rate_analysis_id = fields.Many2one(
        'ra.template', string="Rate Analysis Template")
    product_id = fields.Many2one(
        'product.product', string="Labour", domain="[('is_labour','=',True)]")
    name = fields.Char(string="Description")
    code = fields.Char(related="product_id.default_code")
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id')
    qty = fields.Float(string="Qty.", default=1)
    uom_id = fields.Many2one(related="product_id.uom_po_id", string="UOM")
    price = fields.Monetary(string="Sale Price")
    tax_id = fields.Many2one('account.tax', string="Tax")
    untaxed_amount = fields.Monetary(compute="_compute_total")
    tax_amount = fields.Monetary(compute="_compute_total")
    total_amount = fields.Monetary(
        compute="_compute_total")

    @api.onchange('product_id')
    def onchange_product_info(self):
        """Product Info"""
        for rec in self:
            if rec.product_id:
                rec.name = rec.product_id.name
                rec.price = rec.product_id.lst_price

    @api.depends('price', 'qty', 'tax_id.amount', 'tax_id')
    def _compute_total(self):
        """Compute Total"""
        for rec in self:
            untaxed_amount = rec.qty * rec.price
            tax_amount = (rec.tax_id.amount * untaxed_amount /
                          100) if rec.tax_id else 0.0
            total_amount = untaxed_amount + tax_amount
            rec.untaxed_amount = untaxed_amount
            rec.tax_amount = tax_amount
            rec.total_amount = total_amount


class RaOverheadTemplate(models.Model):
    """Rate analysis overhead template"""
    _name = "ra.overhead.template"
    _description = "Rate Analysis Template Overhead Line"

    rate_analysis_id = fields.Many2one(
        'ra.template', string="Rate Analysis Template")
    product_id = fields.Many2one(
        'product.product', string="Overhead", domain="[('is_overhead','=',True)]")
    name = fields.Char(string="Description")
    code = fields.Char(related="product_id.default_code")
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id')
    qty = fields.Float(string="Qty.", default=1)
    uom_id = fields.Many2one(related="product_id.uom_po_id", string="UOM")
    price = fields.Monetary(string="Sale Price")
    tax_id = fields.Many2one('account.tax', string="Tax")
    untaxed_amount = fields.Monetary(compute="_compute_total")
    tax_amount = fields.Monetary(compute="_compute_total")
    total_amount = fields.Monetary(
        compute="_compute_total")

    @api.onchange('product_id')
    def onchange_product_info(self):
        """Product Info"""
        for rec in self:
            if rec.product_id:
                rec.name = rec.product_id.name
                rec.price = rec.product_id.lst_price

    @api.depends('price', 'qty', 'tax_id.amount', 'tax_id')
    def _compute_total(self):
        """Compute Total"""
        for rec in self:
            untaxed_amount = rec.qty * rec.price
            tax_amount = (rec.tax_id.amount * untaxed_amount /
                          100) if rec.tax_id else 0.0
            total_amount = untaxed_amount + tax_amount
            rec.untaxed_amount = untaxed_amount
            rec.tax_amount = tax_amount
            rec.total_amount = total_amount


class RAEmployeeHours(models.Model):
    """Rate Analysis Employee Hours"""
    _name = 'ra.employee.hours'
    _description = "RA Employee Hours"

    rate_analysis_id = fields.Many2one(
        comodel_name='rate.analysis', string="Rate Analysis")
    employee_id = fields.Many2one(comodel_name='hr.employee')
    date = fields.Date(default=fields.Date.today())
    sub_project_id = fields.Many2one(related="rate_analysis_id.project_id")
    phase_id = fields.Many2one(
        comodel_name='job.costing', domain="[('project_id','=',sub_project_id)]")
    work_order_id = fields.Many2one(
        comodel_name='job.order', domain="[('job_sheet_id','=',phase_id)]")
    hours = fields.Float(string="Worked Hours")
