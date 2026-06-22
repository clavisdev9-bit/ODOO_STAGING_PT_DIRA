{
    'name': 'Clavis AI',
    'version': '18.0.1.0.0',
    'category': 'Productivity',
    'summary': 'AI Agent Orchestrator for Odoo 18 — LangChain + FastAPI',
    'description': """
        Clavis AI integrates Odoo 18 with a FastAPI-based LangChain orchestrator.

        Features:
        - Intelligent chat assistant embedded in the Odoo backend
        - Customer lookups, quotation creation, and order queries via natural language
        - Async polling architecture (non-blocking LLM calls)
        - Full audit log of every AI interaction
        - Pluggable LLM backend: OpenAI GPT-4o or Ollama (local)
        - Demo mode with simulated responses when service is not configured
    """,
    'author': 'Clavis Development',
    'website': 'https://github.com/clavisdev9-bit',
    'depends': ['base', 'mail', 'sale', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/ai_log_views.xml',
        'views/res_config_settings_views.xml',
        'views/ai_menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'clavis_ai/static/src/components/ai_chat_window/ai_chat_window.scss',
            'clavis_ai/static/src/components/ai_chat_window/ai_chat_window.js',
            'clavis_ai/static/src/components/ai_chat_window/ai_chat_window.xml',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
