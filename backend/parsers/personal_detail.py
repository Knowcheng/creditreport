import logging
from typing import Optional
from backend.parsers.base import BaseParser, ReportResult

logger = logging.getLogger(__name__)


class PersonalDetailParser(BaseParser):
    """个人征信详版解析器（重构自旧代码 CR_PDParser）"""

    def parse(self) -> ReportResult:
        report_info = self._extract_report_info()
        id_info = self._extract_id_info()
        query_records = self._extract_query_records()

        raw_data = {
            "report_info": report_info,
            "id_info": id_info,
            "addr_info": self._safe_extract(self._extract_addr_info),
            "career_info": self._safe_extract(self._extract_career_info),
            "account_info": self._safe_extract(self._extract_account_info),
        }

        return ReportResult(
            report_type="personal_detail",
            report_number=report_info.get("report_number") if report_info else None,
            subject_name=id_info.get("被查询者姓名") if id_info else None,
            report_date=report_info.get("report_date") if report_info else None,
            raw_data=raw_data,
            credit_accounts=[],
            query_records=query_records,
        )

    def _extract_report_info(self) -> Optional[dict]:
        if not self.tables or len(self.tables[0]) < 3:
            return None
        try:
            info = {}
            keys = self.tables[0][1]
            values = self.tables[0][2]
            for k, v in zip(keys, values):
                info[k] = v
            info["report_number"] = self.tables[0][0][0].split("：")[1] if "：" in str(self.tables[0][0][0]) else None
            info["report_date"] = self.tables[0][0][3].split("：")[1] if len(self.tables[0][0]) > 3 else None
            return info
        except (IndexError, TypeError) as e:
            logger.warning(f"报告信息提取失败: {e}")
            return None

    def _extract_id_info(self) -> Optional[dict]:
        if not self.tables:
            return None
        for table in self.tables:
            for row in table:
                for cell in row:
                    if cell and "被查询者姓名" in str(cell):
                        return {"被查询者姓名": self._find_name_in_tables()}
        return None

    def _find_name_in_tables(self) -> Optional[str]:
        for table in self.tables:
            for i, row in enumerate(table):
                for cell in row:
                    if cell and "被查询者姓名" in str(cell):
                        if i + 1 < len(table):
                            return table[i + 1][0] if table[i + 1] else None
        return None

    def _extract_addr_info(self) -> Optional[list]:
        return None

    def _extract_career_info(self) -> Optional[list]:
        return None

    def _extract_account_info(self) -> Optional[list]:
        return None

    def _extract_query_records(self) -> list:
        return []

    def _safe_extract(self, func) -> Optional[dict]:
        try:
            return func()
        except Exception as e:
            logger.warning(f"{func.__name__} 提取失败: {e}")
            return None
