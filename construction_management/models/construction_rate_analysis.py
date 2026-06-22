from odoo import models, fields, api, _


class ConstructionRateAnalysis(models.Model):
    _name = 'construction.rate.analysis'
    _description = 'Rate Analysis (Analisa Harga Satuan)'
    _inherit = ['mail.thread']
    _order = 'name'

    name = fields.Char(string='Name', required=True)
    code = fields.Char(string='Code')
    boq_line_id = fields.Many2one('construction.boq.line', string='BOQ Line')
    contract_id = fields.Many2one(
        'construction.job.contract', related='boq_line_id.contract_id',
        string='Contract', store=True,
    )
    currency_id = fields.Many2one(
        'res.currency', default=lambda self: self.env.company.currency_id,
    )
    uom_id = fields.Many2one('uom.uom', string='Output UoM')

    material_line_ids = fields.One2many(
        'construction.ra.material.line', 'ra_id', string='Material Components',
    )
    labor_line_ids = fields.One2many(
        'construction.ra.labor.line', 'ra_id', string='Labor Components',
    )
    equipment_line_ids = fields.One2many(
        'construction.ra.equipment.line', 'ra_id', string='Equipment Components',
    )

    total_material = fields.Monetary(string='Material Cost', compute='_compute_totals', store=True)
    total_labor = fields.Monetary(string='Labor Cost', compute='_compute_totals', store=True)
    total_equipment = fields.Monetary(string='Equipment Cost', compute='_compute_totals', store=True)
    total_unit_price = fields.Monetary(string='Total Unit Price', compute='_compute_totals', store=True)
    overhead_percent = fields.Float(string='Overhead (%)', default=0.0)
    profit_percent = fields.Float(string='Profit (%)', default=0.0)
    total_with_overhead = fields.Monetary(
        string='Total incl. OH & Profit', compute='_compute_totals', store=True,
    )

    notes = fields.Text(string='Notes')

    @api.depends(
        'material_line_ids.subtotal',
        'labor_line_ids.subtotal',
        'equipment_line_ids.subtotal',
        'overhead_percent', 'profit_percent',
    )
    def _compute_totals(self):
        for rec in self:
            mat = sum(rec.material_line_ids.mapped('subtotal'))
            lab = sum(rec.labor_line_ids.mapped('subtotal'))
            eqp = sum(rec.equipment_line_ids.mapped('subtotal'))
            base = mat + lab + eqp
            overhead_amount = base * rec.overhead_percent / 100
            profit_amount = base * rec.profit_percent / 100
            rec.total_material = mat
            rec.total_labor = lab
            rec.total_equipment = eqp
            rec.total_unit_price = base
            rec.total_with_overhead = base + overhead_amount + profit_amount

    def action_apply_to_boq(self):
        """Apply RA total unit price to linked BOQ line."""
        self.ensure_one()
        if self.boq_line_id:
            self.boq_line_id.unit_price_contract = self.total_with_overhead


class ConstructionRaMaterialLine(models.Model):
    _name = 'construction.ra.material.line'
    _description = 'RA Material Component'
    _order = 'sequence'

    sequence = fields.Integer(default=10)
    ra_id = fields.Many2one('construction.rate.analysis', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Material')
    name = fields.Char(string='Description', required=True)
    uom_id = fields.Many2one('uom.uom', string='UoM')
    coefficient = fields.Float(string='Coefficient', digits=(16, 4), default=1.0)
    unit_price = fields.Monetary(string='Unit Price')
    currency_id = fields.Many2one(
        'res.currency', related='ra_id.currency_id', store=True,
    )
    subtotal = fields.Monetary(string='Subtotal', compute='_compute_subtotal', store=True)

    @api.depends('coefficient', 'unit_price')
    def _compute_subtotal(self):
        for rec in self:
            rec.subtotal = rec.coefficient * rec.unit_price

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.name
            self.uom_id = self.product_id.uom_id
            self.unit_price = self.product_id.standard_price


class ConstructionRaLaborLine(models.Model):
    _name = 'construction.ra.labor.line'
    _description = 'RA Labor Component'
    _order = 'sequence'

    sequence = fields.Integer(default=10)
    ra_id = fields.Many2one('construction.rate.analysis', required=True, ondelete='cascade')
    name = fields.Char(string='Worker Type', required=True)
    uom_id = fields.Many2one('uom.uom', string='UoM')
    coefficient = fields.Float(string='Coefficient', digits=(16, 4), default=1.0)
    unit_price = fields.Monetary(string='Wage Rate')
    currency_id = fields.Many2one(
        'res.currency', related='ra_id.currency_id', store=True,
    )
    subtotal = fields.Monetary(string='Subtotal', compute='_compute_subtotal', store=True)

    @api.depends('coefficient', 'unit_price')
    def _compute_subtotal(self):
        for rec in self:
            rec.subtotal = rec.coefficient * rec.unit_price


class ConstructionRaEquipmentLine(models.Model):
    _name = 'construction.ra.equipment.line'
    _description = 'RA Equipment Component'
    _order = 'sequence'

    sequence = fields.Integer(default=10)
    ra_id = fields.Many2one('construction.rate.analysis', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Equipment')
    name = fields.Char(string='Equipment Name', required=True)
    uom_id = fields.Many2one('uom.uom', string='UoM')
    coefficient = fields.Float(string='Coefficient', digits=(16, 4), default=1.0)
    unit_price = fields.Monetary(string='Rental Rate')
    currency_id = fields.Many2one(
        'res.currency', related='ra_id.currency_id', store=True,
    )
    subtotal = fields.Monetary(string='Subtotal', compute='_compute_subtotal', store=True)

    @api.depends('coefficient', 'unit_price')
    def _compute_subtotal(self):
        for rec in self:
            rec.subtotal = rec.coefficient * rec.unit_price

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.name
            self.uom_id = self.product_id.uom_id
