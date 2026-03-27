import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.core.database import Base
from backend.models.db import User, Report

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Session = sessionmaker(bind=engine)

@pytest.fixture(autouse=True)
def setup():
    Base.metadata.create_all(engine)
    db = Session()
    user = User(id=1, username="test", password_hash="x", role="user")
    db.add(user)
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(engine)

def test_process_report_creates_db_record():
    from backend.parsers.base import ReportResult
    mock_result = ReportResult(
        report_type="enterprise",
        report_number="20240101120000001",
        subject_name="测试企业",
        report_date="2024-01-01T12:00:00",
        raw_data={"key": "val"},
    )
    with patch("backend.services.report_service.FileProcessor") as MockFP, \
         patch("backend.services.report_service.ReportParserFactory") as MockFactory, \
         patch("backend.services.report_service.ReportValidator") as MockValidator:

        MockFP.return_value.detect_file_type.return_value = "pdf_native"
        MockFP.return_value.extract_text_and_tables.return_value = ("企业信用报告文字", [])
        MockFactory.get_parser.return_value.parse.return_value = mock_result
        MockValidator.validate_report.return_value = (True, "通过")

        from backend.services.report_service import ReportService
        db = Session()
        service = ReportService(db=db)
        report_id = service.process_report(file_path="test.pdf", user_id=1)
        db.close()

        db = Session()
        report = db.query(Report).filter(Report.id == report_id).first()
        assert report is not None
        assert report.subject_name == "测试企业"
        assert report.parse_status == "success"
        db.close()
