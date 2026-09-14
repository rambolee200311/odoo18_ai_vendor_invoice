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
from ..services import observability_service


MARKDOWN_PROMPT_VERSION = "markdown-extraction-v4"
MARKDOWN_SYSTEM_PROMPT = """You are a transport-supplier-invoice fact extractor.
The user content is Markdown converted from the original PDF.
Extract only facts visibly printed in that document. Return JSON only.
Use exactly the production Canonical JSON shape:
{"header":{"invoice_number":{"value":string|null,"confidence":number},"invoice_date":{"value":"YYYY-MM-DD"|null,"confidence":number},"supplier_raw_text":{"value":string|null,"confidence":number},"currency_raw_text":{"value":string|null,"confidence":number},"total_amount":{"value":string|null,"confidence":number},"total_tax":{"value":string|null,"confidence":number},"subtotal":{"value":string|null,"confidence":number}},"lines":[{"description":{"value":string|null,"confidence":number},"amount":{"value":string|null,"confidence":number},"tax_raw_text":{"value":string|null,"confidence":number},"tax_rate":{"value":number|string|null,"confidence":number},"tax_amount":{"value":string|null,"confidence":number},"reconciliation_clues":[{"label":string,"value":string}],"charge_details":string|null}],"is_multi_invoice":boolean}.
Use nested value/confidence header and
line fields. One independent transport/business record is exactly one line.
Keep nested fees in charge_details and preserve shipment, loading, unloading,
cargo, weight, volume, and references in reconciliation_clues. Do not treat
shipment or order references as invoice_number unless explicitly labelled.
Header totals must come from explicitly labelled summary values; never calculate
or infer them. Reconstruct Markdown layout conservatively and preserve order.
Set is_multi_invoice when applicable. Confidence is 0..1; use null rather than
guessing.

supplier_raw_text must contain only the supplier name.
Do not include address, phone, email, VAT number, or contact information.
If the name and address appear on the same line or block, keep only the name."""


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
        client = self._build_client(provider_config)
        prompt_snapshot = {
            "prompt_version": MARKDOWN_PROMPT_VERSION,
            "instructions_checksum": hashlib.sha256(
                MARKDOWN_SYSTEM_PROMPT.encode()
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
                        {"role": "system", "content": MARKDOWN_SYSTEM_PROMPT},
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
