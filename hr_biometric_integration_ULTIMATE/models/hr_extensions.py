# File: models/hr_extensions.py

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from collections import defaultdict
from datetime import datetime, time
import pytz # Library penting untuk memaksa timezone

class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    @api.model
    def api_process_attendance(self, secret_key, attendances):
   
        conf_key = self.env['ir.config_parameter'].sudo().get_param('biometric_sync.secret_key')
        if not conf_key or secret_key != conf_key:
            raise ValidationError("Secret Key tidak valid.")

        if not attendances:
            return {'status': 'success', 'summary': 'Tidak ada data absensi untuk diproses.'}

        # Definisikan sumber timezone secara eksplisit.
        SOURCE_TIMEZONE = pytz.timezone('Asia/Jakarta') 
        UTC_TIMEZONE = pytz.utc

        def convert_to_utc_for_odoo(naive_timestamp_str):
            
            try:
                naive_dt = datetime.strptime(naive_timestamp_str, '%Y-%m-%d %H:%M:%S')
                aware_local_dt = SOURCE_TIMEZONE.localize(naive_dt)
                utc_dt = aware_local_dt.astimezone(UTC_TIMEZONE)
                return utc_dt.strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                return None

        daily_scans = defaultdict(list)
        for att_data in attendances:
            try:
                timestamp = fields.Datetime.from_string(att_data['timestamp'])
                employee = self.env['hr.employee'].search([('barcode', '=', att_data['uid'])], limit=1)
                if not employee: continue
                date_key = timestamp.date()
                unique_key = f"{employee.id}-{date_key}"
                daily_scans[unique_key].append(timestamp)
            except Exception:
                continue

        processed_count = 0
        for unique_key, scans in daily_scans.items():
            if not scans: continue
            
            employee_id = int(unique_key.split('-')[0])
            scan_date = scans[0].date()
            
            first_scan = min(scans)
            last_scan = max(scans)
            
            check_in_for_odoo = convert_to_utc_for_odoo(first_scan.strftime('%Y-%m-%d %H:%M:%S'))
            check_out_for_odoo = False
            if len(scans) > 1:
                check_out_for_odoo = convert_to_utc_for_odoo(last_scan.strftime('%Y-%m-%d %H:%M:%S'))

            if not check_in_for_odoo: continue

            domain = [
                ('employee_id', '=', employee_id),
                ('check_in', '>=', datetime.combine(scan_date, time.min)),
                ('check_in', '<=', datetime.combine(scan_date, time.max)),
            ]
            attendance_record = self.env['hr.attendance'].search(domain, limit=1)
            
            if attendance_record:
                vals_to_update = {}
                if fields.Datetime.from_string(check_in_for_odoo) < attendance_record.check_in:
                    vals_to_update['check_in'] = check_in_for_odoo
                if check_out_for_odoo:
                    if not attendance_record.check_out or fields.Datetime.from_string(check_out_for_odoo) > attendance_record.check_out:
                        vals_to_update['check_out'] = check_out_for_odoo
                if vals_to_update:
                    attendance_record.write(vals_to_update)
            else:
                self.env['hr.attendance'].create({
                    'employee_id': employee_id,
                    'check_in': check_in_for_odoo,
                    'check_out': check_out_for_odoo,
                })
            
            processed_count += 1
            
        summary = f"{len(daily_scans)} hari data karyawan berhasil diolah menjadi {processed_count} record absensi."
        return {'status': 'success', 'summary': summary, 'errors': []}

class HrAttendance(models.Model):
    _inherit = 'hr.attendance'
   