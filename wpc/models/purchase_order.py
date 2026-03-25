from odoo import api, fields, models, _

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    warning = fields.Text('Warning', compute='_compute_warning', store=False)

    # @api.depends('partner_id')
    # def _compute_warning(self):
    #     for record in self:
    #         record.warning = (
    #             _("Vendor's Fiscal Position is empty!") if record.partner_id and not record.partner_id.property_account_position_id else ''
    #         )
    #
    #         for line in record.order_line:
    #             record.warning = (
    #                 _("Product's Tax is empty!") if line.product_id and not line.product_id.supplier_tax_id else ''
    #             )

    @api.depends(
        'partner_id',
        'partner_id.property_account_position_id',
        'order_line.product_id',
        'order_line.product_id.supplier_taxes_id'
    )
    def _compute_warning(self):
        for record in self:
            record.warning = (
                _("Vendor's Fiscal Position is empty")
                if record.partner_id and not record.partner_id.property_account_position_id
                else (
                    _('Some products have no Supplier Tax')
                    if any(line.product_id and not line.product_id.supplier_taxes_id for line in record.order_line)
                    else ''
                )
            )
