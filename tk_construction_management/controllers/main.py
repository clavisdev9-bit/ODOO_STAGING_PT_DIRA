# -*- coding: utf-8 -*-
# Copyright 2020-Today TechKhedut.
# Part of TechKhedut. See LICENSE file for full copyright and licensing details.

import logging
from datetime import datetime

from odoo.http import request, route
from odoo import http, tools, _, fields

_logger = logging.getLogger(__name__)


class ProjectGantt(http.Controller):
    @http.route('/get/project-gantt/data', type='json', auth='user')
    def _get_project_gantt_data(self, **kw):
        project_record = request.env['tk.construction.site'].sudo().search(
            [('id', '=', kw.get('id'))])

        # Get date filter parameters
        start_date_str = kw.get('start_date')
        end_date_str = kw.get('end_date')

        # Convert string dates to datetime objects if provided
        start_date = fields.Date.from_string(start_date_str) if start_date_str else None
        end_date = fields.Date.from_string(end_date_str) if end_date_str else None

        data = []
        links = []  # Add links array
        project_count = 1
        link_count = 1  # Counter for link IDs

        if project_record:
            if self._is_date_in_range(project_record.start_date, project_record.end_date,
                                      start_date, end_date):
                data.append({
                    "id": project_count,
                    "text": project_record.name,
                    "code": project_record.id,
                    "model": 'tk.construction.site',
                    "open": True,
                    "start_date": project_record.start_date.strftime(
                        "%d-%m-%Y") if project_record.start_date else None,
                    "duration": self._calculate_duration(project_record.start_date,
                                                         project_record.end_date),
                    "progress": 0.8,
                    "color": "#8F87F1",
                    "prop": "sale"
                })
                project_node_id = project_count
                project_count += 1

                # Get sub-projects
                sub_projects = request.env['tk.construction.project'].sudo().search(
                    [('construction_site_id', '=', project_record.id)])

                if sub_projects:
                    for sub_project in sub_projects:
                        if self._is_date_in_range(sub_project.start_date, sub_project.end_date,
                                                  start_date, end_date):
                            data.append({
                                "id": project_count,
                                "text": sub_project.name,
                                "code": sub_project.id,
                                "model": 'tk.construction.project',
                                "open": True,
                                "start_date": sub_project.start_date.strftime(
                                    "%d-%m-%Y") if sub_project.start_date else None,
                                "duration": self._calculate_duration(sub_project.start_date,
                                                                     sub_project.end_date),
                                "progress": 0.8,
                                "parent": project_node_id,
                                "color": "#C68EFD",
                            })

                            # Add link from project to sub-project
                            links.append({
                                "id": link_count,
                                "source": project_node_id,
                                "target": project_count,
                                "type": "0",
                                "color": "#8F87F1"
                            })
                            link_count += 1

                            sub_project_id = project_count
                            project_count += 1

                            # Get job costings
                            job_costings = request.env['job.costing'].sudo().search([
                                ('project_id', '=', sub_project.id)
                            ])

                            if job_costings:
                                for job_costing in job_costings:
                                    # Only add job costing if it falls within date range
                                    if self._is_date_in_range(job_costing.start_date,
                                                              job_costing.close_date, start_date,
                                                              end_date):
                                        data.append({
                                            "id": project_count,
                                            "text": job_costing.name,
                                            "code": job_costing.id,
                                            "model": 'job.costing',
                                            "open": True,
                                            "start_date": job_costing.start_date.strftime(
                                                "%d-%m-%Y") if job_costing.start_date else None,
                                            "duration": self._calculate_duration(
                                                job_costing.start_date, job_costing.close_date),
                                            "progress": 0.8,
                                            "parent": sub_project_id,
                                            "color": "#E9A5F1",
                                        })

                                        # Add link from sub-project to job costing
                                        links.append({
                                            "id": link_count,
                                            "source": sub_project_id,
                                            "target": project_count,
                                            "type": "0",
                                            "color": "#C68EFD",
                                        })
                                        link_count += 1

                                        job_costing_id = project_count
                                        project_count += 1

                                        # Get job orders
                                        job_orders = request.env['job.order'].sudo().search([
                                            ('job_sheet_id', '=', job_costing.id)
                                        ])

                                        if job_orders:
                                            for job_order in job_orders:
                                                # Only add job order if it falls within date range
                                                if self._is_date_in_range(job_order.start_date,
                                                                          job_order.end_date,
                                                                          start_date, end_date):
                                                    data.append({
                                                        "id": project_count,
                                                        "text": job_order.name,
                                                        "code": job_order.id,
                                                        "model": 'job.order',
                                                        "open": True,
                                                        "start_date": job_order.start_date.strftime(
                                                            "%d-%m-%Y") if job_order.start_date else None,
                                                        "duration": self._calculate_duration(
                                                            job_order.start_date,
                                                            job_order.end_date),
                                                        "progress": 0.8,
                                                        "parent": job_costing_id,
                                                        "color": "#FED2E2",
                                                    })

                                                    # Add link from job costing to job order
                                                    links.append({
                                                        "id": link_count,
                                                        "source": job_costing_id,
                                                        "target": project_count,
                                                        "type": "0",
                                                        "color": "#E9A5F1",
                                                    })
                                                    link_count += 1

                                                    project_count += 1
        return {
            "data": data,
            "links": links
        }

    def _is_date_in_range(self, item_start_date, item_end_date, filter_start_date, filter_end_date):
        """
        Check if an item's date range overlaps with the filter date range.
        Returns True if there's any overlap or if no filter dates are provided.
        """
        if not filter_start_date or not filter_end_date:
            return True

        if not item_start_date or not item_end_date:
            return False

        return not (item_end_date < filter_start_date or item_start_date > filter_end_date)

    def _calculate_duration(self, start_date, end_date):
        """
        Calculate duration in days between two dates.
        Returns 0 if either date is missing.
        """
        if not start_date or not end_date:
            return 0
        return (end_date - start_date).days
