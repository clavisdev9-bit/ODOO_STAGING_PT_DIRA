# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ConstructionResConfig(models.TransientModel):
    """Construction Res Config"""
    _inherit = 'res.config.settings'

    phase_prefix = fields.Char(default="PHASE/",
                               config_parameter='tk_construction_management.phase_prefix')

    timesheet_product_id = fields.Many2one(
        'product.product',
        default=lambda self: self.env.ref('tk_construction_management.construction_product_2',
                                          raise_if_not_found=False),
        config_parameter='tk_construction_management.construction_timesheet_product_id')
