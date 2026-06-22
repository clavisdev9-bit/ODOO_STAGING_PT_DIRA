{
    'name': 'TMS Integration',
    'version': '18.0.1.0.0',
    'category': 'Inventory/Delivery',
    'summary': 'Transport Management System integration with Odoo 18',
    'description': """
        TMS + Odoo 18 Integration Add-on
        ================================
        Custom add-on untuk integrasi bi-directional antara TMS dan Odoo 18.

        Features:
        - 7 trigger points otomatis (SO → Invoice)
        - Custom fields pada stock.picking, fleet.vehicle, product
        - Webhook endpoints /tms/webhook/*
        - Auto-create hr.expense dari delivery
        - Auto-validate picking & create invoice saat delivery complete
        - Sync log untuk audit trail
    """,
    'author': 'TMS Dev Team',
    'website': 'https://tms.perusahaan.com',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'sale_management',
        'stock',
        'fleet',
        'hr_expense',
        'account',
        'delivery',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/tms_config_data.xml',
        'views/stock_picking_views.xml',
        'views/sale_order_views.xml',
        'views/fleet_vehicle_views.xml',
        'views/product_template_views.xml',
        'views/tms_sync_log_views.xml',
        'views/menu.xml',
    ],
    'assets': {},
    'installable': True,
    'application': False,
    'auto_install': False,
}
