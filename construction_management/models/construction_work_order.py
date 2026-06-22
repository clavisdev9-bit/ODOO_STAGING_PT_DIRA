from odoo import models, fields, api, _
from odoo.exceptions import UserError


class ConstructionWorkOrder(models.Model):
    _name = 'construction.work.order'
    _description = 'Construction Work Order'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'

    name = fields.Char(
        string='WO No.', required=True, copy=False,
        readonly=True, default=lambda self: _('New'),
    )
    contract_id = fields.Many2one(
        'construction.job.contract', string='Contract',
        required=True, ondelete='restrict', index=True,
    )
    project_id = fields.Many2one(
        'project.project', related='contract_id.project_id', store=True,
    )
    boq_line_id = fields.Many2one(
        'cop.line', string='COP Item',
        domain="[('contract_id', '=', contract_id)]",
    )
    task_id = fields.Many2one('project.task', string='Project Task', readonly=True, copy=False)
    currency_id = fields.Many2one(
        'res.currency', related='contract_id.currency_id', store=True,
    )

    description = fields.Char(string='Work Description', required=True)
    location = fields.Char(string='Location / Zone')
    assignee_ids = fields.Many2many('res.users', string='Assignees')
    date_start = fields.Date(string='Start Date')
    date_deadline = fields.Date(string='Deadline')

    volume_plan = fields.Float(string='Planned Volume', digits=(16, 4))
    uom_id = fields.Many2one('uom.uom', string='UoM')
    volume_actual = fields.Float(string='Actual Volume', digits=(16, 4))
    progress = fields.Float(
        string='Progress (%)', compute='_compute_progress', store=True, digits=(5, 2),
    )

    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('done', 'Done'),
        ('late', 'Late'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    notes = fields.Text(string='Notes / Instructions')

    @api.depends('volume_plan', 'volume_actual')
    def _compute_progress(self):
        for rec in self:
            if rec.volume_plan:
                rec.progress = min(rec.volume_actual / rec.volume_plan * 100, 100.0)
            else:
                rec.progress = 0.0

    def action_start(self):
        for rec in self:
            if rec.name == _('New'):
                rec.name = self.env['ir.sequence'].next_by_code('construction.work.order') or _('New')
            rec._create_task()
            rec.state = 'in_progress'

    def action_done(self):
        for rec in self.filtered(lambda r: r.state == 'in_progress'):
            rec.state = 'done'
            if rec.task_id:
                rec.task_id.write({'stage_id': rec._get_done_stage()})
            if rec.boq_line_id and rec.volume_plan:
                rec.boq_line_id.volume_actual += rec.volume_actual
                rec.boq_line_id.progress_physical = min(
                    rec.boq_line_id.progress_physical + rec.progress, 100.0
                )

    def action_cancel(self):
        self.filtered(lambda r: r.state not in ('done',)).write({'state': 'cancelled'})

    def action_reset_draft(self):
        self.filtered(lambda r: r.state == 'cancelled').write({'state': 'draft'})

    def _create_task(self):
        self.ensure_one()
        if self.task_id:
            return
        if not self.project_id:
            raise UserError(_('Contract has no linked project. Please confirm the contract first.'))

        task_vals = {
            'name': self.description,
            'project_id': self.project_id.id,
            'date_deadline': self.date_deadline,
            'description': self.notes or '',
        }
        if self.assignee_ids:
            task_vals['user_ids'] = [(6, 0, self.assignee_ids.ids)]

        task = self.env['project.task'].create(task_vals)
        self.task_id = task

    def _get_done_stage(self):
        stage = self.env['project.task.type'].search(
            [('name', 'ilike', 'done'), ('project_ids', 'in', self.project_id.id)],
            limit=1,
        )
        if not stage:
            stage = self.env['project.task.type'].search(
                [('project_ids', 'in', self.project_id.id)],
                order='sequence desc', limit=1,
            )
        return stage.id if stage else False

    def action_view_task(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'project.task',
            'res_id': self.task_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
