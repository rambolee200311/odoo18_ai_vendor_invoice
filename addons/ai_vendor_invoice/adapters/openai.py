# © 2024 Wukong Digital. License LGPL-3.

import json

from openai import OpenAI

from .aibase import BaseVisionAIProviderAdapter
from .base import AIProviderPermanentError
from ..services.native_document_projection import document_to_canonical


class OpenAIAIProviderAdapter(BaseVisionAIProviderAdapter):
    provider_name = "openai"
    provider_label = "OpenAI"
    supported_input_modes = frozenset({"rendered_images", "native_pdf"})

    def _build_client(self, provider_config):
        return OpenAI(
            api_key=self._credentials(provider_config),
            base_url=provider_config.api_base_url,
            timeout=provider_config.http_timeout,
            max_retries=0,
        )

    def _build_payload(self, provider_config, images):
        return self._vision_payload(provider_config, images)

    def parse_pdf(self, provider_input, provider_config, max_attempt_retry=0, attempt_obj=None):
        if provider_input.get("mode", "rendered_images") == "native_pdf":
            document, raw_response, _content = self.parse_native_pdf(
                provider_input,
                provider_config,
                self._native_document_instructions(),
            )
            return document_to_canonical(document), raw_response
        return super().parse_pdf(
            provider_input,
            provider_config,
            max_attempt_retry,
            attempt_obj,
        )

    @staticmethod
    def _native_document_instructions():
        return """Extract the supplied invoice as a document-level JSON object.
Return valid JSON only with document_type and invoice.lines. Keep one
independent invoice business record as one line; keep nested charge components
inside that record and do not create extra lines. When a line contains a
reconciliation clue, preserve it as reconciliation_clues with the original
label and value. Do not infer a clue type or match transport orders. Include
the invoice number, date, currency, totals, supplier, and tax values when
present."""

    def parse_native_pdf(self, provider_input, provider_config, instructions):
        """Call OpenAI native PDF transport without applying business normalization."""
        self.validate_input_mode(provider_input["mode"])
        document_bytes = provider_input["document_bytes"]
        client = self._build_client(provider_config)
        uploaded_file = client.files.create(
            file=("source.pdf", document_bytes, "application/pdf"),
            purpose="user_data",
            timeout=provider_config.http_timeout,
        )
        response = client.responses.create(
            model=provider_config.model_name,
            reasoning={"effort": "low"},
            input=[{
                "role": "user",
                "content": [
                    {
                        "type": "input_file",
                        "file_id": uploaded_file.id,
                    },
                    {
                        "type": "input_text",
                        "text": instructions,
                    },
                ],
            }],
            stream=False,
            timeout=provider_config.http_timeout,
        )
        raw_response = response.model_dump_json().encode("utf-8")
        content = response.output_text
        if not isinstance(content, str) or not content.strip():
            raise AIProviderPermanentError("OpenAI native PDF response was empty.")
        return json.loads(content), raw_response, content
