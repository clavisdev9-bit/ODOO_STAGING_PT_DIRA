from odoo import models, fields, api


class SosAuditLog(models.Model):
    _name = 'sos.audit.log'
    _description = 'SOS Audit Log'
    _order = 'datetime desc'
    _rec_name = 'res_name'

    res_model = fields.Char(string='Model', required=True, index=True)
    res_id = fields.Integer(string='Record ID', required=True, index=True)
    res_name = fields.Char(string='Document', required=True)
    field_name = fields.Char(string='Field', required=True)
    old_value = fields.Char(string='Old Value')
    new_value = fields.Char(string='New Value')
    user_id = fields.Many2one(
        'res.users', string='Actor', required=True,
        default=lambda self: self.env.user,
        ondelete='restrict',
    )
    datetime = fields.Datetime(
        string='Timestamp (UTC)', required=True,
        default=fields.Datetime.now,
        index=True,
    )
    note = fields.Text(string='Note')

    @api.model
    def log(self, record, field_name, old_value, new_value, note=None):
        """Convenience factory used by SosAuditMixin.write()."""
        self.sudo().create({
            'res_model': record._name,
            'res_id': record.id,
            'res_name': record.display_name or str(record.id),
            'field_name': field_name,
            'old_value': str(old_value) if old_value is not False else '',
            'new_value': str(new_value) if new_value is not False else '',
            'user_id': self.env.uid,
            'note': note,
        })


class SosAuditMixin(models.AbstractModel):
    """
    Mix into any model to get automatic sos.audit.log entries and chatter
    messages whenever a tracked state field changes.

    Concrete model must define SOS_TRACKED_FIELDS as a list of field names
    to watch, or rely on the default ['state'].
    """
    _name = 'sos.audit.mixin'
    _description = 'SOS Audit Mixin'

    SOS_TRACKED_FIELDS = ['state']

    def write(self, vals):
        tracked_fields = [f for f in self.SOS_TRACKED_FIELDS if f in vals]

        # Snapshot old values per record before the write
        old_values = {}
        if tracked_fields:
            for rec in self:
                old_values[rec.id] = {f: getattr(rec, f, False) for f in tracked_fields}

        result = super().write(vals)

        if not tracked_fields:
            return result

        audit_log = self.env['sos.audit.log']
        for rec in self:
            for field_name in tracked_fields:
                old_val = old_values.get(rec.id, {}).get(field_name, False)
                new_val = getattr(rec, field_name, False)
                if old_val == new_val:
                    continue

                audit_log.log(rec, field_name, old_val, new_val)

                if hasattr(rec, 'message_post'):
                    rec.message_post(
                        body=(
                            f'<b>[SOS]</b> <code>{field_name}</code> changed: '
                            f'<i>{old_val}</i> → <b>{new_val}</b>'
                        ),
                        message_type='notification',
                        subtype_xmlid='mail.mt_note',
                    )

        return result
