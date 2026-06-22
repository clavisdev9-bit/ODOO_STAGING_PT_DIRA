# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
from datetime import date

from odoo import api, fields, models
from odoo.tools import sql as odoo_sql


class AccountAnalyticAccountBudgetSync(models.Model):
    """Extends account.analytic.account to auto-sync a budget.analytic record
    whenever the account is placed on the 'Project' analytic plan.

    DEPLOYMENT NOTE
    ---------------
    This class adds the column ``budget_analytic_id`` to the
    ``account_analytic_account`` table.  Run once after deploying this file:

        python odoo-bin -c odoo.conf -d <DB> -u tk_construction_management --stop-after-init

    The ``_auto_init`` override below makes this idempotent so re-running
    ``-u`` never fails, and the ``column_exists`` guard in
    ``_sync_budget_analytic`` prevents a 500 error if the column is absent
    (graceful degradation until the upgrade is applied).
    """

    _inherit = 'account.analytic.account'

    budget_analytic_id = fields.Many2one(
        comodel_name='budget.analytic',
        string='Linked Budget',
        ondelete='set null',   # budget deleted → pointer silently NULLed
        copy=False,
        readonly=True,
    )

    # ------------------------------------------------------------------
    # Schema self-healing — runs on every -u, creates column if missing
    # ------------------------------------------------------------------

    def _auto_init(self):
        # Idempotent DDL: add the column before the ORM tries to use it.
        # Without this, the column only appears after the first -u.
        # With this, any subsequent -u is a no-op.
        if not odoo_sql.column_exists(self.env.cr, 'account_analytic_account', 'budget_analytic_id'):
            self.env.cr.execute(
                'ALTER TABLE account_analytic_account '
                'ADD COLUMN budget_analytic_id integer'
            )
        return super()._auto_init()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_project_plan(self):
        """Return the singleton 'Project' analytic plan, or empty recordset."""
        return self.env.ref('analytic.analytic_plan_projects', raise_if_not_found=False)

    @staticmethod
    def _current_year_dates():
        """Default date_from/date_to: current calendar year."""
        today = date.today()
        return today.replace(month=1, day=1), today.replace(month=12, day=31)

    # ------------------------------------------------------------------
    # Core sync logic
    # ------------------------------------------------------------------

    def _sync_budget_analytic(self):
        """Create or update the linked budget.analytic for every record on the
        'Project' plan.  Severs the link (without deleting the budget) when
        plan_id is changed away from 'Project'.

        Layer-2 guard: if the budget_analytic_id column hasn't been migrated
        yet (restart without -u), this method skips silently instead of
        raising a 500 error.
        """
        # Guard: graceful degradation if migration hasn't run yet
        if not odoo_sql.column_exists(self.env.cr, 'account_analytic_account', 'budget_analytic_id'):
            return

        project_plan = self._get_project_plan()
        if not project_plan:
            return

        for rec in self:
            if rec.plan_id == project_plan:
                sync_vals = {
                    'name': rec.name,
                    'budget_type': 'expense',
                }
                if rec.budget_analytic_id:
                    # Update existing — name + forced budget_type
                    rec.budget_analytic_id.write(sync_vals)
                else:
                    # First assignment to 'Project' plan — create new budget.
                    # date_from/date_to are required fields on budget.analytic;
                    # default to the current calendar year.
                    date_from, date_to = self._current_year_dates()
                    sync_vals.update({'date_from': date_from, 'date_to': date_to})
                    # Writing budget_analytic_id back calls write() on this
                    # record with vals={'budget_analytic_id': id}, which does
                    # NOT contain 'name' or 'plan_id', so _sync_budget_analytic
                    # is not re-entered (no recursion).
                    rec.budget_analytic_id = self.env['budget.analytic'].create(sync_vals)

            elif rec.budget_analytic_id:
                # plan_id changed away from 'Project' — sever the link without
                # deleting the budget so budget lines and history are preserved.
                # Writing only 'budget_analytic_id' won't re-trigger this method.
                rec.write({'budget_analytic_id': False})

    # ------------------------------------------------------------------
    # ORM overrides
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._sync_budget_analytic()
        return records

    def write(self, vals):
        res = super().write(vals)
        # Re-evaluate only when sync-relevant fields change.
        if 'name' in vals or 'plan_id' in vals:
            self._sync_budget_analytic()
        return res
