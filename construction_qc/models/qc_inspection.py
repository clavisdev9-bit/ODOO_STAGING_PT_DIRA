from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class QcInspection(models.Model):
    _name = 'qc.inspection'
    _description = 'QC Inspection'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'

    name = fields.Char(
        string='Reference', readonly=True, default='New', copy=False,
    )
    project_id = fields.Many2one(
        'project.project', string='Project', required=True, tracking=True, index=True,
    )
    task_id = fields.Many2one(
        'project.task', string='Task',
        domain="[('project_id', '=', project_id)]", tracking=True,
    )
    area = fields.Char(string='Area', required=True, tracking=True,
                       help='e.g. Level 5, Zone A')
    location = fields.Char(string='Location Detail',
                           help='Specific location within the area')
    work_package = fields.Char(string='Work Package', required=True, tracking=True,
                               help='e.g. Cable Tray Installation')
    spv_id = fields.Many2one(
        'res.users', string='Supervisor', required=True,
        default=lambda self: self.env.user, tracking=True,
    )
    pm_id = fields.Many2one(
        'res.users', string='Project Manager', required=True, tracking=True,
    )
    inspection_date = fields.Date(
        string='Inspection Date', required=True,
        default=fields.Date.today, tracking=True,
    )
    drawing_ref = fields.Char(string='Drawing Reference')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('closed', 'Closed'),
    ], string='Status', default='draft', tracking=True, copy=False, index=True)

    checklist_ids = fields.One2many(
        'qc.checklist.line', 'inspection_id', string='Checklist',
    )
    attachment_ids = fields.One2many(
        'qc.attachment', 'inspection_id', string='Photo Evidence',
    )
    ncr_ids = fields.One2many('qc.ncr', 'inspection_id', string='NCRs')
    corrective_action_ids = fields.One2many(
        'qc.corrective.action', 'inspection_id', string='Corrective Actions',
    )

    pm_note = fields.Text(string='PM Review Notes', tracking=True)
    sign_spv = fields.Binary(string='Supervisor Signature')
    sign_pm = fields.Binary(string='PM Signature')

    progress_qty = fields.Float(string='Approved Quantity', digits=(16, 2))
    progress_uom = fields.Many2one('uom.uom', string='Unit of Measure')

    # Computed
    has_fail = fields.Boolean(
        string='Has Failed Items', compute='_compute_has_fail', store=True,
    )
    ncr_count = fields.Integer(compute='_compute_counts', string='NCR Count')
    ca_count = fields.Integer(compute='_compute_counts', string='CA Count')
    checklist_pass = fields.Integer(compute='_compute_checklist_stats', string='Pass')
    checklist_fail = fields.Integer(compute='_compute_checklist_stats', string='Fail')
    checklist_total = fields.Integer(compute='_compute_checklist_stats', string='Total Items')

    project_name = fields.Char(related='project_id.name', store=True, string='Project Name')

    @api.depends('checklist_ids.result')
    def _compute_has_fail(self):
        for rec in self:
            rec.has_fail = any(l.result == 'fail' for l in rec.checklist_ids)

    @api.depends('checklist_ids.result')
    def _compute_checklist_stats(self):
        for rec in self:
            lines = rec.checklist_ids
            rec.checklist_pass = sum(1 for l in lines if l.result == 'pass')
            rec.checklist_fail = sum(1 for l in lines if l.result == 'fail')
            rec.checklist_total = len(lines)

    def _compute_counts(self):
        for rec in self:
            rec.ncr_count = len(rec.ncr_ids)
            rec.ca_count = len(rec.corrective_action_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('qc.inspection') or 'New'
                )
        return super().create(vals_list)

    @api.onchange('work_package')
    def _onchange_work_package(self):
        if not self.work_package or self.checklist_ids:
            return
        template = self.env['qc.checklist.template'].search(
            [('work_package_type', 'ilike', self.work_package), ('active', '=', True)],
            limit=1,
        )
        if template:
            self.checklist_ids = [
                (0, 0, {
                    'sequence': line.sequence,
                    'item': line.item,
                    'specification': line.specification,
                })
                for line in template.line_ids
            ]

    # ── State transitions ──────────────────────────────────────────────────

    def action_submit(self):
        for rec in self:
            if rec.state != 'draft':
                raise UserError(_('Only draft inspections can be submitted.'))
            rec.write({'state': 'submitted'})
            rec.activity_schedule(
                'mail.mail_activity_data_todo',
                user_id=rec.pm_id.id,
                summary=_('QC Inspection awaiting approval: %s') % rec.name,
                note=_('Work Package: %s | Area: %s') % (rec.work_package, rec.area),
            )
            self._send_mail('construction_qc.mail_template_qc_submitted')

    def action_approve(self):
        for rec in self:
            if rec.state != 'submitted':
                raise UserError(_('Only submitted inspections can be approved.'))
            rec.write({'state': 'approved'})
            if rec.task_id:
                rec.task_id.message_post(
                    body=_('✅ QC Inspection <b>%s</b> approved. '
                           'Qty: %s %s') % (
                        rec.name, rec.progress_qty,
                        rec.progress_uom.name if rec.progress_uom else '',
                    )
                )
            self._send_mail('construction_qc.mail_template_qc_approved')

    def action_reject(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reject QC Inspection'),
            'res_model': 'qc.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_inspection_id': self.id},
        }

    def action_close(self):
        for rec in self:
            if rec.state != 'approved':
                raise UserError(_('Only approved inspections can be closed.'))
            open_cas = rec.corrective_action_ids.filtered(
                lambda ca: ca.status not in ('completed', 'verified')
            )
            if open_cas:
                raise UserError(
                    _('Complete all corrective actions first:\n%s')
                    % '\n'.join('• ' + ca.name for ca in open_cas)
                )
            rec.write({'state': 'closed'})

    def action_revise(self):
        for rec in self:
            if rec.state != 'rejected':
                raise UserError(_('Only rejected inspections can be revised.'))
            rec.write({'state': 'draft'})

    # ── Smart button actions ───────────────────────────────────────────────

    def action_view_ncr(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Non Conformance Reports'),
            'res_model': 'qc.ncr',
            'view_mode': 'list,form',
            'domain': [('inspection_id', '=', self.id)],
            'context': {'default_inspection_id': self.id,
                        'default_project_id': self.project_id.id},
        }

    def action_view_ca(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Corrective Actions'),
            'res_model': 'qc.corrective.action',
            'view_mode': 'list,form',
            'domain': [('inspection_id', '=', self.id)],
            'context': {'default_inspection_id': self.id},
        }

    # ── Constraints ────────────────────────────────────────────────────────

    @api.constrains('state', 'task_id', 'corrective_action_ids')
    def _check_billing_lock(self):
        for rec in self:
            if rec.state == 'rejected' and rec.task_id:
                open_cas = rec.corrective_action_ids.filtered(
                    lambda ca: ca.status not in ('completed', 'verified')
                )
                if open_cas and rec.task_id.stage_id and rec.task_id.stage_id.fold:
                    raise ValidationError(
                        _('Cannot mark task "%s" as done: '
                          'QC Inspection "%s" is Rejected with %d open corrective action(s).')
                        % (rec.task_id.name, rec.name, len(open_cas))
                    )

    # ── Helpers ────────────────────────────────────────────────────────────

    def _send_mail(self, template_xml_id):
        template = self.env.ref(template_xml_id, raise_if_not_found=False)
        if template:
            for rec in self:
                template.send_mail(rec.id, force_send=False)

    # ── Dashboard data ─────────────────────────────────────────────────────

    @api.model
    def get_dashboard_data(self):
        state_colors = {
            'draft': 'secondary',
            'submitted': 'warning',
            'approved': 'success',
            'rejected': 'danger',
            'closed': 'dark',
        }
        state_labels = dict(self._fields['state'].selection)

        all_recs = self.search([])
        recent = self.search([], order='create_date desc', limit=10)

        by_state = {}
        for rec in all_recs:
            by_state[rec.state] = by_state.get(rec.state, 0) + 1

        return {
            'total': len(all_recs),
            'approved': by_state.get('approved', 0),
            'rejected': by_state.get('rejected', 0),
            'pending': by_state.get('submitted', 0),
            'closed': by_state.get('closed', 0),
            'recent': [{
                'id': r.id,
                'name': r.name,
                'project': r.project_id.name or '',
                'work_package': r.work_package or '',
                'area': r.area or '',
                'date': str(r.inspection_date) if r.inspection_date else '',
                'state_color': state_colors.get(r.state, 'secondary'),
                'state_label': state_labels.get(r.state, r.state),
            } for r in recent],
        }
