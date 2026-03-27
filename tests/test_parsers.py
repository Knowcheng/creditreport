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


def test_factory_returns_enterprise_parser_for_enterprise_text():
    from backend.parsers.factory import ReportParserFactory
    parser = ReportParserFactory.get_parser(
        text="企业信用报告\nNO.123", tables=[], file_path="test.pdf"
    )
    from backend.parsers.enterprise import EnterpriseParser
    assert isinstance(parser, EnterpriseParser)

def test_factory_returns_personal_detail_for_detail_text():
    from backend.parsers.factory import ReportParserFactory
    parser = ReportParserFactory.get_parser(
        text="个人信用报告\n身份信息", tables=[], file_path="test.pdf"
    )
    from backend.parsers.personal_detail import PersonalDetailParser
    assert isinstance(parser, PersonalDetailParser)

def test_factory_returns_personal_simple_for_simple_text():
    from backend.parsers.factory import ReportParserFactory
    parser = ReportParserFactory.get_parser(
        text="个人信用报告\n信贷记录", tables=[], file_path="test.pdf"
    )
    from backend.parsers.personal_simple import PersonalSimpleParser
    assert isinstance(parser, PersonalSimpleParser)

def test_factory_raises_for_unknown_text():
    from backend.parsers.factory import ReportParserFactory
    with pytest.raises(ValueError, match="无法识别"):
        ReportParserFactory.get_parser(text="无关内容", tables=[], file_path="test.pdf")


# ── OCR mode tests (scanned PDF / photo) ─────────────────────────────────────

# Minimal OCR HTML matching real GLM-OCR output structure for 个人信用报告（本人版）
_OCR_PERSONAL_DETAIL_TEXT = """
## 个人信用报告

（本人版）

<table><tr><td colspan="3">报告编号：2024072314523944185099</td><td colspan="2">报告时间：2024.07.23 14:52:39</td></tr><tr><td>被查询者姓名</td><td>被查询者证件类型</td><td>被查询者证件号码</td><td>查询机构</td><td>查询原因</td></tr><tr><td>尚杨杰</td><td>身份证</td><td>510211197712219011</td><td>本人</td><td>本人查询（自助查询机）</td></tr></table>

## 一 个人基本信息

（一）身份信息

<table border="1"><tr><td colspan="2">性别</td><td>出生日期</td></tr><tr><td colspan="2">男</td><td>1977.12.21</td></tr></table>

## 二 信息概要

<table border="1"><tr><td colspan="5">贷款信息汇总</td></tr><tr><td>账户数</td><td>3</td></tr></table>

## 三 信贷交易信息明细

## （一）非循环贷账户

<div align="center">账户1</div>

<table border="1"><tr><td colspan="2">管理机构</td><td colspan="2">账户标识</td><td colspan="2">开立日期</td><td colspan="2">到期日期</td><td colspan="2">余额</td><td colspan="2">账户类型</td></tr><tr><td colspan="2">中国银行股份有限公司重庆市分行</td><td colspan="2">D10027910H0001PPD20240112000003001349</td><td colspan="2">2024.01.12</td><td colspan="2">2024.10.12</td><td colspan="2">18,100</td><td colspan="2">消费性贷款</td></tr></table>

<div align="center">账户2</div>

<table border="1"><tr><td colspan="2">管理机构</td><td colspan="2">账户标识</td><td colspan="2">开立日期</td><td colspan="2">到期日期</td><td colspan="2">余额</td><td colspan="2">账户类型</td></tr><tr><td colspan="2">平安银行股份有限公司信用卡中心</td><td colspan="2">A20001234</td><td colspan="2">2022.06.01</td><td colspan="2">2025.06.01</td><td colspan="2">50,000</td><td colspan="2">个人经营类贷款</td></tr></table>

## 四 查询记录

<table border="1"><tr><td>查询日期</td><td>查询机构名称</td><td>查询原因</td></tr><tr><td>2024.06.07</td><td>中国银行股份有限公司重庆市分行</td><td>贷款审批</td></tr><tr><td>2024.01.15</td><td>平安银行股份有限公司信用卡中心</td><td>信用卡审批</td></tr></table>
"""


def test_personal_detail_ocr_extracts_subject_name():
    from backend.parsers.personal_detail import PersonalDetailParser
    parser = PersonalDetailParser(text=_OCR_PERSONAL_DETAIL_TEXT, tables=[], file_path="scan.pdf")
    result = parser.parse()
    assert result.subject_name == "尚杨杰"


def test_personal_detail_ocr_extracts_report_number():
    from backend.parsers.personal_detail import PersonalDetailParser
    parser = PersonalDetailParser(text=_OCR_PERSONAL_DETAIL_TEXT, tables=[], file_path="scan.pdf")
    result = parser.parse()
    assert result.report_number == "2024072314523944185099"


def test_personal_detail_ocr_extracts_report_date():
    from backend.parsers.personal_detail import PersonalDetailParser
    parser = PersonalDetailParser(text=_OCR_PERSONAL_DETAIL_TEXT, tables=[], file_path="scan.pdf")
    result = parser.parse()
    assert result.report_date is not None
    assert "2024" in result.report_date


def test_personal_detail_ocr_extracts_credit_accounts():
    from backend.parsers.personal_detail import PersonalDetailParser
    parser = PersonalDetailParser(text=_OCR_PERSONAL_DETAIL_TEXT, tables=[], file_path="scan.pdf")
    result = parser.parse()
    assert len(result.credit_accounts) == 2
    institutions = [a["institution"] for a in result.credit_accounts]
    assert "中国银行股份有限公司重庆市分行" in institutions
    assert "平安银行股份有限公司信用卡中心" in institutions


def test_personal_detail_ocr_extracts_query_records():
    from backend.parsers.personal_detail import PersonalDetailParser
    parser = PersonalDetailParser(text=_OCR_PERSONAL_DETAIL_TEXT, tables=[], file_path="scan.pdf")
    result = parser.parse()
    assert len(result.query_records) == 2
    dates = [r["query_date"] for r in result.query_records]
    assert "2024.06.07" in dates
