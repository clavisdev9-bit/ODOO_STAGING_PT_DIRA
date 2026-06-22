"""
Pure Python S-Curve calculation engine.
No ORM dependency — accepts plain dicts and returns plain dicts.
"""
import logging

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Threshold constants
# ---------------------------------------------------------------------------
DEVIATION_AHEAD = 0.0      # D > 0 %
DEVIATION_ON_TRACK = -5.0  # -5 % < D <= 0 %
DEVIATION_LATE = -15.0     # -15 % < D <= -5 %
# D <= -15 % → critical

STATUS_COLORS = {
    'ahead':    '#0F6E56',
    'on_track': '#0F6E56',
    'late':     '#BA7517',
    'critical': '#CC3333',
}

STATUS_LABELS = {
    'ahead':    'Ahead of Schedule',
    'on_track': 'On Track',
    'late':     'Late',
    'critical': 'Critical',
}


def _deviation_status(deviation):
    """Return status key for a given deviation value (%)."""
    if deviation > DEVIATION_AHEAD:
        return 'ahead'
    if deviation > DEVIATION_ON_TRACK:
        return 'on_track'
    if deviation > DEVIATION_LATE:
        return 'late'
    return 'critical'


def compute_scurve_lines(task_rows, total_planned_project=None):
    """
    Compute S-Curve weekly aggregation from a list of task dicts.

    Each task dict must contain:
        week_number   (int)   — x_week_number value (> 0)
        planned_hours (float) — planned_hours field
        actual_hours  (float) — effective_hours field

    Returns a list of weekly-line dicts sorted by week_number.
    The denominator for BCR/BCA is always total_planned_project
    (sum of ALL planned hours for the project, including tasks without a
    week number).  If not supplied it is derived from task_rows.
    """
    if not task_rows:
        return []

    # --- aggregate by week ---------------------------------------------------
    week_map = {}
    for row in task_rows:
        wk = int(row.get('week_number', 0))
        if wk <= 0:
            continue
        if wk not in week_map:
            week_map[wk] = {'planned': 0.0, 'actual': 0.0}
        week_map[wk]['planned'] += float(row.get('planned_hours', 0) or 0)
        week_map[wk]['actual']  += float(row.get('actual_hours',  0) or 0)

    if not week_map:
        return []

    total_planned = (
        float(total_planned_project) if total_planned_project
        else sum(r['planned'] for r in week_map.values())
    )
    if total_planned <= 0:
        _logger.warning('compute_scurve_lines: total_planned is 0, cannot compute BCR/BCA')
        return []

    weeks_sorted = sorted(week_map.keys())

    # --- running totals + BCR/BCA -------------------------------------------
    cum_planned = 0.0
    cum_actual  = 0.0
    last_actual_week = 0
    lines = []

    for wk in weeks_sorted:
        data = week_map[wk]
        cum_planned += data['planned']
        cum_actual  += data['actual']

        bcr = round(cum_planned / total_planned * 100, 4)
        bca = round(cum_actual  / total_planned * 100, 4)
        deviation = round(bca - bcr, 4)
        status = _deviation_status(deviation)

        if data['actual'] > 0:
            last_actual_week = wk

        lines.append({
            'week_number':       wk,
            'week_label':        f'Week {wk}',
            'planned_hours_week': round(data['planned'], 2),
            'actual_hours_week':  round(data['actual'],  2),
            'cumulative_planned': round(cum_planned, 2),
            'cumulative_actual':  round(cum_actual,  2),
            'bcr':       bcr,
            'bca':       bca,
            'deviation': deviation,
            'status':    status,
            'forecast_bca': None,  # filled in next pass
        })

    # --- linear forecast for weeks beyond last_actual_week ------------------
    # velocity = BCA(last_actual_week) / last_actual_week  [% per week]
    if last_actual_week > 0:
        last_bca = next(
            (ln['bca'] for ln in lines if ln['week_number'] == last_actual_week),
            0.0
        )
        velocity = last_bca / last_actual_week if last_actual_week > 0 else 0.0

        for ln in lines:
            wk = ln['week_number']
            if wk > last_actual_week:
                forecast = last_bca + (wk - last_actual_week) * velocity
                ln['forecast_bca'] = round(min(forecast, 100.0), 4)

    return lines


