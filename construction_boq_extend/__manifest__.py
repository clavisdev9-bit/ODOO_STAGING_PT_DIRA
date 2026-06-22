# -*- coding: utf-8 -*-
{
    'name': 'Construction BOQ Extend',
    'version': '18.0.1.0.0',
    'summary': 'Extends Construction Site with BOQ (Bill of Quantities) management',
    'category': 'Construction',
    'depends': [
        'tk_construction_management',
        'sale_management',
        'purchase',
        'account',
        'analytic',
        'uom',
    ],
    'data': [
        'security/ir.model.access.csv',
        'views/construction_boq_views.xml',
        'report/boq_report.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
