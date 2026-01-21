from odoo import api, fields, models


class BudgetRequest(models.Model):
    _name = 'budget.request'
    _description = 'Budget Request'

    date = fields.Date(string='Date')
    reference = fields.Char(string='Reference')
    product_id = fields.Many2one(comodel_name='product.product', string='Product')
    amount = fields.Float(string='Amount', default=0)
    budget_line_id = fields.Many2one(comodel_name='budget.line', string='Budget Plan Line')
    po_id = fields.Many2one(comodel_name='purchase.order', string='Purchase Order')