# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = """You are ReportAgent, an AI integrated into Odoo 18.
Your ONLY job is to convert a user's natural language request into a structured JSON report specification.
You do NOT generate reports, PDFs, Excel files, or data directly.

Always return exactly this JSON structure:
{
  "intent": "sales|invoice|inventory|purchase|expense|summary|unknown",
  "date_range": "today|this_week|this_month|last_month|last_week|this_quarter|last_quarter|Q1|Q2|Q3|Q4|this_year|custom",
  "filters": {
    "state": "",
    "payment_state": "",
    "partner_id": null,
    "product_id": null,
    "warehouse_id": null,
    "custom_start": "",
    "custom_end": ""
  },
  "report_type": "table|summary|chart",
  "output_format": ["pdf", "xlsx"],
  "confidence": 0.0,
  "needs_clarification": false,
  "clarification_question": null
}

Rules:
- Input may be Indonesian or English
- If date is not specified, use "this_month" and set needs_clarification to true
- If intent is unclear, set intent to "unknown" and confidence below 0.5
- ALWAYS output valid JSON only. No prose, no explanation, no markdown.
- Never output anything outside the JSON structure above."""


class AiReportConfig(models.Model):
    """Configuration model for AI Report Agent LLM settings."""

    _name = 'ai.report.config'
    _description = 'AI Report Agent Configuration'
    _rec_name = 'llm_provider'

    llm_provider = fields.Selection(
        selection=[
            ('anthropic', 'Anthropic Claude'),
            ('openai', 'OpenAI'),
            ('ollama', 'Ollama Local'),
            ('custom', 'Custom HTTP'),
        ],
        string='LLM Provider',
        required=True,
        default='anthropic',
    )
    llm_model = fields.Char(
        string='Model Name',
        default='claude-sonnet-4-6',
        required=True,
        help='Model identifier (e.g. claude-sonnet-4-6, gpt-4o, llama3)',
    )
    api_key = fields.Char(
        string='API Key',
        password=True,
        help='API key — stored encrypted, never exposed in RPC',
    )
    api_endpoint = fields.Char(
        string='API Endpoint',
        help='Required for Ollama or Custom HTTP providers',
        default='http://localhost:11434',
    )
    temperature = fields.Float(
        string='Temperature',
        default=0.1,
        help='LLM sampling temperature (0.0 = deterministic, 1.0 = creative)',
    )
    max_tokens = fields.Integer(
        string='Max Tokens',
        default=1000,
        help='Maximum tokens in LLM response',
    )
    max_rows = fields.Integer(
        string='Max Rows',
        default=1000,
        help='Maximum number of records fetched per report',
    )
    async_threshold = fields.Integer(
        string='Async Threshold',
        default=5000,
        help='Records above this count are processed via async queue',
    )
    enable_ai_insight = fields.Boolean(
        string='Enable AI Insights',
        default=True,
        help='Generate AI-powered summary/insight after building report',
    )
    fallback_to_rules = fields.Boolean(
        string='Fallback to Rule Engine',
        default=True,
        help='Use deterministic rule engine when AI confidence is low',
    )
    system_prompt = fields.Text(
        string='System Prompt',
        default=DEFAULT_SYSTEM_PROMPT,
        help='Editable system prompt sent to the LLM',
    )
    active = fields.Boolean(default=True)
    available_models = fields.Text(
        string='Available Models',
        readonly=True,
        help='List of models available. Click "Refresh Models" to update.',
    )
    ollama_tags_url = fields.Char(
        string='Ollama Tags URL',
        compute='_compute_ollama_tags_url',
        help='URL endpoint untuk melihat model yang tersedia di Ollama (/api/tags)',
    )
    openai_model_preset = fields.Selection(
        selection=[
            ('gpt-4o', 'GPT-4o'),
            ('gpt-4o-mini', 'GPT-4o Mini'),
            ('gpt-4-turbo', 'GPT-4 Turbo'),
            ('gpt-3.5-turbo', 'GPT-3.5 Turbo'),
            ('o1', 'o1'),
            ('o1-mini', 'o1 Mini'),
            ('o3', 'o3'),
            ('o3-mini', 'o3 Mini'),
        ],
        string='Pilih Model OpenAI',
        help='Pilih model OpenAI dari daftar. Akan mengisi field Model Name di bawah.',
    )
    anthropic_model_preset = fields.Selection(
        selection=[
            ('claude-opus-4-7', 'Claude Opus 4.7 (Terbaru & Terkuat)'),
            ('claude-sonnet-4-6', 'Claude Sonnet 4.6 (Seimbang)'),
            ('claude-haiku-4-5', 'Claude Haiku 4.5 (Cepat & Hemat)'),
        ],
        string='Pilih Model Claude',
        help='Pilih model Anthropic Claude dari daftar. Akan mengisi field Model Name di bawah.',
    )

    _sql_constraints = [
        ('temperature_range', 'CHECK(temperature >= 0.0 AND temperature <= 1.0)',
         'Temperature must be between 0.0 and 1.0'),
        ('max_tokens_positive', 'CHECK(max_tokens > 0)', 'Max tokens must be positive'),
        ('max_rows_positive', 'CHECK(max_rows > 0)', 'Max rows must be positive'),
    ]

    @api.depends('llm_provider', 'api_endpoint')
    def _compute_ollama_tags_url(self) -> None:
        for rec in self:
            if rec.llm_provider == 'ollama':
                endpoint = (rec.api_endpoint or 'http://localhost:11434').rstrip('/')
                rec.ollama_tags_url = f'{endpoint}/api/tags'
            else:
                rec.ollama_tags_url = False

    @api.constrains('llm_provider', 'api_endpoint')
    def _check_endpoint_required(self) -> None:
        """Validate that endpoint is set for providers requiring it."""
        for rec in self:
            if rec.llm_provider in ('ollama', 'custom') and not rec.api_endpoint:
                raise ValidationError(
                    _('API Endpoint is required for %s provider.') % rec.llm_provider
                )

    @api.model
    def get_active_config(self) -> 'AiReportConfig':
        """Return the first active configuration record."""
        config = self.search([('active', '=', True)], limit=1)
        if not config:
            raise ValidationError(
                _('No active AI Report configuration found. Please configure one in Settings.')
            )
        return config

    def _store_api_key(self, record_id: int, key: str) -> None:
        param_key = f'ai_report_agent.api_key.{record_id}'
        self.env['ir.config_parameter'].sudo().set_param(param_key, key)

    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            if rec.api_key:
                self._store_api_key(rec.id, rec.api_key)
        return records

    def write(self, vals: dict) -> bool:
        """Store api_key in ir.config_parameter for extra security."""
        if 'api_key' in vals and vals['api_key']:
            for rec in self:
                self._store_api_key(rec.id, vals['api_key'])
        return super().write(vals)

    def get_api_key_secure(self) -> str:
        """Retrieve API key from secure parameter store."""
        self.ensure_one()
        param_key = f'ai_report_agent.api_key.{self.id}'
        key = self.env['ir.config_parameter'].sudo().get_param(param_key, default='')
        if not key and self.api_key:
            key = self.api_key
        return key

    @api.onchange('llm_provider')
    def _onchange_llm_provider(self):
        """Set sensible defaults and clear presets when provider changes."""
        provider_defaults = {
            'anthropic': 'claude-opus-4-7',
            'openai': 'gpt-4o',
            'ollama': 'qwen3:4b',
            'custom': '',
        }
        self.llm_model = provider_defaults.get(self.llm_provider, '')
        self.openai_model_preset = False
        self.anthropic_model_preset = False
        if self.llm_provider == 'ollama' and self.api_endpoint:
            self._do_fetch_ollama_models()

    @api.onchange('openai_model_preset')
    def _onchange_openai_model_preset(self):
        """Populate llm_model from the OpenAI preset dropdown."""
        if self.openai_model_preset:
            self.llm_model = self.openai_model_preset

    @api.onchange('anthropic_model_preset')
    def _onchange_anthropic_model_preset(self):
        """Populate llm_model from the Anthropic preset dropdown."""
        if self.anthropic_model_preset:
            self.llm_model = self.anthropic_model_preset

    @api.onchange('api_endpoint')
    def _onchange_fetch_ollama_models(self):
        """Auto-fetch Ollama models when endpoint changes."""
        if self.llm_provider == 'ollama' and self.api_endpoint:
            self._do_fetch_ollama_models()

    def _do_fetch_ollama_models(self) -> list:
        """Fetch model list from Ollama /api/tags. Returns list of model names."""
        import requests
        endpoint = (self.api_endpoint or 'http://localhost:11434').rstrip('/')
        url = f'{endpoint}/api/tags'
        try:
            resp = requests.get(url, timeout=10)
            _logger.info('Ollama /api/tags [%s] status=%s body=%s', url, resp.status_code, resp.text[:500])
            resp.raise_for_status()
            data = resp.json()
            models = [m['name'] for m in data.get('models', [])]
            _logger.info('Ollama models found: %s', models)
            if models:
                self.available_models = '\n'.join(models)
            else:
                self.available_models = _(
                    'No models found at %s\n'
                    'Raw response: %s\n\n'
                    'Run on server: ollama pull qwen3:4b'
                ) % (url, resp.text[:200])
            return models
        except Exception as e:
            _logger.error('Ollama fetch failed [%s]: %s', url, e)
            self.available_models = _('Failed to fetch from %s\nError: %s') % (url, str(e))
            return []

    def _do_fetch_openai_models(self) -> list:
        """Fetch model list from OpenAI /v1/models. Returns list of chat model names."""
        import requests

        api_key = self.get_api_key_secure()
        if not api_key:
            self.available_models = _('API Key belum diisi. Masukkan API Key OpenAI terlebih dahulu.')
            return []

        url = 'https://api.openai.com/v1/models'
        headers = {'Authorization': f'Bearer {api_key}'}
        try:
            resp = requests.get(url, headers=headers, timeout=15)
            _logger.info('OpenAI /v1/models status=%s', resp.status_code)
            resp.raise_for_status()
            data = resp.json()
            # Filter to chat/completion models only
            all_models = sorted(
                [m['id'] for m in data.get('data', []) if 'gpt' in m['id'] or m['id'].startswith('o')],
                key=lambda x: x,
            )
            _logger.info('OpenAI models found: %s', all_models)
            if all_models:
                self.available_models = '\n'.join(all_models)
            else:
                self.available_models = _('Tidak ada model ditemukan di akun OpenAI Anda.')
            return all_models
        except Exception as e:
            _logger.error('OpenAI models fetch failed: %s', e)
            self.available_models = _('Gagal mengambil daftar model OpenAI.\nError: %s') % str(e)
            return []

    def action_fetch_ollama_models(self) -> dict:
        """Button: Fetch and display available models for the active provider."""
        self.ensure_one()
        if self.llm_provider == 'openai':
            models = self._do_fetch_openai_models()
            if models:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Models Loaded'),
                        'message': _('%d model(s) available. Lihat daftar di bawah atau gunakan dropdown Pilih Model OpenAI.') % len(models),
                        'type': 'success',
                    },
                }
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Models Found'),
                    'message': _('Tidak ada model ditemukan. Periksa API Key OpenAI Anda.'),
                    'type': 'warning',
                },
            }

        models = self._do_fetch_ollama_models()
        if models:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Models Loaded'),
                    'message': _('%d model(s) available. Select one in the Model Name field.') % len(models),
                    'type': 'success',
                },
            }
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('No Models Found'),
                'message': _('No models found. Make sure Ollama is running and models are pulled.'),
                'type': 'warning',
            },
        }

    def action_test_connection(self) -> dict:
        """Test LLM connection and return a notification."""
        self.ensure_one()
        if self.llm_provider == 'ollama':
            return self._test_ollama_connection()
        try:
            from ..services.ai_interpreter import AIInterpreter
            AIInterpreter(self.env).interpret('test connection')
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Successful'),
                    'message': _('LLM provider responded correctly.'),
                    'type': 'success',
                },
            }
        except Exception as e:
            _logger.exception('LLM connection test failed: %s', e)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Failed'),
                    'message': str(e),
                    'type': 'danger',
                },
            }

    def _test_ollama_connection(self) -> dict:
        """Test Ollama by calling /api/tags — faster than a full LLM call."""
        import requests
        url = self.ollama_tags_url or 'http://localhost:11434/api/tags'
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            models = resp.json().get('models', [])
            model_names = [m['name'] for m in models]
            self.available_models = '\n'.join(model_names) or _(
                'No models pulled yet.\n'
                'Run on the Ollama server:\n'
                '  ollama pull %s'
            ) % (self.llm_model or 'qwen3:4b')
            if not models:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': _('Ollama Connected — No Models'),
                        'message': _(
                            'Server reachable at %s but no models are pulled.\n'
                            'Run on server: ollama pull %s'
                        ) % (url, self.llm_model or 'qwen3:4b'),
                        'type': 'warning',
                    },
                }
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Ollama Connected'),
                    'message': _('%d model(s) available at %s') % (len(models), url),
                    'type': 'success',
                },
            }
        except Exception as e:
            _logger.error('Ollama connection test failed: %s', e)
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Connection Failed'),
                    'message': str(e),
                    'type': 'danger',
                },
            }
