{
    'name': 'Amazing Toys SOS Integration',
    'version': '18.0.1.0.0',
    'summary': 'Self-Ordering System to Odoo Sales Order integration',
    'author': 'ST Corp',
    'category': 'Sales/Sales',
    'depends': ['sale_stock', 'account', 'stock', 'base_automation', 'mail', 'base_setup'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_sequence.xml',
        'data/automated_actions.xml',
        'views/sale_order_views.xml',
        'views/res_config_settings_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
