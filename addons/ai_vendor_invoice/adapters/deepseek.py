# © 2024 Wukong Digital. License LGPL-3.

import hashlib
import json

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

from .aibase import (
    BaseVisionAIProviderAdapter,
    EXTRACTION_CONTRACT_VERSION,
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    USER_PROMPT,
)
from .base import AIProviderPermanentError, AIProviderTemporaryError
from .prompts import MARKDOWN_PROMPT, MARKDOWN_PROMPT_VERSION, prompt_for_mode
from ..services import observability_service
from ..services.extraction_profiles import get_profile


MARKDOWN_SYSTEM_PROMPT = MARKDOWN_PROMPT


class DeepSeekAIProviderAdapter(BaseVisionAIProviderAdapter):
    provider_name = "deepseek"
    provider_label = "DeepSeek"
    supported_input_modes = frozenset({"rendered_images", "markdown"})

    def _build_client(self, provider_config):
        return OpenAI(
            api_key=self._credentials(provider_config),
            base_url=provider_config.api_base_url,
            timeout=provider_config.http_timeout,
            max_retries=0,
        )

    def _build_payload(self, provider_config, images):
        payload = self._vision_payload(provider_config, images)
        payload.update({
            "reasoning_effort": "high",
            "extra_body": {"thinking": {"type": "enabled"}},
        })
        return payload

    def parse_pdf(self, provider_input, provider_config, max_attempt_retry=0, attempt_obj=None):
        if provider_input.get("mode") == "markdown":
            return self.parse_markdown(
                provider_input, provider_config, max_attempt_retry, attempt_obj
            )
        return super().parse_pdf(
            provider_input, provider_config, max_attempt_retry, attempt_obj
        )

    def parse_markdown(self, provider_input, provider_config, max_attempt_retry=0, attempt_obj=None):
        self.validate_input_mode("markdown")
        profile = (
            get_profile(attempt_obj.profile_key)
            if attempt_obj else get_profile("generic")
        )
        prompt = prompt_for_mode(
            "markdown",
            profile.extension,
            profile.extension_version,
        )
        system_prompt = prompt.system
        client = self._build_client(provider_config)
        prompt_snapshot = {
            "prompt_version": prompt.version,
            "instructions_checksum": hashlib.sha256(
                system_prompt.encode()
            ).hexdigest(),
            "input_mode": "markdown",
        }
        retries = 0
        while True:
            provider_call = observability_service.begin_provider_call(
                attempt_obj, None, retries, provider_config, prompt_snapshot,
                input_page_count=provider_input.get("source", {}).get("page_count"),
                input_mode="markdown", input_document_type="text/markdown",
                rendered_image_count=0,
            ) if attempt_obj else None
            try:
                response = client.chat.completions.create(
                    model=provider_config.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": provider_input["markdown_text"]},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0,
                    stream=False,
                    timeout=provider_config.http_timeout,
                )
                raw_response = response.model_dump_json().encode()
                content = response.choices[0].message.content
                if not isinstance(content, str) or not content.strip():
                    raise AIProviderPermanentError("AI provider returned empty JSON.")
                canonical = self._canonical(json.loads(content))
                observability_service.finish_provider_call(
                    attempt_obj, provider_call, outcome="success",
                    validation_status="pass", http_status=200,
                    raw_response=raw_response, response_received=True,
                )
                return canonical, raw_response
            except (json.JSONDecodeError, AIProviderPermanentError) as error:
                if attempt_obj and provider_call:
                    observability_service.finish_provider_call(
                        attempt_obj, provider_call, outcome="response_invalid",
                        validation_status="fail", failure_stage="CANONICAL_VALIDATION",
                        safe_error_summary="DeepSeek Markdown response was invalid.",
                        response_received=True,
                    )
                raise
            except (APITimeoutError, APIConnectionError) as error:
                if retries >= max_attempt_retry:
                    raise AIProviderTemporaryError(
                        "AI provider request temporarily unavailable."
                    ) from error
                retries += 1
                self._wait_before_retry(retries - 1)
            except APIStatusError as error:
                if not self._is_retryable_http_status(error.status_code):
                    raise AIProviderPermanentError(
                        "AI provider rejected the request."
                    ) from error
                if retries >= max_attempt_retry:
                    raise AIProviderTemporaryError(
                        "AI provider temporarily unavailable."
                    ) from error
                retries += 1
                self._wait_before_retry(retries - 1)


__all__ = [
    "DeepSeekAIProviderAdapter",
    "EXTRACTION_CONTRACT_VERSION",
    "PROMPT_VERSION",
    "SYSTEM_PROMPT",
    "USER_PROMPT",
    "MARKDOWN_PROMPT_VERSION",
    "MARKDOWN_SYSTEM_PROMPT",
]
