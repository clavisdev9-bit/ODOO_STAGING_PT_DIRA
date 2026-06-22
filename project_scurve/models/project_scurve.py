import logging
from odoo import api, fields, models
from odoo.tools import float_round
from ..utils.scurve_calculator import (
    compute_scurve_lines,
    compute_forecast_finish_week,
    build_chart_data,
    compute_milestone_summary,
    STATUS_COLORS,
    STATUS_LABELS,
)

_logger = logging.getLogger(__name__)


class ProjectScurveLine(models.Model):
    """
    Non-stored, computed weekly aggregation of S-Curve data per project.
    This model exists to provide a structured representation for views;
    actual data is always computed on the fly from project.task records.
    """
    _name = 'project.scurve.line'
    _description = 'S-Curve Weekly Line'

    project_id = fields.Many2one('project.project', string="Project")
    week_number = fields.Integer(string="Week No.")
    week_label = fields.Char(string="Week")
    planned_hours_week = fields.Float(string="Planned Hrs (Week)")
    actual_hours_week = fields.Float(string="Actual Hrs (Week)")
    cumulative_planned = fields.Float(string="Cumulative Planned")
    cumulative_actual = fields.Float(string="Cumulative Actual")
    bcr = fields.Float(string="BCR (%)", digits=(6, 2))
    bca = fields.Float(string="BCA (%)", digits=(6, 2))
    deviation = fields.Float(string="Deviation (%)", digits=(6, 2))
    status = fields.Selection([
        ('ahead',    'Ahead of Schedule'),
        ('on_track', 'On Track'),
        ('late',     'Late'),
        ('critical', 'Critical'),
    ], string="Status")
    forecast_bca = fields.Float(string="Forecast BCA (%)", digits=(6, 2))


class ProjectScurveDashboard(models.TransientModel):
    """
    Transient model providing computed KPIs and chart data for the
    S-Curve Dashboard.  The get_scurve_data() method is the primary
    entry point called by the OWL component via JSON-RPC.
    """
    _name = 'project.scurve.dashboard'
    _description = 'S-Curve Dashboard'

    project_id = fields.Many2one('project.project', string="Project")

    # -------------------------------------------------------------------------
    # Public API — called by OWL component
    # -------------------------------------------------------------------------

    @api.model
    def get_scurve_data(self, project_id, milestone_filter=False):
        """
        Return complete S-Curve payload for the frontend chart component.

        :param project_id:      int  — project.project id
        :param milestone_filter: int or False — filter to a single milestone id
        :returns: dict with keys: kpis, chart_data, milestones
        """
        project = self.env['project.project'].browse(project_id)
        if not project.exists():
            return self._empty_response()

        # --- fetch all tasks for the project (with week numbers) via SQL ----
        self.env.cr.execute("""
            SELECT
                pt.id,
                pt.x_week_number,
                pt.planned_hours,
                COALESCE(SUM(aal.unit_amount), 0.0) AS effective_hours,
                pt.milestone_id
            FROM project_task pt
            LEFT JOIN account_analytic_line aal ON aal.task_id = pt.id
            WHERE pt.project_id = %s
              AND pt.active = TRUE
            GROUP BY pt.id, pt.x_week_number, pt.planned_hours, pt.milestone_id
        """, (project_id,))
        all_rows = self.env.cr.dictfetchall()

        # total planned for the project (all tasks, even without week number)
        total_planned = sum(float(r['planned_hours'] or 0) for r in all_rows)

        # --- apply milestone filter if requested ----------------------------
        if milestone_filter:
            filtered_rows = [r for r in all_rows if r['milestone_id'] == milestone_filter]
        else:
            filtered_rows = all_rows

        task_rows = [
            {
                'week_number':   r['x_week_number'],
                'planned_hours': r['planned_hours'],
                'actual_hours':  r['effective_hours'],
            }
            for r in filtered_rows
            if r['x_week_number'] and r['x_week_number'] > 0
        ]

        # --- compute S-Curve lines ------------------------------------------
        lines = compute_scurve_lines(task_rows, total_planned_project=total_planned)

        if not lines:
            return self._empty_response(milestones=self._milestone_data(all_rows, total_planned))

        # --- KPIs -----------------------------------------------------------
        last_actual_week = max(
            (ln['week_number'] for ln in lines if (ln['actual_hours_week'] or 0) > 0),
            default=0
        )
        current_line = next(
            (ln for ln in reversed(lines) if ln['week_number'] <= (last_actual_week or lines[-1]['week_number'])),
            lines[-1]
        )

        forecast_finish_week = compute_forecast_finish_week(lines, last_actual_week)
        planned_end_week     = max(ln['week_number'] for ln in lines)
        if forecast_finish_week:
            additional_weeks = max(0, round(forecast_finish_week - planned_end_week))
        else:
            additional_weeks = 0

        deviation   = current_line['deviation']
        status_key  = current_line['status']

        kpis = {
            'current_bcr':              round(current_line['bcr'], 2),
            'current_bca':              round(current_line['bca'], 2),
            'deviation':                round(deviation, 2),
            'status':                   status_key,
            'status_label':             STATUS_LABELS[status_key],
            'status_color':             STATUS_COLORS[status_key],
            'forecast_additional_weeks': additional_weeks,
            'total_planned_hours':      round(total_planned, 2),
            'total_actual_hours':       round(
                sum(float(r['effective_hours'] or 0) for r in filtered_rows), 2
            ),
            'last_week_with_actual':    last_actual_week,
        }

        # --- chart data -----------------------------------------------------
        chart_data = build_chart_data(lines, total_weeks=planned_end_week)

        # --- milestone breakdown --------------------------------------------
        milestones = self._milestone_data(all_rows, total_planned)

        return {
            'kpis':       kpis,
            'chart_data': chart_data,
            'milestones': milestones,
        }

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    def _milestone_data(self, all_rows, total_planned):
        """Build milestone summary from raw task rows."""
        # collect milestone ids and names
        milestone_ids = list({r['milestone_id'] for r in all_rows if r['milestone_id']})
        if not milestone_ids:
            return []

        milestones_recs = self.env['project.milestone'].browse(milestone_ids)
        ms_name_map = {m.id: m.name for m in milestones_recs}

        rows_by_ms = {}
        for r in all_rows:
            ms_id = r['milestone_id']
            if not ms_id:
                continue
            if ms_id not in rows_by_ms:
                rows_by_ms[ms_id] = {
                    'name': ms_name_map.get(ms_id, f'Milestone {ms_id}'),
                    'rows': [],
                }
            rows_by_ms[ms_id]['rows'].append({
                'planned_hours': r['planned_hours'],
                'actual_hours':  r['effective_hours'],
            })

        return compute_milestone_summary(rows_by_ms, total_planned)

    @staticmethod
    def _empty_response(milestones=None):
        return {
            'kpis': {
                'current_bcr': 0.0,
                'current_bca': 0.0,
                'deviation': 0.0,
                'status': 'on_track',
                'status_label': 'No Data',
                'status_color': '#888888',
                'forecast_additional_weeks': 0,
                'total_planned_hours': 0.0,
                'total_actual_hours': 0.0,
                'last_week_with_actual': 0,
            },
            'chart_data': {'labels': [], 'plan': [], 'actual': [], 'forecast': []},
            'milestones': milestones or [],
        }
