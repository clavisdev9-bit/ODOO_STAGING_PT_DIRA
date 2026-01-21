from odoo import fields, models, api


class BudgetLine(models.Model):
    _inherit = 'budget.line'
    _rec_name = "account_id"

    request = fields.Float(string='Request', compute='_compute_request')
    remaining = fields.Float(string='Remaining', compute='_compute_request')
    request_ids = fields.One2many(comodel_name='budget.request', inverse_name='budget_line_id', string='Request Detail')

    @api.depends('request_ids.amount', 'budget_amount')
    def _compute_request(self):
        for line in self:
            total_request = sum(line.request_ids.mapped('amount'))
            line.request = total_request
            line.remaining = line.budget_amount - total_request