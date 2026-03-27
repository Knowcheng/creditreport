import httpx
import base64
import logging

logger = logging.getLogger(__name__)


class GlmOcr:
    """GLM-OCR 本地服务封装（通过 HTTP API 调用）"""

    def __init__(self, endpoint: str):
        self.endpoint = endpoint

    def recognize_image(self, image_bytes: bytes) -> str:
        image_b64 = base64.b64encode(image_bytes).decode()
        # GLM-OCR server accepts images as data URIs
        data_uri = f"data:image/jpeg;base64,{image_b64}"
        # Use trust_env=False to bypass system proxies for local connections
        with httpx.Client(trust_env=False) as client:
            response = client.post(
                self.endpoint,
                json={"images": [data_uri]},
                headers={"Content-Type": "application/json"},
                timeout=120.0,
            )
        if response.status_code != 200:
            raise RuntimeError(f"OCR 服务返回错误: {response.status_code} {response.text}")
        return response.json().get("markdown_result", "")

    def recognize_file(self, file_path: str) -> str:
        with open(file_path, "rb") as f:
            return self.recognize_image(f.read())
