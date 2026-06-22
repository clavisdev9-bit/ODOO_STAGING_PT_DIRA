from odoo import models, api


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    # ------------------------------------------------------------------
    # Trigger B — new line added to SO that already has project_id
    # ------------------------------------------------------------------

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)

        # Collect unique orders that have a project set
        orders_with_project = lines.mapped('order_id').filtered('project_id')
        if orders_with_project:
            orders_with_project._sync_analytic()

        return lines
