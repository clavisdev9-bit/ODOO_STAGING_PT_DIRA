# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from .construction_boq_line import CATEGORY_SELECTION



class ConstructionSiteBoq(models.Model):
    _inherit = 'tk.construction.site'

    # Client / owner info
    partner_id = fields.Many2one('res.partner', string='Owner / Client', tracking=True)
    project_manager_id = fields.Many2one('res.users', string='Project Manager', tracking=True)
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account')
    category = fields.Selection(CATEGORY_SELECTION, string='Divisi', tracking=True)

    # Currency
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        store=True,
        readonly=True,
    )

    # Sale order link
    sale_order_id = fields.Many2one('sale.order', string='Sale Order', readonly=True)
    contract_value = fields.Monetary(string='Contract Value', currency_field='currency_id')

    # BOQ lines
    boq_line_ids = fields.One2many('construction.boq.line', 'site_id', string='BOQ Lines')

    # Computed totals
    total_rab = fields.Monetary(
        string='Total RAB',
        compute='_compute_boq_totals',
        store=True,
        currency_field='currency_id',
    )
    total_realisasi = fields.Monetary(
        string='Total Realisasi',
        compute='_compute_boq_totals',
        store=True,
        currency_field='currency_id',
    )
    boq_progress = fields.Float(
        string='Progress (%)',
        compute='_compute_boq_totals',
        store=True,
    )

    # Smart button counts
    sale_order_count = fields.Integer(compute='_compute_boq_counts')
    boq_purchase_order_count = fields.Integer(compute='_compute_boq_counts')
    so_invoice_count = fields.Integer(compute='_compute_boq_counts')

    @api.depends('boq_line_ids.subtotal_plan', 'boq_line_ids.subtotal_actual')
    def _compute_boq_totals(self):
        for rec in self:
            rec.total_rab = sum(rec.boq_line_ids.mapped('subtotal_plan'))
            rec.total_realisasi = sum(rec.boq_line_ids.mapped('subtotal_actual'))
            if rec.total_rab:
                rec.boq_progress = (rec.total_realisasi / rec.total_rab) * 100.0
            else:
                rec.boq_progress = 0.0

    def _compute_boq_counts(self):
        for rec in self:
            rec.sale_order_count = 1 if rec.sale_order_id else 0
            po_ids = rec.boq_line_ids.mapped('purchase_line_ids.order_id').ids
            rec.boq_purchase_order_count = len(set(po_ids))
            invoice_count = 0
            if rec.sale_order_id:
                invoice_count = self.env['account.move'].search_count([
                    ('invoice_origin', 'like', rec.sale_order_id.name),
                    ('move_type', 'in', ['out_invoice', 'out_refund']),
                ])
            rec.so_invoice_count = invoice_count

    # Actions
    def action_view_sale_order(self):
        self.ensure_one()
        if not self.sale_order_id:
            return
        return {
            'type': 'ir.actions.act_window',
            'name': _('Sale Order'),
            'res_model': 'sale.order',
            'res_id': self.sale_order_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_view_boq_purchase_orders(self):
        self.ensure_one()
        po_ids = self.boq_line_ids.mapped('purchase_line_ids.order_id').ids
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Orders'),
            'res_model': 'purchase.order',
            'domain': [('id', 'in', po_ids)],
            'view_mode': 'list,form',
            'target': 'current',
        }

    def action_view_so_invoices(self):
        self.ensure_one()
        domain = []
        if self.sale_order_id:
            domain = [
                ('invoice_origin', 'like', self.sale_order_id.name),
                ('move_type', 'in', ['out_invoice', 'out_refund']),
            ]
        return {
            'type': 'ir.actions.act_window',
            'name': _('SO Invoices'),
            'res_model': 'account.move',
            'domain': domain,
            'view_mode': 'list,form',
            'target': 'current',
        }

    def action_generate_sale_order(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Generate Sale Order'),
            'res_model': 'wizard.construction.generate.so',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_site_id': self.id,
                'default_partner_id': self.partner_id.id if self.partner_id else False,
            },
        }

    def action_open_generate_po_wizard(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Generate Purchase Order'),
            'res_model': 'wizard.construction.generate.po',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_site_id': self.id,
            },
        }

    # -------------------------------------------------------------------------
    # Analytic Account → Project sync
    # -------------------------------------------------------------------------

    def _sync_analytic_to_project(self):
        """Create or update a project.project linked to this site's analytic account.

        Uses account_id as the link key between account.analytic.account and
        project.project (field added by hr_timesheet).  If a project already
        has account_id pointing to this analytic account, its name / partner_id
        are refreshed.  If no project exists yet, one is created.

        Passing account_id to project.create() suppresses Odoo's built-in
        analytic account auto-creation, so there is no recursion risk.
        """
        self.ensure_one()
        aa = self.analytic_account_id
        if not aa:
            return

        Project = self.env['project.project']
        ctx = dict(self.env.context, _skip_analytic_project_sync=True)

        project = Project.search([('account_id', '=', aa.id)], limit=1)
        sync_vals = {
            'name': aa.name,
            'partner_id': aa.partner_id.id or False,
            'allow_timesheets': True,
        }

        if project:
            project.with_context(ctx).write(sync_vals)
        else:
            # Providing account_id prevents hr_timesheet from creating a
            # second analytic account inside project.create().
            Project.with_context(ctx).create({
                **sync_vals,
                'account_id': aa.id,
            })

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records.filtered('analytic_account_id'):
            rec._sync_analytic_to_project()
        return records

    def write(self, vals):
        result = super().write(vals)
        # Only act when analytic_account_id is being set (not cleared)
        if vals.get('analytic_account_id'):
            for rec in self:
                if rec.analytic_account_id:
                    rec._sync_analytic_to_project()
        return result
