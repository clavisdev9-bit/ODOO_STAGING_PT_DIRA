# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
from odoo import models


class ConstructionEmployee(models.Model):
    """Construction Employee"""
    _inherit = "hr.employee"
