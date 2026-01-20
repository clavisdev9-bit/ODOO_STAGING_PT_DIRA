# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
from odoo import fields, models, _


class ConstructionPurchase(models.Model):
    """Construction Purchase Order"""
    _inherit = 'purchase.order'

    material_req_id = fields.Many2one(
        'material.requisition', string="Material Requisition")
    job_order_id = fields.Many2one('job.order', string="Work order")
    purchase_order = fields.Selection([('equipment', 'Equipment'),
                                       ('labour', 'Labour'),
                                       ('overhead', 'Overhead')],
                                      string="Source Ref.")
    equipment_subcontract_id = fields.Many2one(
        'equipment.subcontract', string="Subcontract")
    labour_subcontract_id = fields.Many2one(
        'labour.subcontract', string="Subcontract ")
    overhead_subcontract_id = fields.Many2one(
        'overhead.subcontract', string="Subcontract  ")

    def _prepare_invoice(self):
        """Prepare Invoice Lines"""
        res = super(ConstructionPurchase, self)._prepare_invoice()
        if self.material_req_id:
            res['material_req_id'] = self.material_req_id.id
        if self.job_order_id:
            res['job_order_id'] = self.job_order_id.id
            res['purchase_order'] = self.purchase_order
            res['equipment_subcontract_id'] = self.equipment_subcontract_id.id
            res['labour_subcontract_id'] = self.labour_subcontract_id.id
            res['overhead_subcontract_id'] = self.overhead_subcontract_id.id
        return res


class ConstructionBills(models.Model):
    """Construction Bills"""
    _inherit = 'account.move'

    material_req_id = fields.Many2one(
        'material.requisition', string="Material Requisition")
    project_id = fields.Many2one(related="material_req_id.project_id", string="Sub Project",
                                 store=True)
    job_order_id = fields.Many2one('job.order', string="Work order")
    purchase_order = fields.Selection(
        [('equipment', 'Equipment'), ('labour', 'Labour'), ('overhead', 'Overhead')],
        string="Source Ref.")
    equipment_subcontract_id = fields.Many2one(
        'equipment.subcontract', string="Subcontract")
    labour_subcontract_id = fields.Many2one(
        'labour.subcontract', string="Subcontract ")
    overhead_subcontract_id = fields.Many2one(
        'overhead.subcontract', string="Subcontract  ")
    progress_bill_id = fields.Many2one(
        'progress.billing', string="Progress Bill Ref.")
    bill_of = fields.Char(string="Bill Ref.")


class ConstructionProduct(models.Model):
    """Construction Products"""
    _inherit = 'product.product'

    last_po_price = fields.Monetary(string="Last Purchase Price")
    is_material = fields.Boolean()
    is_equipment = fields.Boolean()
    is_labour = fields.Boolean()
    is_overhead = fields.Boolean()
    is_expense = fields.Boolean()


class ConstructionWarehouse(models.Model):
    """Construction Warehouse"""
    _inherit = 'stock.warehouse'

    project_id = fields.Many2one('tk.construction.project', string="Project")
    consume_stock_location_id = fields.Many2one(
        'stock.location', string="Consume Location")


class ConstructionDelivery(models.Model):
    """"Construction Delivery Orders"""
    _inherit = 'stock.picking'

    code = fields.Selection(
        related='picking_type_id.code', store=True, string="Code ")
    transfer_id = fields.Many2one('internal.transfer', string="Transfer Ref.")
    consume_order_id = fields.Many2one(
        'job.order', string="Consume Order Ref.")
    material_consume_id = fields.Many2one(
        'material.consume', string="Material Consume Ref.")

    def button_validate(self):
        """Construction Validate"""
        res = super().button_validate()
        if res is not True:
            return res
        if self.transfer_id:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Internal Transfer'),
                'res_model': 'internal.transfer',
                'res_id': self.transfer_id.id,
                'view_mode': 'form',
                'target': 'current'
            }
        return res
