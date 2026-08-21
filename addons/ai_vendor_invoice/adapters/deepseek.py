# © 2024 Wukong Digital. License LGPL-3.
import base64

from .base import BaseAIProviderAdapter


class DeepSeekAIProviderAdapter(BaseAIProviderAdapter):
    provider_name = "deepseek"

    def parse_pdf(self, pdf_attachment, provider_config, max_attempt_retry=0, attempt_obj=None):
        payload = {
            "model": provider_config.model_name,
            "messages": [{
                "role": "user",
                "content": base64.b64encode(pdf_attachment.raw or b"").decode(),
            }],
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": "Bearer " + self._credentials(provider_config)}
        body, raw = self._request(
            provider_config, payload, headers, max_attempt_retry, attempt_obj
        )
        return self._canonical(body), raw
