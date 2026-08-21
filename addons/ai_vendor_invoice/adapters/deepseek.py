# © 2024 Wukong Digital. License LGPL-3.
import base64

from .base import BaseAIProviderAdapter


class DeepSeekAIProviderAdapter(BaseAIProviderAdapter):
    provider_name = "deepseek"

    def parse_pdf(self, provider_input, provider_config, max_attempt_retry=0, attempt_obj=None):
        payload = {
            "model": provider_config.model_name,
            "messages": [{
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "data:image/png;base64,%s"
                            % base64.b64encode(image).decode(),
                        },
                    }
                    for image in provider_input["images"]
                ],
            }],
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": "Bearer " + self._credentials(provider_config)}
        body, raw = self._request(
            provider_config, payload, headers, max_attempt_retry, attempt_obj
        )
        return self._canonical(body), raw
