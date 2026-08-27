# © 2024 Wukong Digital. License LGPL-3.
import base64
import copy
import json
import logging
import time
from datetime import datetime, timezone

from openai import (
    APIError,
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    OpenAI,
)
from jsonschema import ValidationError, validate

from .base import (
    AIProviderPermanentError,
    AIProviderTemporaryError,
    BaseAIProviderAdapter,
)
from ..schemas.page_extraction import PAGE_EXTRACTION_RESULT_SCHEMA
from .document_normalizer import (
    DocumentNormalizationError,
    normalize_page_results,
)

_logger = logging.getLogger(__name__)

EXTRACTION_CONTRACT_VERSION = "transport-invoice-page-v1"
PROMPT_VERSION = "vision-extraction-v1.1"

SYSTEM_PROMPT = """You are a transport-supplier-invoice page fact extractor, not a business decision maker.
Extract only facts visibly printed on the current PDF page. Return JSON only.
Extract explicit invoice header fields, fee and charge lines, dates, addresses,
and explicitly labelled identifiers or references. Preserve every uncertain or
unclassified printed field in raw_facts using its original source_label and
source_value. Do not determine business meaning unless the printed label
explicitly states it.

Do not guess, autocomplete, calculate, reconcile, or fill missing values.
Omit missing fields or use null. Do not use information from another page.
Do not treat repeated headers, footers, or column headings as invoice lines.
Do not interpret Shipment Number, Dossier, O.No., Opdracht, Uw ref., Your
reference, customer reference, order reference, transport reference, booking
reference, or consignment reference as invoice_number unless the page explicitly
labels the value as an invoice number.
Use plain scalar values and return no explanation outside the JSON object."""

USER_PROMPT = """Extract visible facts from this PDF page and return one PageExtractionResult JSON object.
Include explicit invoice header fields, fee or charge lines, dates, addresses,
and explicitly labelled identifiers or references. Keep standard fields as plain
scalar values. For every visible field whose business meaning is uncertain, add
a raw_facts item containing the original source_label and source_value.
Do not classify or rename an uncertain reference. Do not convert shipment,
dossier, order, opdracht, customer, transport, or other reference numbers into
invoice_number unless the printed label explicitly says invoice number.
Do not guess, calculate, reconcile, autocomplete, or fill missing values.
Return JSON only."""


