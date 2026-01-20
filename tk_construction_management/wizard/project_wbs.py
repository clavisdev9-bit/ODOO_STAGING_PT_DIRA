from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ProjectWBS(models.TransientModel):
    """Project WBS"""
    _name = 'project.wbs'
    _description = "Sub Project WBS"

    name = fields.Char(string="Title")
    work_type_ids = fields.Many2many(
        'job.type', string="Work Type Jobs", compute="_compute_work_type_ids")
    activity_id = fields.Many2one(
        'job.type', string="Work Type", domain="[('id','in',work_type_ids)]")
    start_date = fields.Date()
    end_date = fields.Date()
    sub_project_id = fields.Many2one(
        'tk.construction.project')
    project_start_date = fields.Date(
        related="sub_project_id.start_date", store=True)
    project_end_date = fields.Date(
        related="sub_project_id.end_date", store=True)

    is_any_pending_ra = fields.Boolean(compute="_compute_is_any_pending_ra")

    @api.model
    def default_get(self, fields_list):
        """Default get"""
        res = super().default_get(fields_list)
        active_id = self._context.get('active_id')
        res['sub_project_id'] = active_id
        return res

    def action_create_project_phase(self):
        """Create Project Phase"""
        active_id = self._context.get('active_id')
        sub_project_id = self.env['tk.construction.project'].browse(active_id)
        phase_id = self.env['job.costing'].create({
            'title': self.name,
            'activity_id': self.activity_id.id,
            'start_date': self.start_date,
            'close_date': self.end_date,
            'site_id': sub_project_id.construction_site_id.id,
            'project_id': sub_project_id.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Project Phase(WBS)'),
            'res_model': 'job.costing',
            'res_id': phase_id.id,
            'view_mode': 'form',
            'target': 'current'
        }

    @api.constrains('project_start_date', 'project_end_date', 'start_date')
    def _check_wbs_start_date(self):
        """Check WBS Start Date"""
        for record in self:
            if record.project_start_date and record.project_end_date:
                if not record.project_start_date <= record.start_date <= record.project_end_date:
                    raise ValidationError(_("Invalid start date. Must be within sub project start "
                                            "and end dates."))

    @api.constrains('start_date', 'project_end_date', 'end_date')
    def _check_wbs_end_date(self):
        """Check WBS End Date"""
        for record in self:
            if record.start_date and record.project_end_date:
                if not record.project_end_date >= record.end_date > record.start_date:
                    raise ValidationError(_("Invalid end date. Must be within start date and sub "
                                            "project end date."))

    @api.depends('activity_id', 'sub_project_id')
    def _compute_work_type_ids(self):
        """Compute Work Type ID"""
        ids = self.sub_project_id.boq_budget_ids.mapped(
            'activity_id').mapped('id')
        self.work_type_ids = ids

    @api.depends("sub_project_id", "sub_project_id.budget_id", "sub_project_id.budget_id")
    def _compute_is_any_pending_ra(self):
        """Compute Is Pending RA"""
        for rec in self:
            is_any_pending_ra = False
            budget_lines = self.env['project.budget'].sudo().search(
                [('sub_project_budget_id', '=', rec.sub_project_id.budget_id.id)])
            for data in budget_lines:
                if not data.rate_analysis_id:
                    is_any_pending_ra = True
                    break
            rec.is_any_pending_ra = is_any_pending_ra
