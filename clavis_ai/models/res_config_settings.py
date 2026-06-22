from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    clavis_ai_enabled = fields.Boolean(
        string='Enable Clavis AI',
        config_parameter='clavis_ai.enabled',
    )
    clavis_ai_service_url = fields.Char(
        string='AI Service URL',
        config_parameter='clavis_ai.service_url',
        help='URL of the FastAPI orchestration service, e.g. http://localhost:8000',
    )
    clavis_ai_api_key = fields.Char(
        string='API Key',
        config_parameter='clavis_ai.api_key',
        help='Shared secret key sent in the X-API-Key header to authenticate with the AI service.',
    )
    clavis_ai_llm_provider = fields.Selection(
        selection=[
            ('openai', 'OpenAI (GPT-4o)'),
            ('ollama', 'Ollama (Local)'),
        ],
        string='LLM Provider',
        config_parameter='clavis_ai.llm_provider',
        default='openai',
        help='The LLM backend the FastAPI service should use. This is passed to the service on each request.',
    )
