from . import controllers
from . import models
from . import wizard
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Set implied_ids after install.
    Moved out of security.xml to avoid hard ref() failure.
    Uses group_hr_attendance_own_reader (Odoo 18 name; older versions used group_hr_attendance)."""
    # Odoo 18 renamed group_hr_attendance → group_hr_attendance_own_reader
    xmlid = (
        'hr_attendance.group_hr_attendance_own_reader'
        if env.ref('hr_attendance.group_hr_attendance_own_reader', raise_if_not_found=False)
        else 'hr_attendance.group_hr_attendance'
    )
    group_attendance = env.ref(xmlid, raise_if_not_found=False)
    group_user = env.ref('hr_attendance_middleware.group_attendance_middleware_user', raise_if_not_found=False)
    if group_attendance and group_user:
        group_user.write({'implied_ids': [(4, group_attendance.id)]})
        _logger.info('hr_attendance_middleware: linked group_attendance_middleware_user -> %s', xmlid)
    else:
        _logger.warning(
            'hr_attendance_middleware: could not link group_attendance_middleware_user '
            'to hr_attendance group (not found). Grant access manually via Settings > Groups.'
        )
