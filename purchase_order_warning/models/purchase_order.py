from odoo import api, fields, models, _

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    warning = fields.Text('Warning', compute='_compute_warning', store=False)

    @api.depends(
        'order_line.product_id',
        'order_line.product_id.supplier_taxes_id'
    )
    def _compute_warning(self):
        for record in self:
            record.warning = (
                _('Some products have no Supplier Tax')
                if any(line.product_id and not line.product_id.supplier_taxes_id for line in record.order_line)
                else ''
            )
