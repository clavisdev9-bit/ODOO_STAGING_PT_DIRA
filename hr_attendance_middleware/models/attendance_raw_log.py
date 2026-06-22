from odoo import fields, models


class AttendanceRawLog(models.Model):
    """Log mentah data yang diterima dari mesin absensi sebelum diproses."""
    _name = 'hr.attendance.raw.log'
    _description = 'Log Raw Absensi'
    _order = 'raw_timestamp desc'
    _rec_name = 'employee_uid'

    device_id = fields.Many2one(
        'hr.attendance.device', string='Mesin', required=True,
        ondelete='cascade', index=True
    )
    sync_history_id = fields.Many2one(
        'hr.attendance.sync.history', string='Sesi Sync',
        ondelete='set null', index=True
    )
    employee_uid = fields.Char(
        string='ID Karyawan (Mesin)', required=True, index=True,
        help='ID/UID karyawan sebagaimana tercatat di mesin absensi.'
    )
    employee_id = fields.Many2one(
        'hr.employee', string='Karyawan Odoo',
        compute='_compute_employee', store=True
    )
    raw_timestamp = fields.Char(string='Timestamp Raw', help='Timestamp original dari mesin.')
    timestamp_utc = fields.Datetime(string='Timestamp (UTC)', index=True)

    state = fields.Selection([
        ('pending', 'Menunggu'),
        ('processed', 'Diproses'),
        ('skipped', 'Dilewati'),
        ('error', 'Error'),
    ], string='Status', default='pending', index=True)
    error_message = fields.Text(string='Pesan Error')

    attendance_id = fields.Many2one(
        'hr.attendance', string='Record Absensi',
        help='Record hr.attendance yang dibuat dari log ini.'
    )

    def _compute_employee(self):
        for rec in self:
            emp = self.env['hr.employee'].search(
                [('barcode', '=', rec.employee_uid)], limit=1
            )
            rec.employee_id = emp.id if emp else False
