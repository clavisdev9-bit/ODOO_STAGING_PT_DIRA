from odoo import fields, models


class BudgetConstruction(models.TransientModel):
    """Budget Construction"""
    _name = 'budget.construction'
    _description = "Budget Construction"

    name = fields.Char(string="Title")
    responsible_id = fields.Many2one('res.users', default=lambda
                                     self: self.env.user and self.env.user.id or False,
                                     string="Responsible",
                                     domain=lambda self: [('groups_id', '=', self.env.ref('base.group_user').id)])

    def action_create_sub_project_budget(self):
        """Create sub project budget"""
        active_id = self._context.get('active_id')
        project_id = self.env['tk.construction.project'].browse(active_id)
        if not project_id.boq_budget_ids:
            message = {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'type': 'info',
                    'message': "Please add BOQ Line to create Budget.",
                    'sticky': False,
                }
            }
            return message

        budget_id = self.env['sub.project.budget'].create({
            'name': self.name,
            'responsible_id': self.responsible_id.id,
            'site_id': project_id.construction_site_id.id,
            'sub_project_id': project_id.id,
            'start_date': project_id.start_date,
            'end_date': project_id.end_date
        })
        project_id.budget_id = budget_id.id
        for data in project_id.boq_budget_ids:
            budget_line = self.env['project.budget'].create({
                'sub_project_budget_id': budget_id.id,
                'job_type_id': data.activity_id.id,
                'sub_category_id': data.sub_activity_id.id,
                'boq_qty': data.total_qty,
                'boq_budget_line_id': data.id
            })
            data.budget_line_id = budget_line.id

        return True
