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
        response = httpx.post(
            self.endpoint,
            json={"image": image_b64},
            timeout=60.0,
        )
        if response.status_code != 200:
            raise RuntimeError(f"OCR 服务返回错误: {response.status_code} {response.text}")
        return response.json().get("text", "")

    def recognize_file(self, file_path: str) -> str:
        with open(file_path, "rb") as f:
            return self.recognize_image(f.read())
