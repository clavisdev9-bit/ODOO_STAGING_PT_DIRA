from datetime import datetime, timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError


class SyncAttendanceWizard(models.TransientModel):
    """Wizard untuk menjalankan sinkronisasi manual dari satu device."""
    _name = 'hr.attendance.sync.wizard'
    _description = 'Wizard Sync Manual Absensi'

    device_id = fields.Many2one(
        'hr.attendance.device', string='Mesin Absensi', required=True
    )
    sync_mode = fields.Selection([
        ('pull', 'Tarik Data dari Mesin (Pull)'),
        ('push_test', 'Test Push Data Sample'),
    ], string='Mode Sync', default='pull')

    date_from = fields.Date(
        string='Dari Tanggal', default=lambda self: fields.Date.today() - timedelta(days=7)
    )
    date_to = fields.Date(
        string='Sampai Tanggal', default=fields.Date.today
    )

    clear_existing = fields.Boolean(
        string='Hapus Data Lama di Rentang Ini',
        help='Jika dicentang, record absensi lama dalam rentang tanggal ini akan dihapus sebelum sync.'
    )

    # Hasil
    state = fields.Selection([
        ('draft', 'Siap'),
        ('done', 'Selesai'),
        ('error', 'Error'),
    ], default='draft')
    result_summary = fields.Text(string='Hasil', readonly=True)
    sync_history_id = fields.Many2one('hr.attendance.sync.history', string='ID Sesi Sync', readonly=True)

    @api.onchange('device_id')
    def _onchange_device(self):
        if self.device_id and self.device_id.protocol == 'push':
            self.sync_mode = 'push_test'

    def action_start_sync(self):
        self.ensure_one()
        device = self.device_id

        if device.state != 'active':
            raise UserError(f'Mesin "{device.name}" tidak dalam status Aktif.')

        if self.date_from > self.date_to:
            raise UserError('Tanggal "Dari" tidak boleh lebih besar dari "Sampai".')

        if self.clear_existing:
            self._clear_attendance_range()

        if self.sync_mode == 'pull':
            if device.protocol != 'pull':
                raise UserError('Mode Pull hanya tersedia untuk device dengan protokol Pull.')
            try:
                device.pull_and_sync()
                last_history = self.env['hr.attendance.sync.history'].search(
                    [('device_id', '=', device.id)], order='started_at desc', limit=1
                )
                self.write({
                    'state': 'done',
                    'result_summary': last_history.summary or 'Sync selesai.',
                    'sync_history_id': last_history.id,
                })
            except Exception as e:
                self.write({'state': 'error', 'result_summary': str(e)})

        elif self.sync_mode == 'push_test':
            sample_data = self._generate_sample_data()
            history = self.env['hr.attendance.sync.history'].create({
                'device_id': device.id,
                'sync_type': 'manual',
                'state': 'running',
                'started_at': fields.Datetime.now(),
            })
            result = device._process_attendance_data(sample_data, history)
            device._finalize_sync(history, result)
            self.write({
                'state': 'done',
                'result_summary': (
                    f"Test push selesai.\n"
                    f"Total: {result['total_raw']} | "
                    f"Diproses: {result['processed']} | "
                    f"Dilewati: {result['skipped']}"
                ),
                'sync_history_id': history.id,
            })

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }

    def action_view_history(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Detail Sesi Sync',
            'res_model': 'hr.attendance.sync.history',
            'res_id': self.sync_history_id.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def _clear_attendance_range(self):
        from datetime import datetime, time as dt_time
        employees = self.env['hr.employee'].search([])
        start_dt = datetime.combine(self.date_from, dt_time.min)
        end_dt = datetime.combine(self.date_to, dt_time.max)
        records = self.env['hr.attendance'].search([
            ('employee_id', 'in', employees.ids),
            ('check_in', '>=', start_dt),
            ('check_in', '<=', end_dt),
        ])
        records.unlink()

    def _generate_sample_data(self):
        """Buat data sampel untuk keperluan test push."""
        employees = self.env['hr.employee'].search([], limit=3)
        data = []
        for emp in employees:
            if not emp.barcode:
                continue
            base_date = self.date_from
            data.append({'uid': emp.barcode, 'timestamp': f'{base_date} 08:00:00'})
            data.append({'uid': emp.barcode, 'timestamp': f'{base_date} 17:00:00'})
        return data