class DeepSeekAIProviderAdapter(BaseAIProviderAdapter):
    provider_name = "deepseek"
    page_batch_size = 1

    def parse_pdf(self, provider_input, provider_config, max_attempt_retry=0, attempt_obj=None):
        client = OpenAI(
            api_key=self._credentials(provider_config),
            base_url=provider_config.api_base_url,
            timeout=provider_config.http_timeout,
            max_retries=0,
        )
        results = []
        raw_responses = []
        images = provider_input["images"]
        for offset in range(0, len(images), self.page_batch_size):
            result, raw = self._parse_page_batch(
                client,
                provider_config,
                images[offset:offset + self.page_batch_size],
                max_attempt_retry,
                attempt_obj,
                offset,
                len(images),
            )
            results.append(result)
            raw_responses.append(raw)
        merge_started = time.monotonic()
        try:
            merged = normalize_page_results(results)
        except DocumentNormalizationError:
            self._log_diagnostic(
                attempt_obj,
                0,
                len(images),
                len(images),
                sum(len(image) for image in images),
                int((time.monotonic() - merge_started) * 1000),
                0,
                None,
                "AIProviderPermanentError",
                "DOCUMENT_NORMALIZATION_INVALID",
                "NOT_RUN",
                "PASS",
            )
            raise
        raw_response = json.dumps(raw_responses).encode()
        return merged, base64.b64encode(raw_response)

    def _parse_page_batch(
        self,
        client,
        provider_config,
        images,
        max_attempt_retry,
        attempt_obj,
        page_start,
        total_pages,
    ):
        payload = {
            "model": provider_config.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": USER_PROMPT,
                        },
                        *[
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": "data:image/png;base64,%s"
                                    % base64.b64encode(image).decode(),
                                },
                            }
                            for image in images
                        ],
                    ],
                },
            ],
            "stream": False,
            "reasoning_effort": "high",
            "extra_body": {"thinking": {"type": "enabled"}},
            "response_format": {"type": "json_object"},
        }
        retries = 0
        image_bytes = sum(len(image) for image in images)
        while True:
            request_started = time.monotonic()
            started_at = datetime.now(timezone.utc).isoformat()
            try:
                response = client.chat.completions.create(**payload)
                elapsed_ms = int((time.monotonic() - request_started) * 1000)
                body = response.model_dump()
                raw = response.model_dump_json()
                content = body.get("choices", [{}])[0].get("message", {}).get("content")
                if not isinstance(content, str) or not content.strip():
                    self._log_diagnostic(
                        attempt_obj, page_start, total_pages, len(images),
                        image_bytes, elapsed_ms, retries, 200, None,
                        "RESPONSE_EMPTY", "NOT_RUN", "FAIL", started_at,
                    )
                    raise AIProviderPermanentError(
                        "DeepSeek response did not contain JSON message content."
                    )
                try:
                    parsed_content = json.loads(content)
                except (TypeError, ValueError) as error:
                    self._log_diagnostic(
                        attempt_obj, page_start, total_pages, len(images),
                        image_bytes, elapsed_ms, retries, 200,
                        type(error).__name__, "RESPONSE_INVALID_JSON", "NOT_RUN",
                        "FAIL", started_at,
                    )
                    raise AIProviderPermanentError(
                        "DeepSeek response did not contain valid JSON."
                    ) from error
                try:
                    result = self._page_extraction(parsed_content, page_start + 1)
                except (AIProviderPermanentError, ValidationError, TypeError, ValueError) as error:
                    self._log_diagnostic(
                        attempt_obj, page_start, total_pages, len(images),
                        image_bytes, elapsed_ms, retries, 200, type(error).__name__,
                        "RESPONSE_SCHEMA_INVALID", "FAIL", "PASS", started_at,
                    )
                    raise
                self._log_diagnostic(
                    attempt_obj, page_start, total_pages, len(images), image_bytes,
                    elapsed_ms, retries, 200, None, "NONE", "PASS", "PASS",
                    started_at,
                )
                break
            except (APITimeoutError, APIConnectionError) as error:
                elapsed_ms = int((time.monotonic() - request_started) * 1000)
                category = (
                    "TEMPORARY_TIMEOUT"
                    if isinstance(error, APITimeoutError)
                    else "TEMPORARY_CONNECTION"
                )
                self._log_diagnostic(
                    attempt_obj, page_start, total_pages, len(images), image_bytes,
                    elapsed_ms, retries, None, type(error).__name__, category,
                    "NOT_RUN", "NOT_RUN", started_at,
                )
                if retries >= max_attempt_retry:
                    raise AIProviderTemporaryError(
                        "AI provider request temporarily unavailable."
                    ) from error
                retries += 1
                if attempt_obj:
                    attempt_obj.write({"attempt_internal_retry_count": retries})
            except APIStatusError as error:
                elapsed_ms = int((time.monotonic() - request_started) * 1000)
                category = self._status_category(error.status_code)
                self._log_diagnostic(
                    attempt_obj, page_start, total_pages, len(images), image_bytes,
                    elapsed_ms, retries, error.status_code, type(error).__name__,
                    category, "NOT_RUN", "NOT_RUN", started_at,
                )
                if (
                    error.status_code == 408
                    or error.status_code == 429
                    or error.status_code >= 500
                ):
                    if retries < max_attempt_retry:
                        retries += 1
                        if attempt_obj:
                            attempt_obj.write({"attempt_internal_retry_count": retries})
                        continue
                    raise AIProviderTemporaryError(
                        "AI provider temporarily unavailable."
                    ) from error
                raise AIProviderPermanentError(
                    "AI provider rejected the request."
                ) from error
            except APIError as error:
                elapsed_ms = int((time.monotonic() - request_started) * 1000)
                self._log_diagnostic(
                    attempt_obj, page_start, total_pages, len(images), image_bytes,
                    elapsed_ms, retries, None, type(error).__name__,
                    "UNKNOWN_PROVIDER_ERROR", "NOT_RUN", "NOT_RUN", started_at,
                )
                raise AIProviderPermanentError(
                    "AI provider request failed."
                ) from error
        return result, raw

    @staticmethod
    def _page_extraction(body, page_number):
        if not isinstance(body, dict):
            raise TypeError("Page extraction must be an object.")
        result = copy.deepcopy(body)
        result["page_number"] = page_number
        validate(result, PAGE_EXTRACTION_RESULT_SCHEMA)
        for fact in result.get("raw_facts", []):
            fact["source_page"] = page_number
        for line in result.get("lines", []):
            for fact in line.get("raw_fields", []):
                fact["source_page"] = page_number
        return result

    @staticmethod
    def _status_category(status_code):
        if not isinstance(status_code, int):
            return "UNKNOWN_PROVIDER_ERROR"
        if status_code == 401 or status_code == 403:
            return "PERMANENT_AUTH"
        if status_code == 408:
            return "TEMPORARY_TIMEOUT"
        if status_code == 413:
            return "PERMANENT_UNSUPPORTED_INPUT"
        if status_code == 429:
            return "TEMPORARY_RATE_LIMIT"
        if status_code >= 500:
            return "TEMPORARY_5XX"
        if 400 <= status_code < 500:
            return "PERMANENT_BAD_REQUEST"
        return "UNKNOWN_PROVIDER_ERROR"

    @staticmethod
    def _log_diagnostic(
        attempt_obj,
        page_start,
        total_pages,
        image_count,
        total_image_bytes,
        elapsed_ms,
        retry_index,
        http_status_code,
        exception_class,
        provider_error_category,
        canonical_schema_status,
        response_parse_status,
        started_at=None,
    ):
        diagnostic = {
            "started_at": started_at or datetime.now(timezone.utc).isoformat(),
            "page_start": page_start + 1,
            "page_end": page_start + image_count,
            "page_count": image_count,
            "total_pages": total_pages,
            "image_count": image_count,
            "total_image_bytes": total_image_bytes,
            "elapsed_ms": elapsed_ms,
            "retry_index": retry_index,
            "http_status_code": http_status_code,
            "exception_class": exception_class,
            "provider_error_category": provider_error_category,
            "response_parse_status": response_parse_status,
            "canonical_schema_status": canonical_schema_status,
        }
        if attempt_obj:
            diagnostics = getattr(attempt_obj, "provider_diagnostics", None)
            if not isinstance(diagnostics, list):
                diagnostics = []
            attempt_obj.write({
                "provider_diagnostics": diagnostics + [diagnostic],
            })
        _logger.info(
            "provider_page_diagnostic task_id=%s attempt_id=%s "
            "page_start=%s page_end=%s batch_page_count=%s total_pages=%s "
            "image_count=%s total_image_bytes=%s response_elapsed_ms=%s retry_index=%s "
            "http_status_code=%s exception_class=%s provider_error_category=%s "
            "response_parse_status=%s canonical_schema_status=%s",
            attempt_obj.task_id.id if attempt_obj else None,
            attempt_obj.id if attempt_obj else None,
            page_start + 1,
            page_start + image_count,
            image_count,
            total_pages,
            image_count,
            total_image_bytes,
            elapsed_ms,
            retry_index,
            http_status_code,
            exception_class,
            provider_error_category,
            response_parse_status,
            canonical_schema_status,
        )
