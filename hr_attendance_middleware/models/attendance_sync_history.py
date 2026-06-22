from odoo import api, fields, models


class AttendanceSyncHistory(models.Model):
    """Riwayat setiap sesi sinkronisasi data absensi."""
    _name = 'hr.attendance.sync.history'
    _description = 'Riwayat Sinkronisasi Absensi'
    _order = 'started_at desc'

    name = fields.Char(string='Nama Sesi', compute='_compute_name', store=True)
    device_id = fields.Many2one(
        'hr.attendance.device', string='Mesin', required=True,
        ondelete='cascade', index=True
    )
    sync_type = fields.Selection([
        ('auto', 'Otomatis (Cron)'),
        ('manual', 'Manual'),
        ('push', 'Push API'),
    ], string='Tipe Sync', default='manual')

    state = fields.Selection([
        ('running', 'Berjalan'),
        ('success', 'Berhasil'),
        ('partial', 'Sebagian Berhasil'),
        ('error', 'Gagal'),
    ], string='Status', default='running', index=True)

    started_at = fields.Datetime(string='Mulai', default=fields.Datetime.now)
    finished_at = fields.Datetime(string='Selesai')
    duration = fields.Float(
        string='Durasi (detik)', compute='_compute_duration', store=True
    )

    total_raw = fields.Integer(string='Total Data Raw')
    total_processed = fields.Integer(string='Berhasil Diproses')
    total_skipped = fields.Integer(string='Dilewati')
    total_errors = fields.Integer(
        string='Total Error', compute='_compute_total_errors', store=True
    )
    error_log = fields.Text(string='Log Error')
    summary = fields.Text(string='Ringkasan')

    raw_log_ids = fields.One2many(
        'hr.attendance.raw.log', 'sync_history_id', string='Log Raw'
    )
    raw_log_count = fields.Integer(
        string='Jumlah Log Raw', compute='_compute_raw_log_count'
    )

    triggered_by = fields.Many2one('res.users', string='Dipicu Oleh', default=lambda s: s.env.user)

    @api.depends('device_id', 'started_at')
    def _compute_name(self):
        for rec in self:
            dt_str = rec.started_at.strftime('%d/%m/%Y %H:%M') if rec.started_at else ''
            rec.name = f"{rec.device_id.name or 'Device'} - {dt_str}"

    @api.depends('started_at', 'finished_at')
    def _compute_duration(self):
        for rec in self:
            if rec.started_at and rec.finished_at:
                delta = rec.finished_at - rec.started_at
                rec.duration = delta.total_seconds()
            else:
                rec.duration = 0.0

    @api.depends('total_raw', 'total_processed', 'total_skipped')
    def _compute_total_errors(self):
        for rec in self:
            rec.total_errors = max(0, rec.total_raw - rec.total_processed - rec.total_skipped)

    def _compute_raw_log_count(self):
        for rec in self:
            rec.raw_log_count = len(rec.raw_log_ids)

    def action_view_raw_logs(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Log Raw',
            'res_model': 'hr.attendance.raw.log',
            'view_mode': 'list,form',
            'domain': [('sync_history_id', '=', self.id)],
        }
