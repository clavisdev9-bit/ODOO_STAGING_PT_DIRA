from odoo import fields, models

class BudgetLine(models.Model):
    _inherit = 'budget.line'
    _rec_name = "account_id"