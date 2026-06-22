from odoo import api, fields, models, _
from odoo.exceptions import UserError


class QcRejectWizard(models.TransientModel):
    _name = 'qc.reject.wizard'
    _description = 'QC Rejection Wizard'

    inspection_id = fields.Many2one(
        'qc.inspection', string='Inspection', required=True, readonly=True,
    )
    rejection_reason = fields.Text(string='Rejection Reason', required=True)
    create_ca = fields.Boolean(
        string='Create Corrective Action automatically', default=True,
    )
    ca_description = fields.Text(
        string='Corrective Action Required',
        help='Describe what the SPV must fix.',
    )
    ca_target_date = fields.Date(string='CA Target Date')

    @api.onchange('rejection_reason')
    def _onchange_rejection_reason(self):
        if self.rejection_reason and not self.ca_description:
            self.ca_description = self.rejection_reason

    def action_confirm_reject(self):
        self.ensure_one()
        inspection = self.inspection_id
        if inspection.state != 'submitted':
            raise UserError(_('Inspection is no longer in Submitted state.'))

        inspection.write({
            'state': 'rejected',
            'pm_note': self.rejection_reason,
        })

        if self.create_ca and self.ca_description:
            self.env['qc.corrective.action'].create({
                'inspection_id': inspection.id,
                'description': self.ca_description,
                'pic_id': inspection.spv_id.id,
                'target_date': self.ca_target_date,
                'status': 'open',
            })

        # Send rejection notification
        template = self.env.ref(
            'construction_qc.mail_template_qc_rejected', raise_if_not_found=False,
        )
        if template:
            template.send_mail(inspection.id, force_send=False)

        # Schedule activity for SPV
        inspection.activity_schedule(
            'mail.mail_activity_data_todo',
            user_id=inspection.spv_id.id,
            summary=_('QC Rejected — Action Required: %s') % inspection.name,
            note=_('Reason: %s') % self.rejection_reason,
        )

        return {'type': 'ir.actions.act_window_close'}
