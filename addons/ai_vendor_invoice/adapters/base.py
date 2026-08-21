# © 2024 Wukong Digital. License LGPL-3.
"""Provider adapters.  Adapters never expose provider secrets in exceptions."""

from abc import ABC, abstractmethod

import requests


class AIProviderError(Exception):
    """Base class for errors returned by an AI provider."""


class AIProviderTemporaryError(AIProviderError):
    """The request may succeed when retried later."""


class AIProviderPermanentError(AIProviderError):
    """The request cannot succeed without changing its input/configuration."""


class BaseAIProviderAdapter(ABC):
    provider_name = None

    def __init__(self, env):
        self.env = env

    def _credentials(self, provider_config):
        # Reading the key through sudo is intentional; callers still cannot
        # return it through an RPC recordset.
        return provider_config.sudo().api_key

    def _request(self, provider_config, payload, headers=None, max_attempt_retry=0, attempt_obj=None):
        request_headers = {"Content-Type": "application/json"}
        if headers:
            request_headers.update(headers)
        retries = 0
        while True:
            try:
                response = requests.post(
                    provider_config.api_base_url,
                    json=payload,
                    headers=request_headers,
                    timeout=provider_config.http_timeout,
                )
            except (requests.Timeout, requests.ConnectionError) as error:
                if retries < max_attempt_retry:
                    retries += 1
                    if attempt_obj:
                        attempt_obj.write({"attempt_internal_retry_count": retries})
                    continue
                raise AIProviderTemporaryError("AI provider request temporarily unavailable.") from error
            except requests.RequestException as error:
                raise AIProviderPermanentError("AI provider request failed.") from error
            if response.status_code in (408, 409, 425, 429) or response.status_code >= 500:
                if retries < max_attempt_retry:
                    retries += 1
                    if attempt_obj:
                        attempt_obj.write({"attempt_internal_retry_count": retries})
                    continue
                raise AIProviderTemporaryError("AI provider temporarily unavailable.")
            break
        if response.status_code >= 400:
            raise AIProviderPermanentError("AI provider rejected the request.")
        try:
            body = response.json()
        except ValueError as error:
            raise AIProviderPermanentError("AI provider returned invalid JSON.") from error
        return body, response.content

    @staticmethod
    def _canonical(body):
        result = body.get("canonical_result", body.get("result", body))
        if not isinstance(result, dict):
            raise AIProviderPermanentError("AI provider returned an invalid invoice result.")
        return result

    @abstractmethod
    def parse_pdf(self, pdf_attachment, provider_config, max_attempt_retry=0, attempt_obj=None):
        """Return ``(canonical_result, raw_response_bytes)``."""


def adapter_for(env, provider_config):
    from .claude import ClaudeAIProviderAdapter
    from .deepseek import DeepSeekAIProviderAdapter

    name = (provider_config.name or "").lower()
    if "claude" in name or "anthropic" in name:
        return ClaudeAIProviderAdapter(env)
    if "deepseek" in name:
        return DeepSeekAIProviderAdapter(env)
    raise AIProviderPermanentError("Unsupported AI provider.")
