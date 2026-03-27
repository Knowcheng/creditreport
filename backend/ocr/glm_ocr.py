import httpx
import base64
import logging

logger = logging.getLogger(__name__)


class GlmOcr:
    """GLM-OCR 服务封装，支持两种接口模式：
    - MaaS 模式（默认）: POST /glmocr/parse  {"images": [...]} → {"markdown_result": "..."}
    - Chat 模式: POST /chat/completions (OpenAI 格式)  → choices[0].message.content
    """

    def __init__(self, endpoint: str):
        self.endpoint = endpoint
        # Auto-detect mode from endpoint URL
        self._chat_mode = "chat/completions" in endpoint

    def recognize_image(self, image_bytes: bytes) -> str:
        image_b64 = base64.b64encode(image_bytes).decode()
        data_uri = f"data:image/jpeg;base64,{image_b64}"
        with httpx.Client(trust_env=False) as client:
            if self._chat_mode:
                return self._recognize_chat(client, data_uri)
            else:
                return self._recognize_maas(client, data_uri)

    def _recognize_maas(self, client: httpx.Client, data_uri: str) -> str:
        response = client.post(
            self.endpoint,
            json={"images": [data_uri]},
            headers={"Content-Type": "application/json"},
            timeout=120.0,
        )
        if response.status_code != 200:
            raise RuntimeError(f"OCR 服务返回错误: {response.status_code} {response.text}")
        return response.json().get("markdown_result", "")

    def _recognize_chat(self, client: httpx.Client, data_uri: str) -> str:
        payload = {
            "model": "mlx-community/GLM-OCR-bf16",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_uri}},
                        {"type": "text", "text": "请识别图片中的所有文字，以Markdown格式输出，保留表格结构。"},
                    ],
                }
            ],
            "max_tokens": 4096,
            "temperature": 0.0,
        }
        response = client.post(
            self.endpoint,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=180.0,
        )
        if response.status_code != 200:
            raise RuntimeError(f"OCR 服务返回错误: {response.status_code} {response.text}")
        return response.json()["choices"][0]["message"]["content"]

    def recognize_file(self, file_path: str) -> str:
        with open(file_path, "rb") as f:
            return self.recognize_image(f.read())
