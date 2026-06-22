# -*- coding: utf-8 -*-
from odoo import fields, models


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    boq_line_id = fields.Many2one('tk.construction.boq.line', string='BOQ Line', ondelete='set null')
