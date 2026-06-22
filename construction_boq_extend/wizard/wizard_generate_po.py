# -*- coding: utf-8 -*-
from odoo import fields, models, _
from odoo.exceptions import UserError


class WizardConstructionGeneratePo(models.TransientModel):
    _name = 'wizard.construction.generate.po'
    _description = 'Wizard Generate Purchase Order dari BOQ'

    site_id = fields.Many2one('tk.construction.site', string='Construction Site', required=True)
    partner_id = fields.Many2one('res.partner', string='Vendor', required=True)
    category = fields.Selection([
        ('all', 'All'),
        ('preparation', 'Persiapan'),
        ('earthwork', 'Pekerjaan Tanah'),
        ('foundation', 'Pondasi'),
        ('structure', 'Struktur'),
        ('architecture', 'Arsitektur'),
        ('mep', 'MEP'),
        ('finishing', 'Finishing'),
        ('external', 'Pekerjaan Luar'),
    ], string='Filter Divisi', default='all')

    def action_generate(self):
        self.ensure_one()
        domain = [('site_id', '=', self.site_id.id)]
        if self.category != 'all':
            domain.append(('category', '=', self.category))

        boq_lines = self.env['construction.boq.line'].search(domain)
        if not boq_lines:
            raise UserError(_("No BOQ lines found for the selected filter."))

        po_vals = {
            'partner_id': self.partner_id.id,
            'order_line': [],
        }
        for line in boq_lines:
            po_vals['order_line'].append((0, 0, {
                'name': line.name,
                'product_id': line.product_id.id if line.product_id else False,
                'product_uom': line.uom_id.id if line.uom_id else False,
                'product_qty': line.qty_plan,
                'price_unit': line.unit_price,
                'boq_line_id': line.id,
            }))

        purchase_order = self.env['purchase.order'].create(po_vals)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Order'),
            'res_model': 'purchase.order',
            'res_id': purchase_order.id,
            'view_mode': 'form',
            'target': 'current',
        }
