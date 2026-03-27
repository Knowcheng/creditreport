from backend.parsers.base import BaseParser
from backend.parsers.enterprise import EnterpriseParser
from backend.parsers.personal_detail import PersonalDetailParser
from backend.parsers.personal_simple import PersonalSimpleParser


class ReportParserFactory:
    @staticmethod
    def get_parser(text: str, tables: list, file_path: str) -> BaseParser:
        # Search broader range to handle OCR output (Markdown format, longer headers)
        search_text = text[:3000]
        # Enterprise: explicit header OR enterprise-specific fields (for OCR/photo input)
        is_enterprise = (
            "企业信用报告" in search_text
            or ("企业名称" in search_text and "统一社会信用代码" in search_text)
            or ("企业名称" in search_text and "中征码" in search_text)
        )
        if is_enterprise:
            return EnterpriseParser(text=text, tables=tables, file_path=file_path)
        # Personal: check for header keyword or OCR-specific field that appears even without page header
        is_personal = (
            "个人信用报告" in search_text
            or "个人版" in search_text
            or "被查询者姓名" in search_text  # OCR pages may omit header but keep this field
        )
        if is_personal:
            if "身份信息" in text:
                return PersonalDetailParser(text=text, tables=tables, file_path=file_path)
            return PersonalSimpleParser(text=text, tables=tables, file_path=file_path)
        raise ValueError(f"无法识别报告类型，请确认上传的是人民银行征信报告")
