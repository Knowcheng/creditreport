import pytest
import re
from dataclasses import asdict
from unittest.mock import MagicMock, patch
from backend.parsers.base import ReportResult

def test_report_result_has_required_fields():
    result = ReportResult(
        report_type="enterprise",
        report_number="20240101120000001",
        subject_name="测试企业有限公司",
        report_date="2024-01-01",
        raw_data={"key": "value"},
    )
    d = asdict(result)
    assert d["report_type"] == "enterprise"
    assert d["subject_name"] == "测试企业有限公司"
    assert d["raw_data"] == {"key": "value"}


def test_enterprise_parser_extracts_report_info():
    sample_text = (
        "NO.20240101120000001\n"
        "企业名称：测试科技有限公司 \n"
        "统一社会信用代码：91110000123456789X\n"
        "查询机构：某商业银行 \n"
        "2024-01-01T12:00:00\n"
    )
    sample_tables = [
        [["统一社会信用代码", "91110000123456789X"]],
        [["字段1", "值1"], ["借贷余额", "100"], ["被追偿类余额", "0"],
         ["关注类余额", "0"], ["不良类余额", "0"],
         ["担保余额", "200"], ["担保关注", "0"], ["担保不良", "0"]],
    ]
    from backend.parsers.enterprise import EnterpriseParser
    parser = EnterpriseParser(text=sample_text, tables=sample_tables, file_path="test.pdf")
    result = parser.parse()
    assert result.report_type == "enterprise"
    assert result.report_number == "20240101120000001"
    assert result.subject_name == "测试科技有限公司"
    assert result.report_date == "2024-01-01T12:00:00"


def test_personal_detail_parser_returns_correct_type():
    sample_tables = [
        [
            ["报告编号：20240201000001", "", "", "报告时间：2024-02-01"],
            ["被查询者姓名", "证件类型", "证件号码"],
            ["张三", "身份证", "110101199001011234"],
        ]
    ]
    from backend.parsers.personal_detail import PersonalDetailParser
    parser = PersonalDetailParser(text="个人信用报告 身份信息", tables=sample_tables, file_path="test.pdf")
    result = parser.parse()
    assert result.report_type == "personal_detail"

def test_personal_simple_parser_returns_correct_type():
    sample_text = (
        "个人信用报告\n"
        "报告编号：20240301 报告时间：2024-03-01\n"
        "姓名：李四 证件号码：110101199001012345 已婚\n"
    )
    from backend.parsers.personal_simple import PersonalSimpleParser
    parser = PersonalSimpleParser(text=sample_text, tables=[], file_path="test.pdf")
    result = parser.parse()
    assert result.report_type == "personal_simple"
