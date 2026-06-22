# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError


class WizardConstructionGenerateSo(models.TransientModel):
    _name = 'wizard.construction.generate.so'
    _description = 'Wizard Generate Sale Order dari BOQ'

    site_id = fields.Many2one('tk.construction.site', string='Construction Site', required=True)
    partner_id = fields.Many2one('res.partner', string='Customer', required=True)
    validity_date = fields.Date(string='Validity Date')
    note = fields.Text(string='Terms and Conditions')
    line_ids = fields.One2many('wizard.construction.generate.so.line', 'wizard_id', string='BOQ Lines')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        site_id = self._context.get('default_site_id')
        if site_id:
            site = self.env['tk.construction.site'].browse(site_id)
            lines = []
            for boq_line in site.boq_line_ids:
                lines.append((0, 0, {
                    'boq_line_id': boq_line.id,
                    'include': True,
                    'name': boq_line.name,
                    'product_id': boq_line.product_id.id if boq_line.product_id else False,
                    'uom_id': boq_line.uom_id.id if boq_line.uom_id else False,
                    'product_uom_qty': boq_line.qty_plan,
                    'price_unit': boq_line.unit_price,
                }))
            res['line_ids'] = lines
        return res

    def action_generate(self):
        self.ensure_one()
        if not self.site_id:
            raise UserError(_("Construction Site is required."))
        if self.site_id.sale_order_id:
            raise UserError(_("A Sale Order already exists for this site."))

        included_lines = self.line_ids.filtered(lambda l: l.include)
        if not included_lines:
            raise UserError(_("Please select at least one BOQ line to include."))

        so_vals = {
            'partner_id': self.partner_id.id,
            'validity_date': self.validity_date,
            'note': self.note,
            'order_line': [],
        }
        analytic_dist = {}
        if self.site_id.analytic_account_id:
            analytic_dist = {str(self.site_id.analytic_account_id.id): 100.0}

        for line in included_lines:
            line_vals = {
                'name': line.name,
                'product_id': line.product_id.id if line.product_id else False,
                'product_uom': line.uom_id.id if line.uom_id else False,
                'product_uom_qty': line.product_uom_qty,
                'price_unit': line.price_unit,
            }
            if analytic_dist:
                line_vals['analytic_distribution'] = analytic_dist
            so_vals['order_line'].append((0, 0, line_vals))

        sale_order = self.env['sale.order'].create(so_vals)
        self.site_id.sale_order_id = sale_order.id

        return {
            'type': 'ir.actions.act_window',
            'name': _('Sale Order'),
            'res_model': 'sale.order',
            'res_id': sale_order.id,
            'view_mode': 'form',
            'target': 'current',
        }


class WizardConstructionGenerateSoLine(models.TransientModel):
    _name = 'wizard.construction.generate.so.line'
    _description = 'Wizard Generate SO Line'

    wizard_id = fields.Many2one('wizard.construction.generate.so', ondelete='cascade')
    boq_line_id = fields.Many2one('construction.boq.line', string='BOQ Line')
    include = fields.Boolean(string='Include', default=True)
    name = fields.Char(string='Description')
    product_id = fields.Many2one('product.product', string='Product')
    uom_id = fields.Many2one('uom.uom', string='UoM')
    product_uom_qty = fields.Float(string='Qty', digits='Product Unit of Measure')
    price_unit = fields.Float(string='Unit Price')
    subtotal = fields.Float(string='Subtotal', compute='_compute_subtotal')

    @api.depends('product_uom_qty', 'price_unit')
    def _compute_subtotal(self):
        for rec in self:
            rec.subtotal = rec.product_uom_qty * rec.price_unit
