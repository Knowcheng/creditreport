import logging
from sqlalchemy.orm import Session
from backend.models.db import Report, EnterpriseReport, PersonalReport, CreditAccount, QueryRecord
from backend.services.file_processor import FileProcessor
from backend.parsers.factory import ReportParserFactory
from backend.parsers.validator import ReportValidator

logger = logging.getLogger(__name__)


class ReportService:
    def __init__(self, db: Session):
        self.db = db
        self.file_processor = FileProcessor()

    def process_report(self, file_path: str, user_id: int) -> int:
        file_type = self.file_processor.detect_file_type(file_path)

        report = Report(
            user_id=user_id,
            file_path=file_path,
            file_type=file_type,
            report_type="unknown",
            parse_status="pending",
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)

        try:
            text, tables = self.file_processor.extract_text_and_tables(file_path, file_type)
            parser = ReportParserFactory.get_parser(text=text, tables=tables, file_path=file_path)
            result = parser.parse()

            is_valid = None
            if file_type == "pdf_native":
                is_valid, _ = ReportValidator.validate_report(
                    {"report_date": result.report_date, "report_number": result.report_number},
                    file_path,
                )

            report.report_type = result.report_type
            report.report_number = result.report_number
            report.subject_name = result.subject_name
            report.report_date = result.report_date
            report.is_valid = is_valid
            report.parse_status = "success"

            self._save_detail(report.id, result)
            self.db.commit()

        except Exception as e:
            logger.error(f"报告解析失败: {e}", exc_info=True)
            report.parse_status = "failed"
            self.db.commit()
            raise

        return report.id

    def _save_detail(self, report_id: int, result) -> None:
        if result.report_type == "enterprise":
            self.db.add(EnterpriseReport(
                report_id=report_id,
                company_name=result.subject_name,
                data_json=result.raw_data,
            ))
        else:
            self.db.add(PersonalReport(
                report_id=report_id,
                name=result.subject_name,
                data_json=result.raw_data,
            ))

        for acc in result.credit_accounts:
            self.db.add(CreditAccount(
                report_id=report_id,
                account_type=acc.get("account_type"),
                institution=acc.get("institution"),
                amount=acc.get("amount"),
                balance=acc.get("balance"),
                status=acc.get("status"),
                data_json=acc.get("data_json"),
            ))

        for qr in result.query_records:
            self.db.add(QueryRecord(
                report_id=report_id,
                query_date=qr.get("query_date"),
                query_org=qr.get("query_org"),
                query_reason=qr.get("query_reason"),
            ))