def compute_forecast_finish_week(lines, last_actual_week):
    """
    Given S-Curve lines and the last week with actual data,
    return the projected week number at which BCA reaches 100 %.
    Returns None if forecast cannot be computed.
    """
    if not lines or last_actual_week <= 0:
        return None

    last_bca = next(
        (ln['bca'] for ln in lines if ln['week_number'] == last_actual_week),
        0.0
    )
    if last_bca <= 0:
        return None

    velocity = last_bca / last_actual_week
    if velocity <= 0:
        return None

    remaining = 100.0 - last_bca
    additional_weeks = remaining / velocity
    return last_actual_week + additional_weeks


def build_chart_data(lines, total_weeks=None):
    """
    Convert S-Curve lines into the chart_data structure expected by the OWL component.

    Returns:
        {
            'labels':   ['Week 1', 'Week 2', ...],
            'plan':     [bcr_wk1, bcr_wk2, ...],
            'actual':   [bca_wk1, ..., null, null],  # null after last actual week
            'forecast': [null, ..., null, bca_last, forecast_wk+1, ...],
        }
    """
    if not lines:
        return {'labels': [], 'plan': [], 'actual': [], 'forecast': []}

    max_week = max(ln['week_number'] for ln in lines)
    if total_weeks and total_weeks > max_week:
        max_week = total_weeks

    line_by_week = {ln['week_number']: ln for ln in lines}

    # Determine last week with actual data
    last_actual_week = max(
        (ln['week_number'] for ln in lines if (ln['actual_hours_week'] or 0) > 0),
        default=0
    )

    labels   = []
    plan     = []
    actual   = []
    forecast = []

    for wk in range(1, max_week + 1):
        ln = line_by_week.get(wk)
        labels.append(f'Week {wk}')

        plan.append(round(ln['bcr'], 2) if ln else None)

        if ln and wk <= last_actual_week:
            actual.append(round(ln['bca'], 2))
        else:
            actual.append(None)

        if ln and wk >= last_actual_week and last_actual_week > 0:
            forecast.append(round(ln['bca'] if wk == last_actual_week else (ln['forecast_bca'] or 0), 2))
        else:
            forecast.append(None)

    return {
        'labels':   labels,
        'plan':     plan,
        'actual':   actual,
        'forecast': forecast,
    }


def compute_milestone_summary(task_rows_by_milestone, total_planned_project):
    """
    Compute per-milestone BCR/BCA/deviation.

    task_rows_by_milestone: dict  { milestone_id: {'name': str, 'rows': [task_dict]} }
    Returns list of milestone summary dicts.
    """
    result = []
    total = float(total_planned_project) if total_planned_project else 0

    for ms_id, ms_data in task_rows_by_milestone.items():
        rows = ms_data.get('rows', [])
        planned = sum(float(r.get('planned_hours', 0) or 0) for r in rows)
        actual  = sum(float(r.get('actual_hours',  0) or 0) for r in rows)

        if total > 0:
            bcr = round(planned / total * 100, 2)
            bca = round(actual  / total * 100, 2)
        else:
            bcr = bca = 0.0

        deviation = round(bca - bcr, 2)
        status    = _deviation_status(deviation)

        result.append({
            'id':            ms_id,
            'name':          ms_data.get('name', ''),
            'planned_hours': round(planned, 2),
            'actual_hours':  round(actual, 2),
            'bcr':           bcr,
            'bca':           bca,
            'deviation':     deviation,
            'status':        status,
            'status_label':  STATUS_LABELS[status],
            'status_color':  STATUS_COLORS[status],
        })

    return result
