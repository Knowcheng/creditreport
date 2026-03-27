import re
import logging
from typing import Optional
from backend.parsers.base import BaseParser, ReportResult

logger = logging.getLogger(__name__)


class EnterpriseParser(BaseParser):
    """企业征信自查版解析器（重构自旧代码 CR_CIParser）"""

    REPORT_PATTERNS = {
        "report_number": r"NO\.(\d+)",
        "company_name": r"企业名称[：:]\s*([^<\n\s]+)",
        "credit_num": r"中征码[：:](.+?)\s",
        "credit_code": r"统一社会信用代码[：:]\s*([0-9A-Z]{18})",
        "query_org": r"查询机构[：:](.+?)\s",
        "report_date": r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})",
    }

    def parse(self) -> ReportResult:
        info = self._extract_report_info()
        raw_data = {"report_info": info}

        try:
            raw_data["com_base"] = self._extract_com_base(info)
        except Exception as e:
            logger.warning(f"企业基本信息提取失败: {e}")
            raw_data["com_base"] = None

        try:
            raw_data["summary"] = self._extract_summary(info)
        except Exception as e:
            logger.warning(f"信息概要提取失败: {e}")
            raw_data["summary"] = None

        credit_accounts = self._extract_credit_accounts(info)

        return ReportResult(
            report_type="enterprise",
            report_number=info.get("report_number"),
            subject_name=info.get("company_name"),
            report_date=info.get("report_date"),
            raw_data=raw_data,
            credit_accounts=credit_accounts,
            query_records=[],
        )

    def _extract_report_info(self) -> dict:
        info = {}
        for key, pattern in self.REPORT_PATTERNS.items():
            match = re.search(pattern, self.text)
            info[key] = match.group(1).strip() if match else None

        # If report_number not found via NO. pattern, try 中征码 from tables
        if not info.get("report_number") and self.tables and len(self.tables[0]) >= 1:
            for row in self.tables[0]:
                if len(row) >= 2 and row[0] and '中征码' in str(row[0]):
                    info["report_number"] = str(row[1]).strip() if row[1] else None
                    break

        # If company_name not found via text regex, try tables
        if not info.get("company_name") and self.tables and len(self.tables[0]) >= 1:
            for row in self.tables[0]:
                if len(row) >= 2 and row[0] and '企业名称' in str(row[0]):
                    info["company_name"] = str(row[1]).strip() if row[1] else None
                    break

        return info

    def _extract_com_base(self, report_info: dict) -> Optional[dict]:
        if not self.tables:
            return None
        try:
            com_id_dict = {item[0]: item[1] for item in self.tables[0] if len(item) >= 2}
        except (IndexError, TypeError):
            com_id_dict = {}
        result = {**com_id_dict}
        result["报告编号"] = report_info.get("report_number")
        result["报告日期"] = report_info.get("report_date")
        return result

    def _extract_summary(self, report_info: dict) -> Optional[dict]:
        if not self.tables or len(self.tables) < 2:
            return None
        try:
            summary = dict(zip(self.tables[1][0], self.tables[1][1]))
            summary["报告编号"] = report_info.get("report_number")
            return summary
        except (IndexError, TypeError):
            return None

    def _extract_credit_accounts(self, report_info: dict) -> list:
        accounts = []
        if not self.tables or len(self.tables) < 2:
            return accounts
        try:
            row = self.tables[1]
            if len(row) > 3:
                accounts.append({
                    "account_type": "借贷交易汇总",
                    "institution": None,
                    "amount": None,
                    "balance": self._safe_float(row[3][1]) if len(row[3]) > 1 else None,
                    "status": "汇总",
                    "data_json": {"报告编号": report_info.get("report_number")},
                })
        except (IndexError, TypeError):
            pass
        return accounts

    @staticmethod
    def _safe_float(value) -> Optional[float]:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
