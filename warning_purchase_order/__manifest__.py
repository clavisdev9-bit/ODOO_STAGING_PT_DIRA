{
    'name': 'Warning Purchase Order',
    'version': '1.0',
    'license': 'LGPL-3',
    'author': 'Usamah',
    'category': '',
    'description': """Add a warning in Purchase Order when Fiscal position in vendor is empty""",
    'depends': ['base','purchase'],
    'data': [
        'views/purchase_order_view.xml',
    ],
    'installable': True,
    'application': True,
}