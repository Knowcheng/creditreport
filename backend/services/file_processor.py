import os
import logging
from typing import Tuple
import pdfplumber
from backend.ocr.glm_ocr import GlmOcr
from backend.core.config import settings

logger = logging.getLogger(__name__)

NATIVE_PDF_TEXT_THRESHOLD = 50


class FileProcessor:
    """文件类型检测 + OCR 预处理"""

    def __init__(self, ocr_url: str = None):
        self.ocr = GlmOcr(endpoint=ocr_url or settings.OCR_URL)

    def detect_file_type(self, file_path: str) -> str:
        ext = os.path.splitext(file_path)[1].lower()
        if ext in (".jpg", ".jpeg", ".png", ".bmp", ".tiff"):
            return "image"
        if ext == ".pdf":
            return self._detect_pdf_type(file_path)
        return "image"

    def _detect_pdf_type(self, file_path: str) -> str:
        try:
            with pdfplumber.open(file_path) as pdf:
                text = "".join(
                    page.extract_text() or "" for page in pdf.pages[:2]
                )
            if len(text.strip()) >= NATIVE_PDF_TEXT_THRESHOLD:
                return "pdf_native"
            return "pdf_scanned"
        except Exception as e:
            logger.warning(f"PDF 类型检测失败，按扫描件处理: {e}")
            return "pdf_scanned"

    def extract_text_and_tables(self, file_path: str, file_type: str) -> Tuple[str, list]:
        if file_type == "pdf_native":
            return self._extract_from_native_pdf(file_path)
        elif file_type == "pdf_scanned":
            return self._extract_from_scanned_pdf(file_path)
        else:
            return self._extract_from_image(file_path)

    def _extract_from_native_pdf(self, file_path: str) -> Tuple[str, list]:
        with pdfplumber.open(file_path) as pdf:
            text = "".join(page.extract_text() or "" for page in pdf.pages)
            tables = []
            for page in pdf.pages:
                page_tables = page.extract_tables()
                if page_tables:
                    for table in page_tables:
                        if table:
                            if tables and len(table[0]) == len(tables[-1][0]):
                                tables[-1] += table
                            else:
                                tables.append(table)
        tables = self._clean_tables(tables)
        return text, tables

    def _extract_from_scanned_pdf(self, file_path: str) -> Tuple[str, list]:
        try:
            from pdf2image import convert_from_path
            import io
            images = convert_from_path(file_path)
            texts = []
            for img in images:
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                text = self.ocr.recognize_image(buf.getvalue())
                texts.append(text)
            return "\n".join(texts), []
        except Exception as e:
            logger.error(f"扫描件处理失败: {e}")
            return "", []

    def _extract_from_image(self, file_path: str) -> Tuple[str, list]:
        text = self.ocr.recognize_file(file_path)
        return text, []

    @staticmethod
    def _clean_tables(tables: list) -> list:
        for i in range(len(tables)):
            for j in range(len(tables[i])):
                for k in range(len(tables[i][j])):
                    if isinstance(tables[i][j][k], str):
                        tables[i][j][k] = tables[i][j][k].replace("\n", "")
        return tables
