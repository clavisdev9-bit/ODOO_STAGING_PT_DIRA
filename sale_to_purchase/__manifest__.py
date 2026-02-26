{
    'name': 'Sale to Purchase',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'summary': 'Create Purchase Order from Sale Order',
    'depends': ['sale_management', 'purchase'],
    'data': [
        'views/sale_order_view.xml',
    ],
    'installable': True,
    'application': False,
}