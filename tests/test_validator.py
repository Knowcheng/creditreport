def test_check_reporttime_no_valid():
    from backend.parsers.validator import ReportValidator
    report_info = {
        "report_date": "2024-01-01T12:00:00",
        "report_number": "20240101120000001"
    }
    assert ReportValidator.check_reporttime_no(report_info) is True

def test_check_reporttime_no_invalid():
    from backend.parsers.validator import ReportValidator
    report_info = {
        "report_date": "2024-01-01T12:00:00",
        "report_number": "99990101120000001"
    }
    assert ReportValidator.check_reporttime_no(report_info) is False
