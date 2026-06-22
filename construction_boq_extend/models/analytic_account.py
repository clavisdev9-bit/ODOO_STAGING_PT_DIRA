# -*- coding: utf-8 -*-
import logging
from odoo import models

_logger = logging.getLogger(__name__)

_PROJECT_PLAN_NAME = 'Project'


class AnalyticAccountProjectSync(models.Model):
    """Keep project.project and tk.construction.site in sync when an analytic
    account is edited (Save & Close trigger → write()).

    Sync targets:
      1. project.project  (any plan) — name + partner_id
      2. tk.construction.site (plan = 'Project' only) — partner_id

    Link for (1): project.project.account_id → account.analytic.account
    Link for (2): tk.construction.site.analytic_account_id → account.analytic.account
    """

    _inherit = 'account.analytic.account'

    # ------------------------------------------------------------------
    # Sync 1: project.project (existing behaviour, unchanged)
    # ------------------------------------------------------------------

    def _sync_name_partner_to_project(self, vals):
        """Push name / partner_id to the project.project whose account_id = self."""
        if self.env.context.get('_skip_analytic_project_sync'):
            return

        include_name = 'name' in vals
        include_partner = 'partner_id' in vals
        if not include_name and not include_partner:
            return

        Project = self.env['project.project']
        ctx = dict(self.env.context, _skip_analytic_project_sync=True)

        for rec in self:
            project = Project.search([('account_id', '=', rec.id)], limit=1)
            if not project:
                continue

            sync_vals = {'allow_timesheets': True}
            if include_name:
                sync_vals['name'] = rec.name
            if include_partner:
                sync_vals['partner_id'] = rec.partner_id.id or False

            project.with_context(ctx).write(sync_vals)

    # ------------------------------------------------------------------
    # Sync 2: tk.construction.site.partner_id (CR — plan = Project only)
    # ------------------------------------------------------------------

    def _sync_partner_to_construction_site(self):
        """CR: propagate partner_id to tk.construction.site when plan = 'Project'.

        Linking field: tk.construction.site.analytic_account_id = self.id
        Condition    : analytic_account.plan_id.name = 'Project'
        Action       : site.partner_id = analytic_account.partner_id
        """
        if self.env.context.get('_skip_analytic_site_sync'):
            return

        ctx = dict(self.env.context, _skip_analytic_site_sync=True)
        Site = self.env['tk.construction.site']

        for rec in self:
            # Guard: only Project plan analytic accounts participate
            if rec.plan_id.name != _PROJECT_PLAN_NAME:
                continue

            site = Site.search([('analytic_account_id', '=', rec.id)], limit=1)
            if not site:
                _logger.warning(
                    'analytic_site_sync | account "%s" (id=%s): '
                    'no linked tk.construction.site found — skipping.',
                    rec.name, rec.id,
                )
                continue

            site.with_context(ctx).write({'partner_id': rec.partner_id.id or False})
            _logger.info(
                'analytic_site_sync | account "%s" -> site "%s": '
                'partner_id set to %s.',
                rec.name, site.name, rec.partner_id.name or 'False',
            )

    # ------------------------------------------------------------------
    # ORM override — single entry point for both syncs
    # ------------------------------------------------------------------

    def write(self, vals):
        result = super().write(vals)

        if 'name' in vals or 'partner_id' in vals:
            self._sync_name_partner_to_project(vals)

        # CR: propagate partner_id change to construction site
        if 'partner_id' in vals:
            self._sync_partner_to_construction_site()

        return result
