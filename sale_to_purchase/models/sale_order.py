from odoo import models, fields
from odoo.exceptions import UserError

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    purchase_id = fields.Many2one('purchase.order', string="Purchase Order", readonly=True, copy=False)

    def action_create_purchase_strict_multi(self):

        PurchaseOrder = self.env['purchase.order']
        PurchaseOrderLine = self.env['purchase.order.line']

        created_pos = self.env['purchase.order']

        for order in self:

            if order.purchase_id:
                raise UserError(f"{order.name} sudah memiliki PO.")

            if not order.order_line:
                raise UserError(f"{order.name} tidak memiliki line.")

            # --- 1️⃣ Cari irisan vendor ---
            vendor_sets = []

            for line in order.order_line:
                vendors = line.product_id.seller_ids.mapped('partner_id')
                if not vendors:
                    raise UserError(
                        f"Product {line.product_id.display_name} tidak memiliki vendor."
                    )
                vendor_sets.append(set(vendors.ids))

            common_vendor_ids = set.intersection(*vendor_sets)

            if not common_vendor_ids:
                raise UserError(
                    f"{order.name} tidak memiliki vendor yang sama untuk semua product."
                )

            # Ambil vendor pertama dari intersection
            vendor = self.env['res.partner'].browse(list(common_vendor_ids)[0])

            # --- 2️⃣ Buat PO ---
            po = PurchaseOrder.create({
                'partner_id': vendor.id,
                'origin': order.name,
                'company_id': order.company_id.id,
            })

            # --- 3️⃣ Buat Line dengan harga supplier ---
            for line in order.order_line:

                supplierinfo = line.product_id.seller_ids.filtered(
                    lambda s: s.partner_id == vendor
                )[:1]

                price = supplierinfo.price

                PurchaseOrderLine.create({
                    'order_id': po.id,
                    'product_id': line.product_id.id,
                    'name': line.name,
                    'product_qty': line.product_uom_qty,
                    'product_uom': line.product_uom.id,
                    'price_unit': price,
                    'date_planned': fields.Datetime.now(),
                })

            order.purchase_id = po.id
            created_pos |= po

        # --- 4️⃣ Return action clean ---
        action = self.env.ref('purchase.purchase_form_action').read()[0]

        if len(created_pos) == 1:
            action['views'] = [(False, 'form')]
            action['res_id'] = created_pos.id
        else:
            action['domain'] = [('id', 'in', created_pos.ids)]

        return action