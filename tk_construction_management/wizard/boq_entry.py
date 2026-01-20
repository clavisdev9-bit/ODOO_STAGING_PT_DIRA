# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.

from markupsafe import Markup
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class BOQBudgetEntry(models.TransientModel):
    """BOQ Budget Entry"""
    _name = 'boq.budget.entry'
    _description = "Change BOQ Budget Entry"

    subproject_id = fields.Many2one(
        'tk.construction.project', string="Construction Project")
    type = fields.Selection([('insert', 'Insert BOQ Line'),
                             ('update', 'Update BOQ Line Qty'),
                             ('remove', 'Remove BOQ Line')],
                            default='insert', string="Action Type")
    # Operation
    is_use_measure = fields.Boolean(related="subproject_id.is_use_measure")
    boq_budget_line_id = fields.Many2one(
        'boq.budget', string="BOQ Line", domain="[('project_id','=',subproject_id)]")
    work_type_id = fields.Many2one('job.type', string="Work Type")
    work_subtype_ids = fields.Many2many(
        related="work_type_id.sub_category_ids", string="Sub Activities")
    work_subtype_id = fields.Many2one('job.sub.category', string="Work Sub Type",
                                      domain="[('id','in',work_subtype_ids)]")
    qty = fields.Float(string="Qty.", default=1.0)
    length = fields.Float()
    width = fields.Float()
    height = fields.Float()
    total_qty = fields.Float(string="Total Qty.",
                             compute="_compute_total_qty", store=True)
    pending_confirmation_ids = fields.Many2many(comodel_name="budget.line.confirmation",
                                                compute="_compute_pending_confirmation_ids")

    @api.depends('is_use_measure', 'length', 'width', 'height', 'qty')
    def _compute_total_qty(self):
        """Compute total qty"""
        for rec in self:
            if rec.is_use_measure:
                total_qty = rec.height * rec.width * rec.length * rec.qty
            else:
                total_qty = rec.qty
            rec.total_qty = total_qty

    @api.constrains('length', 'width', 'height', 'qty', 'is_use_measure')
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

    @api.model
    def default_get(self, fields_list):
        """Default get"""
        res = super().default_get(fields_list)
        res['subproject_id'] = self._context.get('active_id')
        return res

    @api.onchange('boq_budget_line_id', 'type')
    def onchange_type_boq_line(self):
        """onchange boq lines"""
        for rec in self:
            if rec.type in ['update', 'remove'] and rec.boq_budget_line_id:
                rec.work_type_id = rec.boq_budget_line_id.activity_id.id
                rec.work_subtype_id = rec.boq_budget_line_id.sub_activity_id.id
                rec.qty = rec.boq_budget_line_id.qty
                rec.length = rec.boq_budget_line_id.length
                rec.height = rec.boq_budget_line_id.height
                rec.width = rec.boq_budget_line_id.width
            else:
                rec.work_type_id = False
                rec.work_subtype_id = False
                rec.qty = False
                rec.length = False
                rec.height = False
                rec.width = False

    @api.onchange("type")
    def _onchange_boq_budget_line_id(self):
        """Remove Value if  budget line changed"""
        for rec in self:
            if rec.type == 'insert':
                rec.boq_budget_line_id = False

    @api.depends("boq_budget_line_id")
    def _compute_pending_confirmation_ids(self):
        """Pending Confirmation Lines"""
        for rec in self:
            pending_confirmation_ids = []
            pending_confirmation_lines = self.env['budget.line.confirmation'].sudo().search(
                [('boq_budget_line_id', '!=', False),
                 ('boq_budget_line_id', '=', rec.boq_budget_line_id.id),
                 ('status', '=', 'requested')])
            if pending_confirmation_lines:
                pending_confirmation_ids = pending_confirmation_lines.ids
            rec.pending_confirmation_ids = [(6, 0, pending_confirmation_ids)]

    @api.onchange('work_type_id', 'type')
    def _onchange_work_subtype_id(self):
        """Empty Sub Type on work Types"""
        for rec in self:
            if rec.work_type_id and rec.type == 'insert':
                rec.work_subtype_id = False

    def action_update_boq_lines(self):
        """Update Boq lines"""
        if self.type == 'insert':
            existing_boq_lines = self.subproject_id.budget_id.budget_line_ids.filtered(
                lambda line: line.job_type_id.id == self.work_type_id.id
                             and line.sub_category_id.id == self.work_subtype_id.id
            )
            if existing_boq_lines:
                raise ValidationError(_(
                    "A line with work type '%s' and subtype '%s' already exists."
                ) % (self.work_type_id.name, self.work_subtype_id.name))

        budget_line_confirmation_id = self.env['budget.line.confirmation'].create({
            'budget_id': self.subproject_id.budget_id.id,
            'type': self.type,
            'date': fields.Date.today(),
            'is_use_measure': self.is_use_measure,
            'boq_budget_line_id': self.boq_budget_line_id.id,
            'work_type_id': self.work_type_id.id,
            'work_subtype_id': self.work_subtype_id.id,
            'qty': self.qty,
            'length': self.length,
            'width': self.width,
            'height': self.height,
            'total_qty': self.total_qty,
            'old_qty': self.boq_budget_line_id.qty,
            'old_length': self.boq_budget_line_id.length,
            'old_width': self.boq_budget_line_id.width,
            'old_height': self.boq_budget_line_id.height,
            'old_total_qty': self.boq_budget_line_id.total_qty,
        })
        type = {
            'insert': 'Insert BOQ Line',
            'update': 'Update BOQ Line',
            'remove': 'Remove BOQ Line',
        }
        body = f"""New Request - <strong>{type.get(self.type)}</strong><br/>
                Date : <strong>{fields.Date.today()}</strong>"""
        budget_line_confirmation_id.budget_id.message_post(body=Markup(
            body), partner_ids=[self.subproject_id.budget_id.responsible_id.partner_id.id])
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'type': 'info',
                'title': _("Your requested has been submitted."),
                'sticky': False,
                'next': {
                    'type': 'ir.actions.client',
                    'tag': 'reload',
                },

            }
        }
