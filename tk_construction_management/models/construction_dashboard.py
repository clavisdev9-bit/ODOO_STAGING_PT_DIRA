# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _


class ConstructionDashboard(models.Model):
    """Construction Dashboard"""
    _name = 'tk.construction.dashboard'
    _description = "Construction Dashboard"

    name = fields.Char()

    @api.model
    def get_construction_state(self, site_id, project_id):
        """Get construction state"""
        site_domain = []
        project_domain = []
        internal_site_domain = []
        if (not site_id and not project_id) or (
                site_id == 'all_site' and project_id == 'all_project'):
            pass
        elif not site_id == 'all_site' and (project_id == 'all_project' or project_id == None):
            site_domain = [('construction_site_id', '=', int(site_id))]
            internal_site_domain = [('site_id', '=', int(site_id))]
            projects = self.env['tk.construction.project'].search(
                site_domain).mapped('id')
            project_domain = [('project_id', 'in', projects)]
        elif site_id and project_id:
            site_domain = [('construction_site_id', '=', int(site_id))]
            internal_site_domain = [('site_id', '=', int(site_id))]
            project_domain = [('project_id', '=', int(project_id))]
        # Project
        total_site = self.env['tk.construction.site'].search_count([])
        total_project = self.env['tk.construction.project'].search_count(
            site_domain)
        total_mrq = self.env['material.requisition'].search_count(
            project_domain)
        job_sheet_count = self.env['job.costing'].search_count(project_domain)
        job_order_count = self.env['job.order'].search_count(project_domain)
        budget_count = self.env['sub.project.budget'].search_count([])

        # Sub Project
        sub_project_status = self.get_project_status(site_domain)

        # Material Requisition
        material_req_state = self.get_mrq_state(project_domain)
        back_order = self.env['material.requisition'].sudo().search_count(
            [('is_back_order', '=', True)] + project_domain)

        # Internal Transfer
        internal_state = self.get_it_state(internal_site_domain)
        forward_transfer = self.env['internal.transfer'].sudo().search_count(
            [('is_forward_transfer', '=', True)] + internal_site_domain)

        # Purchase Order
        purchase_order = self.get_purchase_order_state(project_domain)

        return {
            # Project
            'total_site': total_site,
            'total_project': total_project,
            'total_mrq': total_mrq,
            'job_sheet_count': job_sheet_count,
            'job_order_count': job_order_count,
            'con_sites': self.get_site_list(),
            'budget': budget_count,
            # Project Status
            'project_planning': sub_project_status[1][0],
            'project_procurement': sub_project_status[1][1],
            'project_construction': sub_project_status[1][2],
            'project_handover': sub_project_status[1][3],
            # MRE Status
            'mr_draft': material_req_state[1][0],
            'mr_waiting_approval': material_req_state[1][1],
            'mr_approved': material_req_state[1][2],
            'mr_ready_delivery': material_req_state[1][3],
            'mr_material_arrive': material_req_state[1][4],
            'mr_internal_transfer': material_req_state[1][5],
            'back_order': back_order,
            # Internal Transfer Status
            'it_draft': internal_state[1][0],
            'it_in_progress': internal_state[1][1],
            'it_done': internal_state[1][2],
            'forward_transfer': forward_transfer,
            # PO
            'mr_po': purchase_order['mr_po'],
            'equip_po': purchase_order['equip_po'],
            'labour_po': purchase_order['labour_po'],
            'overhead_po': purchase_order['overhead_po'],
            # Graph
            'site_timeline': self.construction_time_line(),
            'site_state': self.get_site_state(),
            'project_timeline': self.project_time_line(site_domain),
            'project_status': sub_project_status,
            'mrq_state': material_req_state,
            'internal_state': internal_state,
            'purchase_order': purchase_order,
            'job_order_po': self.get_purchase_order(project_domain),
        }

    @api.model
    def get_project_list(self, site_domain):
        """Get project list"""
        projects = {}
        if not site_domain == 'all_site':
            domain = [('construction_site_id', '=', int(site_domain))]
            project_obj = self.env['tk.construction.project'].sudo()
            for rec in project_obj.search(domain):
                projects[rec.id] = rec.name
            return projects
        if site_domain == 'all_site':
            return projects

    def get_site_list(self):
        """Get site list"""
        site_obj = self.env['tk.construction.site'].sudo()
        sites = {}
        for rec in site_obj.search([]):
            sites[rec.id] = rec.name
        return sites

    def get_mrq_state(self, project_domain):
        """Get MREQ state"""
        material_requisition = self.env['material.requisition'].sudo()
        draft = material_requisition.search_count(
            [('stage', '=', 'draft')] + project_domain)
        waiting_approval = material_requisition.search_count(
            [('stage', '=', 'department_approval')] + project_domain)
        approved = material_requisition.search_count(
            [('stage', '=', 'approve')] + project_domain)
        ready_delivery = material_requisition.search_count(
            [('stage', '=', 'ready_delivery')] + project_domain)
        material_arrive = material_requisition.search_count(
            [('stage', '=', 'material_arrived')] + project_domain)
        internal_transfer = material_requisition.search_count(
            [('stage', '=', 'internal_transfer')] + project_domain)
        reject = material_requisition.search_count(
            [('stage', '=', 'reject')] + project_domain)
        cancel = material_requisition.search_count(
            [('stage', '=', 'cancel')] + project_domain)
        return [
            ['Draft', 'Waiting Approval', 'In Progress', 'Ready Delivery', 'Material Arrive',
             'Internal Transfer',
             'Reject', 'Cancel'],
            [draft, waiting_approval, approved, ready_delivery,
             material_arrive, internal_transfer, reject, cancel]
        ]

    def get_site_state(self):
        """Get constriction site state"""
        site = self.env['tk.construction.site'].sudo()
        draft = site.search_count([('status', '=', 'draft')])
        in_progress = site.search_count([('status', '=', 'in_progress')])
        done = site.search_count([('status', '=', 'complete')])
        return [
            ['Draft', 'In Progress', 'Complete'], [draft, in_progress, done]
        ]

    def get_it_state(self, site_domain):
        """Get Internal transfer state"""
        internal_transfer = self.env['internal.transfer'].sudo()
        draft = internal_transfer.search_count(
            [('stage', '=', 'draft')] + site_domain)
        in_progress = internal_transfer.search_count(
            [('stage', '=', 'in_progress')] + site_domain)
        done = internal_transfer.search_count(
            [('stage', '=', 'done')] + site_domain)
        return [
            ['Draft', 'In Progress', 'Done'], [draft, in_progress, done]
        ]

    def construction_time_line(self):
        """Construction time lines"""
        site_data = []
        construction_site_data = self.env['tk.construction.site'].search([])
        for site in construction_site_data:
            if site.status == "in_progress":
                site_data.append({
                    'name': site.name,
                    'start_date': str(site.start_date),
                    'end_date': str(site.end_date),
                })
        return site_data

    def project_time_line(self, site_domain):
        """Construction project timeline"""
        data = []
        project_data = self.env['tk.construction.project'].search(site_domain)
        for p in project_data:
            if p.stage == "Construction":
                data.append({
                    'name': str(p.name) + " - " + str(p.construction_site_id.name),
                    'start_date': str(p.start_date),
                    'end_date': str(p.end_date),
                })
        return data

    def get_project_status(self, site_domain):
        """Get project status"""
        project_obj = self.env['tk.construction.project'].sudo()
        planning = project_obj.search_count(
            [('stage', '=', 'Planning')] + site_domain)
        procurement = project_obj.search_count(
            [('stage', '=', 'Procurement')] + site_domain)
        construction = project_obj.search_count(
            [('stage', '=', 'Construction')] + site_domain)
        handover = project_obj.search_count(
            [('stage', '=', 'Handover')] + site_domain)
        return [
            ['Planning', 'Procurement', 'Construction', 'Handover'],
            [planning, procurement, construction, handover]
        ]

    def get_purchase_order(self, project_domain):
        """Get purchase order"""
        jo_order = []
        mrq_po = []
        equip_po = []
        labour_po = []
        overhead_po = []
        job_order = self.env['job.order'].sudo().search(project_domain)
        for j in job_order:
            if j.project_id.stage == "Construction":
                name = str(j.name) + " - " + str(j.title)
                jo_order.append(name)
                mrq_po.append(j.material_req_id.po_count)
                equip_po.append(j.equip_po_count)
                labour_po.append(j.labour_po_count)
                overhead_po.append(j.overhead_po_count)
        data = [jo_order, mrq_po, equip_po, labour_po, overhead_po]
        return data

    def get_purchase_order_state(self, project_domain):
        """Get purchase order state"""
        domain = project_domain
        po_obj = self.env['purchase.order'].sudo()
        mr_po = 0
        equip_po = 0
        labour_po = 0
        overhead_po = 0
        job_orders = self.env['job.order'].search(domain)
        for rec in job_orders:
            equip_po = equip_po + po_obj.search_count(
                [('job_order_id', '=', rec.id), ('purchase_order', '=', 'equipment')])
            labour_po = labour_po + po_obj.search_count(
                [('job_order_id', '=', rec.id), ('purchase_order', '=', 'labour')])
            overhead_po = overhead_po + po_obj.search_count(
                [('job_order_id', '=', rec.id), ('purchase_order', '=', 'overhead')])
            mr_po = mr_po + po_obj.search_count(
                [('material_req_id', '=', rec.material_req_id.id)])
        return {
            'mr_po': mr_po,
            'equip_po': equip_po,
            'labour_po': labour_po,
            'overhead_po': overhead_po,
        }

    @api.model
    def get_construction_project_domain(self, site_id, project_id):
        """Get construction project domain"""
        site_domain = []
        project_domain = []
        if (not site_id and not project_id) or (
                site_id == 'all_site' and project_id == 'all_project'):
            pass
        elif not site_id == 'all_site' and (project_id == 'all_project' or project_id == None):
            site_domain = [('construction_site_id', '=', int(site_id))]
            projects = self.env['tk.construction.project'].search(
                site_domain).mapped('id')
            project_domain = [('project_id', 'in', projects)]
        elif site_id and project_id:
            site_domain = [('construction_site_id', '=', int(site_id))]
            project_domain = [('project_id', '=', int(project_id))]
        return [site_domain, project_domain]

    @api.model
    def get_job_order_po(self, site_id, project_id, source):
        """Get job order po"""
        project_domain = []
        if site_id == 'all_site':
            pass
        elif not site_id == 'all_site' and project_id == 'all_project':
            site_domain = [('construction_site_id', '=', int(site_id))]
            projects = self.env['tk.construction.project'].search(
                site_domain).mapped('id')
            project_domain = [('project_id', 'in', projects)]
        elif site_id and project_id:
            project_domain = [('project_id', '=', int(project_id))]
        ids = []
        po_obj = self.env['purchase.order'].sudo()
        for data in self.env['job.order'].search(project_domain):
            if source == 'equip':
                ids = ids + po_obj.search(
                    [('job_order_id', '=', data.id), ('purchase_order', '=', 'equipment')]).mapped(
                    'id')
            if source == 'labour':
                ids = ids + po_obj.search(
                    [('job_order_id', '=', data.id), ('purchase_order', '=', 'labour')]).mapped(
                    'id')
            if source == 'overhead':
                ids = ids + po_obj.search(
                    [('job_order_id', '=', data.id), ('purchase_order', '=', 'overhead')]).mapped(
                    'id')
            if source == 'material':
                ids = ids + po_obj.search(
                    [('material_req_id', '=', data.material_req_id.id)]).mapped('id')
        return ids
