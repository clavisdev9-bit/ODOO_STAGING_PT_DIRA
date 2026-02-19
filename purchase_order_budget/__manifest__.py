{
    'name': 'Purchase Order Budget',
    'version': '1.0',
    'license': 'LGPL-3',
    'category': 'Sales',
    'description': """Add budget to Sales Order""",
    'depends': ['sale','account_budget'],
    'data': [
        'security/ir.model.access.csv',
        'views/purchase_order_view.xml',
        'views/budget_line_view.xml',
        'views/account_move_view.xml',
        'views/account_payment_view.xml',
        'views/hr_expense_sheet_view.xml',
        'wizard/account_move_confirm_view.xml'
    ],
    'installable': True,
    'application': True,
}