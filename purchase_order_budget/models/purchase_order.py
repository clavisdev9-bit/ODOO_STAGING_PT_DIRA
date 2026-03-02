from odoo import models, fields, api
from odoo.exceptions import UserError

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    state = fields.Selection(selection=[
        ('draft', 'RFQ'),
        ('sent', 'RFQ Sent'),
        ('to approve', 'To Approve'),
        ('confirmed', 'Waiting Manager'),
        ('purchase', 'Purchase Order'),
        ('done', 'Locked'),
        ('cancel', 'Cancel')
    ])

    def button_confirm(self):
        res = super(PurchaseOrder, self).button_confirm()
        for rec in self:
            for line in rec.order_line:
                if line.budget_line_id:
                    if line.price_subtotal > line.budget_line_id.remaining:
                        raise UserError(
                            "⚠️ Anggaran Tidak Mencukupi ⚠️\n\n"
                            f"Anggaran untuk '{line.budget_line_id.account_id.name}' tidak mencukupi.\n"
                            f"Subtotal transaksi: {line.price_subtotal}\n"
                            f"Anggaran tersedia: {line.budget_line_id.remaining}\n\n"
                            "Silakan kurangi jumlah transaksi atau pilih anggaran lain yang sesuai."
                        )
                    else:
                        self.env['budget.request'].create({
                            'date': fields.Date.today(),
                            'reference': rec.name,
                            'product_id': line.product_id.id,
                            'amount': line.price_subtotal,
                            'budget_line_id': line.budget_line_id.id,
                            'po_id': rec.id
                        })
            else:
                raise UserError(
                    "Budget dan Item tidak ditemukan!\n"
                )

            rec.write({'state': 'confirmed'})


        return res

    def button_cancel(self):
        for rec in self:
            requests = self.env['budget.request'].search([('po_id', '=', rec.id)])
            requests.unlink()

        res = super(PurchaseOrder, self).button_cancel()
        return res

    def button_manager(self):
        for rec in self:
            rec.button_approve()

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    budget_id = fields.Many2one(comodel_name='budget.analytic', string='Budget', domain="[('state','=','confirmed')]")
    budget_line_id = fields.Many2one(comodel_name='budget.line', string='Item', domain="[('budget_analytic_id','=',budget_id)]")