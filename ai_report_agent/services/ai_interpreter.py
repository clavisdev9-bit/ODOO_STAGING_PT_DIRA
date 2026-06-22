# -*- coding: utf-8 -*-
"""AI Interpreter — converts natural language to structured JSON intent via LLM.

Supports Anthropic Claude, OpenAI, Ollama, and Custom HTTP providers
via the adapter pattern. All adapters share the same interface.
"""
import json
import logging
from abc import ABC, abstractmethod
from typing import Any

_logger = logging.getLogger(__name__)


class InterpretError(Exception):
    """Raised when AI output cannot be parsed as valid intent JSON."""


class LLMConnectionError(Exception):
    """Raised when the LLM provider is unreachable or returns an error."""


# ---------------------------------------------------------------------------
# Adapter base + implementations
# ---------------------------------------------------------------------------

class LLMAdapter(ABC):
    """Abstract adapter for LLM provider calls."""

    @abstractmethod
    def complete(self, system_prompt: str, user_message: str, config: Any) -> str:
        """Send a completion request and return raw response string.

        Args:
            system_prompt: System-level instruction for the LLM.
            user_message: User's natural language input.
            config: AiReportConfig record with provider settings.

        Returns:
            Raw string response from the LLM (should be JSON).

        Raises:
            LLMConnectionError: On network or API errors.
        """


class AnthropicAdapter(LLMAdapter):
    """Adapter for Anthropic Claude API."""

    def complete(self, system_prompt: str, user_message: str, config: Any) -> str:
        try:
            import anthropic
        except ImportError as e:
            raise LLMConnectionError('anthropic Python package not installed. Run: pip install anthropic') from e

        api_key = config.get_api_key_secure()
        if not api_key:
            raise LLMConnectionError('Anthropic API key is not configured.')

        try:
            client = anthropic.Anthropic(api_key=api_key)
            message = client.messages.create(
                model=config.llm_model or 'claude-sonnet-4-6',
                max_tokens=config.max_tokens or 1000,
                system=system_prompt,
                messages=[{'role': 'user', 'content': user_message}],
                temperature=config.temperature if hasattr(config, 'temperature') else 0.1,
            )
            return message.content[0].text
        except Exception as e:
            _logger.error('Anthropic API error: %s', e)
            raise LLMConnectionError(f'Anthropic API error: {e}') from e


class OpenAIAdapter(LLMAdapter):
    """Adapter for OpenAI API."""

    def complete(self, system_prompt: str, user_message: str, config: Any) -> str:
        try:
            import openai
        except ImportError as e:
            raise LLMConnectionError('openai Python package not installed. Run: pip install openai') from e

        api_key = config.get_api_key_secure()
        if not api_key:
            raise LLMConnectionError('OpenAI API key is not configured.')

        model = config.llm_model or 'gpt-4o'
        try:
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                max_tokens=config.max_tokens or 1000,
                temperature=config.temperature if hasattr(config, 'temperature') else 0.1,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_message},
                ],
            )
            return response.choices[0].message.content
        except openai.NotFoundError:
            raise LLMConnectionError(
                f'OpenAI model "{model}" does not exist. '
                'Use the "Pilih Model OpenAI" dropdown or set a valid model name (e.g. gpt-4o).'
            ) from None
        except Exception as e:
            _logger.error('OpenAI API error: %s', e)
            raise LLMConnectionError(f'OpenAI API error: {e}') from e


class OllamaAdapter(LLMAdapter):
    """Adapter for local Ollama server using /api/generate (all versions)."""

    def complete(self, system_prompt: str, user_message: str, config: Any) -> str:
        import requests

        endpoint = (config.api_endpoint or 'http://localhost:11434').rstrip('/')
        model = config.llm_model or 'llama3.2'
        url = f'{endpoint}/api/generate'
        prompt = f'System: {system_prompt}\n\nUser: {user_message}\nAssistant:'

        try:
            resp = requests.post(
                url,
                json={
                    'model': model,
                    'prompt': prompt,
                    'stream': False,
                    'options': {
                        'temperature': config.temperature if hasattr(config, 'temperature') else 0.1,
                        'num_predict': config.max_tokens or 1000,
                    },
                },
                timeout=120,
            )
        except Exception as e:
            _logger.error('Ollama network error at %s: %s', url, e)
            raise LLMConnectionError(f'Cannot reach Ollama at {endpoint}: {e}') from e

        # Check body before raise_for_status — Ollama returns error JSON on non-2xx
        try:
            data = resp.json()
        except Exception:
            data = {}

        if 'error' in data:
            msg = data['error']
            if 'not found' in msg.lower():
                raise LLMConnectionError(
                    f'Model "{model}" is not pulled on the Ollama server.\n'
                    f'Run on the server: ollama pull {model}'
                )
            raise LLMConnectionError(f'Ollama error: {msg}')

        try:
            resp.raise_for_status()
        except Exception as e:
            _logger.error('Ollama HTTP error at %s: %s', url, e)
            raise LLMConnectionError(f'Ollama error: {e}') from e

        return data.get('response', '')


