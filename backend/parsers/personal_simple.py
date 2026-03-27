import re
import logging
from datetime import datetime
from typing import Optional
from backend.parsers.base import BaseParser, ReportResult

logger = logging.getLogger(__name__)


class PersonalSimpleParser(BaseParser):
    """个人征信简版解析器（重构自旧代码 CR_PSParser）"""

    def parse(self) -> ReportResult:
        base_info = self._extract_base_info()
        credit_accounts = self._extract_credit_summary()
        query_records = self._extract_query_summary()

        name = None
        report_number = None
        report_date = None
        if base_info:
            name = base_info.get("姓名")
            report_number = base_info.get("报告编号")
            report_date = base_info.get("报告日期")

        return ReportResult(
            report_type="personal_simple",
            report_number=report_number,
            subject_name=name,
            report_date=report_date,
            raw_data={"base_info": base_info},
            credit_accounts=credit_accounts,
            query_records=query_records,
        )

    def _extract_base_info(self) -> Optional[dict]:
        lines = self.text.splitlines()
        if len(lines) < 3:
            return None
        try:
            temp = lines[1].split("：")
            report_date = temp[2] if len(temp) > 2 else None
            report_num = temp[1].split(" ")[0] if len(temp) > 1 else None
            temp_1 = lines[2].split("：")
            name = temp_1[1].split(" ")[1] if len(temp_1) > 1 and len(temp_1[1].split(" ")) > 1 else None
            identity = temp_1[3].split(" ")[0] if len(temp_1) > 3 else None
            marry = temp_1[3].split(" ")[1] if len(temp_1) > 3 and len(temp_1[3].split(" ")) > 1 else None

            age = None
            if identity and len(identity) >= 14:
                try:
                    birthdate = datetime.strptime(identity[6:14], "%Y%m%d")
                    today = datetime.today()
                    age = today.year - birthdate.year - (
                        (today.month, today.day) < (birthdate.month, birthdate.day)
                    )
                except ValueError:
                    pass

            return {
                "报告日期": report_date,
                "报告编号": report_num,
                "姓名": name,
                "证件号码": identity,
                "年龄": age,
                "婚姻": marry,
            }
        except (IndexError, AttributeError) as e:
            logger.warning(f"个人简版基础信息提取失败: {e}")
            return None

    def _extract_credit_summary(self) -> list:
        return []

    def _extract_query_summary(self) -> list:
        return []
