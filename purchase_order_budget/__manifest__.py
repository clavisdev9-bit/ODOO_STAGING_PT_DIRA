{
    'name': 'Purchase Order Budget',
    'version': '1.0',
    'category': 'Sales',
    'description': """Add budget to Sales Order""",
    'depends': ['sale'],
    'data': [
        'security/ir.model.access.csv',
        'views/purchase_order_view.xml',
        'views/budget_line_view.xml'
    ],
    'installable': True,
    'application': True,
}