class CustomHTTPAdapter(LLMAdapter):
    """Generic REST POST adapter for custom LLM endpoints."""

    def complete(self, system_prompt: str, user_message: str, config: Any) -> str:
        import requests

        endpoint = config.api_endpoint
        if not endpoint:
            raise LLMConnectionError('Custom HTTP endpoint is not configured.')

        api_key = config.get_api_key_secure()
        headers = {'Content-Type': 'application/json'}
        if api_key:
            headers['Authorization'] = f'Bearer {api_key}'

        payload = {
            'system': system_prompt,
            'message': user_message,
            'model': config.llm_model,
            'temperature': config.temperature if hasattr(config, 'temperature') else 0.1,
            'max_tokens': config.max_tokens or 1000,
        }

        try:
            resp = requests.post(endpoint, json=payload, headers=headers, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            # Support common response shapes
            return (
                data.get('text')
                or data.get('content')
                or data.get('response')
                or data.get('output')
                or str(data)
            )
        except Exception as e:
            _logger.error('Custom HTTP LLM error at %s: %s', endpoint, e)
            raise LLMConnectionError(f'Custom HTTP error: {e}') from e


_ADAPTER_MAP: dict[str, type[LLMAdapter]] = {
    'anthropic': AnthropicAdapter,
    'openai': OpenAIAdapter,
    'ollama': OllamaAdapter,
    'custom': CustomHTTPAdapter,
}

# ---------------------------------------------------------------------------
# Main interpreter class
# ---------------------------------------------------------------------------

class AIInterpreter:
    """Orchestrates LLM calls and parses structured JSON intent.

    Args:
        env: Odoo environment — used to load AiReportConfig.
    """

    def __init__(self, env: Any) -> None:
        self.env = env

    def interpret(self, user_message: str, context_history: list | None = None) -> dict:
        """Convert natural language to structured intent dict.

        Args:
            user_message: The user's report request in any language.
            context_history: Optional list of last N history records for continuity.

        Returns:
            Validated intent dict ready for RuleEngine.

        Raises:
            InterpretError: If AI response is invalid or confidence too low.
        """
        config = self.env['ai.report.config'].get_active_config()
        adapter = self._get_adapter(config)

        system_prompt = config.system_prompt
        full_message = self._build_user_message(user_message, context_history)

        _logger.info('AIInterpreter: calling %s with message length %d', config.llm_provider, len(full_message))

        try:
            raw_response = adapter.complete(system_prompt, full_message, config)
        except LLMConnectionError:
            raise
        except Exception as e:
            raise LLMConnectionError(f'LLM call failed: {e}') from e

        _logger.debug('AIInterpreter raw response: %s', raw_response[:500])

        return self._parse_response(raw_response, config)

    def _get_adapter(self, config: Any) -> LLMAdapter:
        """Instantiate the correct LLM adapter from config."""
        adapter_cls = _ADAPTER_MAP.get(config.llm_provider)
        if not adapter_cls:
            raise LLMConnectionError(f'Unknown LLM provider: {config.llm_provider}')
        return adapter_cls()

    def _build_user_message(self, user_message: str, context_history: list | None) -> str:
        """Prepend recent history context to improve continuity."""
        if not context_history:
            return user_message

        ctx_parts = []
        for hist in context_history[-3:]:
            ctx_parts.append(f'Previous request: {hist.user_message}')
            if hist.interpreted_intent:
                ctx_parts.append(f'Previous intent: {hist.interpreted_intent}')

        context_block = '\n'.join(ctx_parts)
        return f'[Context]\n{context_block}\n\n[Current Request]\n{user_message}'

    def _parse_response(self, raw: str, config: Any) -> dict:
        """Parse raw LLM string into validated intent dict.

        Args:
            raw: Raw string from LLM (should be JSON).
            config: Config record for fallback settings.

        Returns:
            Parsed intent dict.

        Raises:
            InterpretError: On parse failure or low confidence without fallback.
        """
        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith('```'):
            lines = cleaned.split('\n')
            cleaned = '\n'.join(lines[1:-1] if lines[-1].strip() == '```' else lines[1:])

        try:
            intent_dict = json.loads(cleaned)
        except json.JSONDecodeError as e:
            _logger.error('AI response is not valid JSON: %s\nRaw: %s', e, raw[:300])
            if config.fallback_to_rules:
                _logger.info('Falling back to rule-engine default intent')
                return self._default_intent()
            raise InterpretError(f'AI returned invalid JSON: {e}') from e

        confidence = float(intent_dict.get('confidence', 0.0))
        if confidence < 0.5 and not config.fallback_to_rules:
            raise InterpretError(
                f'AI confidence {confidence:.2f} is below threshold 0.5 and fallback is disabled.'
            )

        if confidence < 0.5:
            _logger.warning('Low AI confidence %.2f — using rule-engine fallback', confidence)
            return self._default_intent()

        return intent_dict

    @staticmethod
    def _default_intent() -> dict:
        """Return a safe default intent when AI fails."""
        return {
            'intent': 'summary',
            'date_range': 'this_month',
            'filters': {},
            'report_type': 'table',
            'output_format': ['pdf', 'xlsx'],
            'confidence': 0.3,
            'needs_clarification': True,
            'clarification_question': (
                'I could not understand your request. '
                'Showing a summary report for this month. '
                'Please rephrase your request.'
            ),
        }
