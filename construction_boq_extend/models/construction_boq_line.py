# -*- coding: utf-8 -*-
from odoo import api, fields, models

CATEGORY_SELECTION = [
    ('preparation', 'Persiapan'),
    ('earthwork', 'Pekerjaan Tanah'),
    ('foundation', 'Pondasi'),
    ('structure', 'Struktur'),
    ('architecture', 'Arsitektur'),
    ('mep', 'MEP'),
    ('finishing', 'Finishing'),
    ('external', 'Pekerjaan Luar'),
]


class ConstructionBoqLine(models.Model):
    _name = 'tk.construction.boq.line'
    _description = 'Construction BOQ Line Item'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    site_id = fields.Many2one('tk.construction.site', string='Construction Site', ondelete='cascade', required=True)
    category = fields.Selection(CATEGORY_SELECTION, string='Divisi')
    name = fields.Char(string='Uraian Pekerjaan', required=True)
    product_id = fields.Many2one('product.product', string='Product')
    uom_id = fields.Many2one('uom.uom', string='Satuan')
    product_uom_category_id = fields.Many2one(related='product_id.uom_id.category_id', store=False)

    qty_plan = fields.Float(string='Volume Rencana', digits='Product Unit of Measure')
    price_material = fields.Monetary(string='Harga Material', currency_field='currency_id')
    price_labor = fields.Monetary(string='Harga Tenaga Kerja', currency_field='currency_id')
    price_equipment = fields.Monetary(string='Harga Peralatan', currency_field='currency_id')
    overhead_pct = fields.Float(string='Overhead (%)')
    unit_price = fields.Monetary(string='Harga Satuan', compute='_compute_unit_price', store=True, currency_field='currency_id')
    subtotal_plan = fields.Monetary(string='Jumlah RAB', compute='_compute_subtotal_plan', store=True, currency_field='currency_id')

    qty_actual = fields.Float(string='Volume Realisasi', digits='Product Unit of Measure')
    subtotal_actual = fields.Monetary(string='Jumlah Realisasi', compute='_compute_subtotal_actual', store=True, currency_field='currency_id')
    progress = fields.Float(string='Progress (%)', compute='_compute_progress', store=True)

    currency_id = fields.Many2one('res.currency', related='site_id.currency_id', store=True)
    note = fields.Text(string='Catatan')
    purchase_line_ids = fields.One2many('purchase.order.line', 'boq_line_id', string='Purchase Order Lines')

    @api.depends('price_material', 'price_labor', 'price_equipment', 'overhead_pct')
    def _compute_unit_price(self):
        for rec in self:
            base = rec.price_material + rec.price_labor + rec.price_equipment
            rec.unit_price = base * (1 + rec.overhead_pct / 100.0)

    @api.depends('qty_plan', 'unit_price')
    def _compute_subtotal_plan(self):
        for rec in self:
            rec.subtotal_plan = rec.qty_plan * rec.unit_price

    @api.depends('qty_actual', 'unit_price')
    def _compute_subtotal_actual(self):
        for rec in self:
            rec.subtotal_actual = rec.qty_actual * rec.unit_price

    @api.depends('subtotal_actual', 'subtotal_plan')
    def _compute_progress(self):
        for rec in self:
            if rec.subtotal_plan:
                rec.progress = (rec.subtotal_actual / rec.subtotal_plan) * 100.0
            else:
                rec.progress = 0.0
