# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
from odoo import fields, models


class DocumentType(models.Model):
    """Document Types"""
    _name = 'site.document.type'
    _description = "Project Document Type"

    name = fields.Char(string="Title")


class JobType(models.Model):
    """Work Types"""
    _name = 'job.type'
    _description = "Activity"

    name = fields.Char(string="Title")
    sub_category_ids = fields.Many2many(
        'job.sub.category', string="Work Sub Type")


class JobSubCategory(models.Model):
    """Work sub types"""
    _name = 'job.sub.category'
    _description = "Sub Activity"

    name = fields.Char(string="Title")


class InsuranceRisk(models.Model):
    """Insurance Risks"""
    _name = 'insurance.risk'
    _description = "Insurance Risk"

    name = fields.Char(string="Risk")
