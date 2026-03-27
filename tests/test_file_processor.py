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

def test_detect_native_pdf_returns_pdf_native(tmp_path):
    import pdfplumber
    from unittest.mock import patch, MagicMock
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "这是一段测试文字" * 20
    mock_pdf = MagicMock()
    mock_pdf.pages = [mock_page]
    mock_pdf.__enter__ = lambda s: s
    mock_pdf.__exit__ = MagicMock(return_value=False)
    with patch("pdfplumber.open", return_value=mock_pdf):
        from backend.services.file_processor import FileProcessor
        processor = FileProcessor(ocr_url="http://localhost:8080/ocr")
        file_type = processor.detect_file_type("fake.pdf")
        assert file_type == "pdf_native"

def test_detect_image_file_returns_image():
    from backend.services.file_processor import FileProcessor
    processor = FileProcessor(ocr_url="http://localhost:8080/ocr")
    assert processor.detect_file_type("photo.jpg") == "image"
    assert processor.detect_file_type("scan.png") == "image"
