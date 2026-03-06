{
    'name': 'Product Category Addons',
    'version': '18.0.1.0.0',
    'license': 'LGPL-3',
    'author': 'Usamah',
    'summary': 'Add sub categories to product categories',
    'depends': ['stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/product_category_view.xml',
        'views/product_template_view.xml',
    ],
    'installable': True,
    'application': False,
}