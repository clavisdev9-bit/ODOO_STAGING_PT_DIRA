# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models


class ImportMaterial(models.TransientModel):
    """Import material"""
    _name = 'import.material'
    _description = "Import Material for Material Requisition"

    material_req_id = fields.Many2one('material.requisition')
    template_id = fields.Many2one(
        'construction.product.template')

    @api.model
    def default_get(self, fields_list):
        """Default get"""
        res = super().default_get(fields_list)
        res['material_req_id'] = self._context.get('active_id')
        return res

    def action_import_material(self):
        """Import Material"""
        self.material_req_id.material_line_ids = [(5, 0, 0)]
        for data in self.template_id.template_ids:
            record = {
                'material_id': data.product_id.id,
                'name': data.name,
                'material_req_id': self.material_req_id.id
            }
            self.env['material.requisition.line'].create(record)


class ImportMaterialSheet(models.Model):
    """Import Material Sheet"""
    _name = 'import.material.sheet'
    _description = "Import Material from Sheet"

    job_cost_id = fields.Many2one('job.costing')
    import_from = fields.Selection(
        [('from_material', 'From Material Requisition'), ('from_template', 'From Template')],
        default='from_material')
    template_id = fields.Many2one(
        'construction.product.template')
    material_req_id = fields.Many2one(
        'material.requisition', string="Material Requisition")

    @api.model
    def default_get(self, fields_list):
        """Default get"""
        res = super().default_get(fields_list)
        res['job_cost_id'] = self._context.get('active_id')
        return res

    def action_import_material(self):
        """Import Material"""
        self.job_cost_id.cost_material_ids = [(5, 0, 0)]
        if self.import_from == 'from_material':
            for data in self.material_req_id.material_line_ids:
                record = {
                    'material_id': data.material_id.id,
                    'name': data.name,
                    'job_costing_id': self.job_cost_id.id,
                    'job_type_id': data.job_type_id.id,
                    'sub_category_id': data.sub_category_id.id,
                }
                self.env['cost.material.line'].create(record)
        if self.import_from == 'from_template':
            for data in self.template_id.template_ids:
                record = {
                    'material_id': data.product_id.id,
                    'name': data.name,
                    'job_costing_id': self.job_cost_id.id
                }
                self.env['cost.material.line'].create(record)
