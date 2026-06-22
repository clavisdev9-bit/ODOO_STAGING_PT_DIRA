{
    'name': 'S-Curve Project Monitoring',
    'version': '18.0.1.0.0',
    'category': 'Project',
    'summary': 'Native S-Curve monitoring dashboard for construction projects',
    'description': """
        Native S-Curve monitoring dashboard for construction projects.
        Tracks Planned vs Actual cumulative work weight (BCR/BCA) per week
        and milestone, with deviation alerts and linear completion forecast.
        Eliminates manual Excel export/import workflow.
    """,
    'author': 'Your Company',
    'license': 'LGPL-3',
    'depends': ['project', 'hr_timesheet', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/project_task_views.xml',
        'views/project_views.xml',
        'views/scurve_dashboard_views.xml',
    ],
    'demo': [
        'data/demo_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'project_scurve/static/src/components/scurve_dashboard/scurve_dashboard.scss',
            'project_scurve/static/src/components/scurve_dashboard/scurve_dashboard.js',
            'project_scurve/static/src/components/scurve_dashboard/scurve_dashboard.xml',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}
