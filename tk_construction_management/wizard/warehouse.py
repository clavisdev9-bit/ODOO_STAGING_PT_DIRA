# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ProjectWarehouse(models.TransientModel):
    """Project Warehouse"""
    _name = 'project.warehouse'
    _description = "Project Warehouse"
    _rec_name = 'warehouse'

    warehouse = fields.Selection(
        [('create', 'Create new warehouse'), ('link', 'Use existing warehouse')],
        string=" ")
    warehouse_name = fields.Char()
    warehouse_code = fields.Char(size=5)
    warehouse_id = fields.Many2one('stock.warehouse')

    def action_submit_warehouse(self):
        """Process Warehouse"""
        active_id = self._context.get('active_id')
        project_id = self.env['tk.construction.project'].browse(active_id)
        if self.warehouse == 'create':
            parent_location_id = self.env['stock.location'].create({
                'name': self.warehouse_code,
                'usage': 'view'
            })
            location_id = self.env['stock.location'].create({
                'location_id': parent_location_id.id,
                'name': 'Stock',
                'usage': 'internal'
            })
            data = {
                'code': self.warehouse_code,
                'name': self.warehouse_name,
                'project_id': project_id.id,
                'lot_stock_id': location_id.id,
                'view_location_id': parent_location_id.id,
                'delivery_steps': 'ship_only',
                'reception_steps': 'one_step',
                'company_id': self.env.company.id,
            }
            warehouse_id = self.env['stock.warehouse'].create(data)
            project_id.warehouse_id = warehouse_id.id
        else:
            project_id.warehouse_id = self.warehouse_id.id
