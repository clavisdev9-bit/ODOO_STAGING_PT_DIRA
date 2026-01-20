# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
from odoo import fields, api, models, _
from odoo.exceptions import ValidationError


def is_float(str_vals):
    """Check if string is Float or not
    :param str_vals: String
    :return: True if string is Float or not
    """
    vals = str_vals.replace("-", "").replace(".", "").isnumeric()
    return bool(vals)


class ConstructionSite(models.Model):
    """Construction Site / Project"""
    _name = 'tk.construction.site'
    _description = "Construction Project"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    active = fields.Boolean(default=True)
    name = fields.Char(tracking=True)
    start_date = fields.Date(tracking=True)
    end_date = fields.Date(tracking=True)
    status = fields.Selection([('draft', 'Draft'), ('in_progress', 'In Progress'),
                               ('complete', 'Completed')],
                              default='draft', tracking=True)
    con_project_id = fields.Many2one(
        'tk.construction.project', string="Project", tracking=True)
    phone = fields.Char()
    mobile = fields.Char()
    email = fields.Char()
    warehouse_id = fields.Many2one(
        'stock.warehouse', string="Warehouse", tracking=True)

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

    # One2Many
    stakeholder_ids = fields.One2many('stakeholder.line', 'site_id')
    site_image_ids = fields.One2many('site.images', 'site_id')
    site_dimension_ids = fields.One2many('site.dimension', 'site_id')
    document_permit_ids = fields.One2many('document.permit', 'site_id')
    construction_project_ids = fields.One2many(
        'tk.construction.project', 'construction_site_id')
    boq_ids = fields.One2many(
        'tk.construction.project', 'construction_site_id')

    # Count & Totals
    document_count = fields.Integer(compute="_compute_count")
    project_count = fields.Integer(compute="_compute_count")
    invoice_count = fields.Integer(compute="_compute_count")
    total_area = fields.Float(compute="_compute_total_area")

    # Company
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company)

    # Create, Write, Unlink, Constrain
    @api.constrains('stakeholder_ids')
    def _check_stakeholder_stack(self):
        """Check stakeholder Stack"""
        for record in self.stakeholder_ids:
            duplicates = self.stakeholder_ids.filtered(
                lambda r: r.id != record.id and r.stakeholder_id.id == record.stakeholder_id.id)
            if duplicates:
                raise ValidationError(_("Stakeholder already added !"))

    @api.ondelete(at_uninstall=False)
    def _unlink_construction_site(self):
        for rec in self:
            if rec.construction_project_ids:
                raise ValidationError(
                    _("Sub Projects are created please delete it first."))

    @api.constrains('stakeholder_ids')
    def _check_stakeholder_ids(self):
        """Stakeholder stake"""
        percentage = 0.0
        for record in self.stakeholder_ids:
            percentage = percentage + record.percentage
        if percentage > 100:
            raise ValidationError(
                _("Percentage cannot exceed the limit of 100%."))

    # Compute
    def _compute_count(self):
        """Compute Smart button count"""
        for rec in self:
            rec.document_count = self.env['site.documents'].search_count(
                [('site_id', '=', rec.id)])
            rec.project_count = self.env['tk.construction.project'].search_count(
                [('construction_site_id', '=', rec.id)])
            projects = self.env['tk.construction.project'].search(
                [('construction_site_id', '=', rec.id)]).mapped('id')
            rec.invoice_count = self.env['progress.billing'].search_count(
                [('project_id', 'in', projects)])

    @api.depends('site_dimension_ids')
    def _compute_total_area(self):
        """Compute total area"""
        for rec in self:
            total = 0.0
            if rec.site_dimension_ids:
                for data in rec.site_dimension_ids:
                    total = total + data.area
            rec.total_area = total

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

    @api.onchange('start_date', 'end_date')
    def _onchange_start_date(self):
        """Add Validation on latitude and longitude"""
        for rec in self:
            if rec.start_date and rec.end_date and rec.end_date <= rec.start_date:
                raise ValidationError(
                    _("End date should be greater than start date."))

    # Smart Bottom
    def action_gmap_location(self):
        """Action Gmap Location"""
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

    def action_site_document(self):
        """View site document"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Documents'),
            'res_model': 'site.documents',
            'domain': [('site_id', '=', self.id)],
            'context': {'default_site_id': self.id, 'create': False},
            'view_mode': 'list',
            'target': 'current'
        }

    def action_view_invoice(self):
        """View invoices"""
        projects = self.env['tk.construction.project'].search(
            [('construction_site_id', '=', self.id)]).mapped('id')
        return {
            'type': 'ir.actions.act_window',
            'name': _('Progress Billing'),
            'res_model': 'progress.billing',
            'domain': [('project_id', 'in', projects)],
            'context': {'group_by': 'project_id', 'create': False},
            'view_mode': 'list,form',
            'target': 'current'
        }

    def action_view_project(self):
        """View project"""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Project'),
            'res_model': 'tk.construction.project',
            'domain': [('construction_site_id', '=', self.id)],
            'context': {'default_construction_site_id': self.id, 'create': False},
            'view_mode': 'list,form',
            'target': 'current'
        }

    # Button
    def action_site_complete(self):
        """Status : complete"""
        if not self.construction_project_ids:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'info',
                    'message': _("Please create at least one sub project !."),
                    'sticky': False,
                }
            }
        is_handover_pending = False
        for data in self.construction_project_ids:
            if not data.stage == 'Handover':
                is_handover_pending = True
                break
        if is_handover_pending:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'warning',
                    'message': _("Some sub project is not handover yet please handover to "
                                 "complete project."),
                    'sticky': False,
                }
            }
        self.status = 'complete'

    def action_site_in_progress(self):
        """Status : in_progress"""
        self.status = 'in_progress'

    def action_view_gantt(self):
        self.ensure_one()
        return {
            'name': "Project Gantt",
            'type': 'ir.actions.client',
            'target': 'current',
            'tag': 'project_gantt',
            'context': {
                'id': self.id,
            },
        }


# Stakeholder
class StakeholderLine(models.Model):
    """Stakeholder Line"""
    _name = 'stakeholder.line'
    _description = "Stack Holder Line"
    _rec_name = 'stakeholder_id'

    site_id = fields.Many2one('tk.construction.site',
                              string="Construction Project")
    stakeholder_id = fields.Many2one(
        'res.partner', domain="[('stack_holder','=',True)]")
    percentage = fields.Float()
    image_1920 = fields.Binary(related="stakeholder_id.image_1920")
    phone = fields.Char(related="stakeholder_id.phone")
    email = fields.Char(related="stakeholder_id.email")

    @api.constrains('percentage')
    def _check_stakeholder_ids(self):
        """Check Stack Holder Line"""
        for rec in self:
            if rec.percentage <= 0:
                raise ValidationError(
                    _("Percentage cannot zero or negative !"))


# Project Documents
class SiteDocuments(models.Model):
    """Site Documents"""
    _name = 'site.documents'
    _description = "Project Documents"
    _rec_name = 'document_type_id'

    document_type_id = fields.Many2one(
        'site.document.type', string="Document Type")
    date = fields.Date(default=fields.Date.today())
    site_id = fields.Many2one('tk.construction.site',
                              string="Construction Project", ondelete='cascade')
    document = fields.Binary(required=True)
    file_name = fields.Char()


# Project Images
class SiteImages(models.Model):
    """Site Images"""
    _name = 'site.images'
    _description = "Project Images"

    site_id = fields.Many2one('tk.construction.site',
                              string="Construction Project", ondelete='cascade')
    name = fields.Char(string='Title')
    image = fields.Image(string='Images')


# Project Dimension
class SiteDimension(models.Model):
    """Site Dimension"""
    _name = 'site.dimension'
    _description = "Project Dimension"
    _rec_name = "site_id"

    name = fields.Char(string="Title")
    site_id = fields.Many2one('tk.construction.site',
                              string="Construction Project", ondelete='cascade')
    length = fields.Float(string="Length(m)")
    width = fields.Float(string="Width(m)")
    area = fields.Float(compute="_compute_area")

    @api.depends('length', 'width')
    def _compute_area(self):
        """Compute area"""
        for rec in self:
            area = 0.0
            if rec.length and rec.width:
                area = rec.length * rec.width
            rec.area = area


# Document Permit
class DocumentPermit(models.Model):
    """Document Permit"""
    _name = 'document.permit'
    _description = "Document Permit"
    _rec_name = 'document_type_id'

    document_type_id = fields.Many2one(
        'site.document.type')
    date = fields.Date(default=fields.Date.today())
    site_id = fields.Many2one('tk.construction.site',
                              string="Construction Project", ondelete='cascade')
    document = fields.Binary(string='Documents', required=True)
    file_name = fields.Char()
    status = fields.Selection(
        [('a', 'Approved'), ('r', 'Rejected')])
    feedback = fields.Char()
    submitted_by = fields.Many2one(
        'res.users',
        default=lambda self: self.env.user and self.env.user.id or False)

    def action_approve(self):
        """Action document approve"""
        self.status = 'a'

    def action_reject(self):
        """Action document reject"""
        self.status = 'r'
