{
    'name': 'Amazing Toy Show 2',
    'version': '18.0.1.0',
    'license': 'LGPL-3',
    'author': 'Usamah',
    'summary': 'Self order system for event Amazing Toy Show 2',
    'depends': ['stock','website'],
    'data': [
        'data/ir_sequence.xml',
        'security/ir.model.access.csv',
        'views/event_cashier_view.xml',
        'views/event_order_view.xml',
        'views/event_tenant_view.xml',
        'views/website_templates_cashier.xml',
        'views/website_templates_customer.xml',
        'views/website_templates_tenant.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'amazing_toy_show_2/static/src/css/style.css',
            'amazing_toy_show_2/static/src/js/event_cashier.js',
            'amazing_toy_show_2/static/src/js/event_customer.js',
            'amazing_toy_show_2/static/src/js/event_tenant.js',
        ],
    },
    'installable': True,
}