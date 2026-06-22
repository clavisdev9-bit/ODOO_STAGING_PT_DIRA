import logging
from odoo import models, api

_logger = logging.getLogger(__name__)

# Must match the analytic plan name exactly as stored in the DB
_PROJECT_PLAN_NAME = 'Project'


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # ------------------------------------------------------------------
    # Core helper — single source of truth for the lookup + inject
    # ------------------------------------------------------------------

    def _sync_analytic(self):
        """
        CR logic:
            sale.order.project_id
                → project.project.account_id          (Odoo 18 field name)
                → validated: plan_id.name = 'Project'
                → inject { str(id): 100.0 } into every order_line

        Skips silently (with warning) when:
            - project_id is not set
            - project has no analytic account
            - analytic account plan ≠ 'Project'
        """
        for order in self:
            project = order.project_id
            if not project:
                continue

            # Odoo 18 stores the analytic account as `account_id` on project.project
            # (CR spec uses the Odoo 16/17 alias `analytic_account_id`)
            analytic_account = project.account_id
            if not analytic_account:
                _logger.warning(
                    'analytic_auto | %s: project "%s" has no analytic account — skipping.',
                    order.name, project.name,
                )
                continue

            if analytic_account.plan_id.name != _PROJECT_PLAN_NAME:
                _logger.warning(
                    'analytic_auto | %s: account "%s" plan="%s" != "%s" — skipping.',
                    order.name, analytic_account.name,
                    analytic_account.plan_id.name, _PROJECT_PLAN_NAME,
                )
                continue

            distribution = {str(analytic_account.id): 100.0}
            order.order_line.with_context(
                _sync_analytic_distribution=True
            ).write({'analytic_distribution': distribution})

            _logger.info(
                'analytic_auto | %s: analytic_distribution = {"%s": 100.0} -> %d lines.',
                order.name, analytic_account.id, len(order.order_line),
            )

    # ------------------------------------------------------------------
    # Trigger A — SO create / write
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        orders._sync_analytic()
        return orders

    def write(self, vals):
        # Context guard: skip re-entry when this write() is called from _sync_analytic()
        if self.env.context.get('_sync_analytic_distribution'):
            return super().write(vals)

        result = super().write(vals)

        # Re-sync only when project_id actually changed
        if 'project_id' in vals:
            self.with_context(_sync_analytic_distribution=True)._sync_analytic()

        return result
