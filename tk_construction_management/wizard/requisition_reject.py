# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class RequisitionReject(models.TransientModel):
    """Requisition reject"""
    _name = 'requisition.reject'
    _description = "Requisition Reject Reason"

    name = fields.Char(default="Material Requisition Reason")
    reject_reason = fields.Text()
    allow_resubmit = fields.Boolean()

    def action_reject_requisition(self):
        """Reject Requisition"""
        active_id = self._context.get('active_id')
        material_req_id = self.env['material.requisition'].browse(active_id)
        material_req_id.reject_reason = self.reject_reason
        material_req_id.stage = 'reject'
        material_req_id.allow_resubmit = self.allow_resubmit
