import logging
from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class ProjectTask(models.Model):
    _inherit = 'project.task'

    x_week_number = fields.Integer(
        string="Week No.",
        default=0,
        help="Sequential week number this task is planned for (1–52). "
             "Used as the grouping key for S-Curve weekly aggregation.",
    )

    @api.constrains('x_week_number')
    def _check_week_number(self):
        for task in self:
            if task.x_week_number != 0 and not (1 <= task.x_week_number <= 52):
                raise ValidationError(
                    "Week No. must be 0 (unset) or between 1 and 52."
                )
