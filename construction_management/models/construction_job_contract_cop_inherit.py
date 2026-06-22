from odoo import models, fields, api


class ConstructionJobContractCop(models.Model):
    _inherit = 'construction.job.contract'

    cop_line_ids = fields.One2many('cop.line', 'contract_id', string='COP Lines')
    cop_total = fields.Monetary(
        string='COP Total', compute='_compute_cop_total', store=True,
    )

    @api.depends('cop_line_ids.subtotal_cop')
    def _compute_cop_total(self):
        for rec in self:
            rec.cop_total = sum(rec.cop_line_ids.mapped('subtotal_cop'))

    def action_copy_boq_to_cop(self):
        self.ensure_one()
        self.cop_line_ids.unlink()
        cop_vals = [
            {
                'contract_id': self.id,
                'boq_line_id': boq.id,
                'sequence': boq.sequence,
                'code': boq.code,
                'cop_name': boq.name,
                'product_id': boq.product_id.id if boq.product_id else False,
                'uom_id': boq.uom_id.id,
                'volume_contract': boq.volume_contract,
                'unit_price_contract': boq.unit_price_contract,
                'volume_actual': boq.volume_contract,
                'unit_price_actual': boq.unit_price_contract,
                'weight_percent': boq.weight_percent,
                'progress_physical': boq.progress_physical,
                'rate_analysis_id': boq.rate_analysis_id.id if boq.rate_analysis_id else False,
            }
            for boq in self.boq_line_ids
        ]
        if cop_vals:
            self.env['cop.line'].create(cop_vals)
