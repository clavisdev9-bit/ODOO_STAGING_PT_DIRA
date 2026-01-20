# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class ConstructionPartner(models.Model):
    """Construction Res Partner"""
    _inherit = 'res.partner'

    stack_holder = fields.Boolean(string="Stockholder")
