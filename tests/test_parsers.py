import pytest
from dataclasses import asdict
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
