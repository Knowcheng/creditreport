from backend.parsers.base import BaseParser
from backend.parsers.enterprise import EnterpriseParser
from backend.parsers.personal_detail import PersonalDetailParser
from backend.parsers.personal_simple import PersonalSimpleParser


class ReportParserFactory:
    @staticmethod
    def get_parser(text: str, tables: list, file_path: str) -> BaseParser:
        first_page = text[:500]
        if "企业信用报告" in first_page:
            return EnterpriseParser(text=text, tables=tables, file_path=file_path)
        if "个人信用报告" in first_page and "身份信息" in first_page:
            return PersonalDetailParser(text=text, tables=tables, file_path=file_path)
        if "个人信用报告" in first_page and "信贷记录" in first_page:
            return PersonalSimpleParser(text=text, tables=tables, file_path=file_path)
        raise ValueError(f"无法识别报告类型，请确认上传的是人民银行征信报告")
