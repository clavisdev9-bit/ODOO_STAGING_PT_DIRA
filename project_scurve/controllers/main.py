import logging
from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class SCurveController(http.Controller):
    """
    JSON-RPC controller for the S-Curve dashboard.
    The OWL component calls get_scurve_data() via the standard
    /web/dataset/call_kw endpoint (model: project.scurve.dashboard,
    method: get_scurve_data), so a dedicated route is optional.
    This route provides a convenience REST endpoint for testing.
    """

    @http.route(
        '/project/<int:project_id>/scurve/data',
        type='json',
        auth='user',
        methods=['POST'],
    )
    def scurve_data(self, project_id, milestone_filter=False):
        """
        Return S-Curve JSON payload for project_id.
        Optional body param: milestone_filter (int or false).
        """
        # Access check — browse raises if user has no read access
        request.env['project.project'].browse(project_id).check_access_rights('read')
        dashboard = request.env['project.scurve.dashboard']
        return dashboard.get_scurve_data(project_id, milestone_filter=milestone_filter)
