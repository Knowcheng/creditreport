import pytest
from unittest.mock import patch, MagicMock

def test_glm_ocr_returns_text_on_success():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"text": "识别出的文字内容"}
    with patch("httpx.post", return_value=mock_response):
        from backend.ocr.glm_ocr import GlmOcr
        ocr = GlmOcr(endpoint="http://localhost:8080/ocr")
        result = ocr.recognize_image(b"fake_image_bytes")
        assert result == "识别出的文字内容"

def test_glm_ocr_raises_on_failure():
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    with patch("httpx.post", return_value=mock_response):
        from backend.ocr import glm_ocr as glm_module
        import importlib
        importlib.reload(glm_module)
        from backend.ocr.glm_ocr import GlmOcr
        ocr = GlmOcr(endpoint="http://localhost:8080/ocr")
        with pytest.raises(RuntimeError, match="OCR 服务"):
            ocr.recognize_image(b"fake_image_bytes")
