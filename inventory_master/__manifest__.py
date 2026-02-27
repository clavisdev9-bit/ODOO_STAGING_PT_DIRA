{
    'name': 'Dira Inventory Master',
    'version': '18.0.1.0.0',
    'category': 'Inventory',
    'summary': 'Master Data Material (Brand, Sub Category, Spesifikasi) untuk PT Duta Indo Raya',
    'depends': ['base', 'stock', 'product'],
    'data': [
        'security/ir.model.access.csv',
        'views/master_material_views.xml',
        'views/product_template_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}