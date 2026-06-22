# -*- coding: utf-8 -*-
{
    'name': 'AI Report Agent',
    'version': '18.0.1.2.0',
    'category': 'Reporting',
    'summary': 'Natural Language → Structured Report Generator powered by AI',
    'description': """
        AI Report Agent converts natural language queries into structured Odoo reports.
        Supports PDF and Excel output for Sales, Invoice, Inventory, Purchase, and Summary reports.
        Configurable LLM provider (Anthropic Claude, OpenAI, Ollama, Custom HTTP).
        Includes async queue for large datasets and MCP bridge for external AI agent integration.
    """,
    'author': 'Clavis Development',
    'website': '',
    'license': 'LGPL-3',
    'depends': [
        'base',
        'mail',
        'account',
        'sale',
        'stock',
        'purchase',
    ],
    'external_dependencies': {
        'python': ['dateutil'],  # openpyxl/anthropic/openai are lazy-imported per provider
    },
    'data': [
        'security/ir.model.access.csv',
        'views/ai_report_config_view.xml',
        'views/ai_report_history_view.xml',
        'views/ai_report_queue_view.xml',
        'views/report_preview_wizard_view.xml',
        'views/menu_views.xml',
        'templates/report_templates.xml',
        'data/default_config.xml',
        'data/cron_data.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'ai_report_agent/static/src/xml/ai_report_components.xml',
            'ai_report_agent/static/src/js/ai_report_button.js',
            'ai_report_agent/static/src/xml/ai_chat.xml',
            'ai_report_agent/static/src/js/ai_chat.js',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'images': [],
}
