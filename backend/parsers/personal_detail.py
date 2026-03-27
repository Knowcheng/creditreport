import re
import logging
from typing import Optional
from backend.parsers.base import BaseParser, ReportResult

logger = logging.getLogger(__name__)


class PersonalDetailParser(BaseParser):
    """个人征信详版解析器（重构自旧代码 CR_PDParser）"""

    def parse(self) -> ReportResult:
        if not self.tables:
            return self._parse_ocr()

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

    def _parse_ocr(self) -> ReportResult:
        text = self.text

        # Extract report_number
        m = re.search(r'报告编号[：:]\s*(\d+)', text)
        report_number = m.group(1) if m else None

        # Extract report_date
        m = re.search(r'报告时间[：:]\s*([\d]{4}[\./][\d./ :]+)', text)
        report_date = m.group(1).strip() if m else None

        # Extract subject_name: row after header with 被查询者姓名
        m = re.search(r'被查询者姓名.*?</tr>\s*<tr[^>]*>\s*<td[^>]*>(.*?)</td>', text, re.DOTALL)
        subject_name = m.group(1).strip() if m else None

        # Extract id_number (3rd td in same data row)
        id_match = re.search(
            r'被查询者姓名.*?</tr>\s*<tr[^>]*>\s*<td[^>]*>.*?</td>\s*<td[^>]*>.*?</td>\s*<td[^>]*>([\d]{15,18}[xX]?)</td>',
            text, re.DOTALL
        )
        id_number = id_match.group(1) if id_match else None

        # Extract credit accounts from 信贷交易信息明细 section
        credit_accounts = self._extract_credit_accounts_from_ocr(text)

        # Extract query records
        query_records = self._extract_query_records_from_ocr(text)

        base_info = {
            "report_number": report_number,
            "report_date": report_date,
            "subject_name": subject_name,
            "id_number": id_number,
        }

        return ReportResult(
            report_type="personal_detail",
            report_number=report_number,
            subject_name=subject_name,
            report_date=report_date,
            raw_data={"base_info": base_info},
            credit_accounts=credit_accounts,
            query_records=query_records,
        )

    def _extract_credit_accounts_from_ocr(self, text: str) -> list:
        accounts = []
        # Find credit detail section
        section_start = text.find('三信贷交易信息明细')
        if section_start == -1:
            section_start = text.find('信贷交易信息明细')
        if section_start == -1:
            return accounts

        section_text = text[section_start:]
        # Find all HTML tables in this section
        table_pattern = re.compile(r'<table[^>]*>(.*?)</table>', re.DOTALL)

        for table_match in table_pattern.finditer(section_text):
            table_html = table_match.group(1)
            # Extract all td contents
            cells = re.findall(r'<td[^>]*>(.*?)</td>', table_html, re.DOTALL)
            cells = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]  # strip HTML tags

            if len(cells) >= 4 and '管理机构' in cells:
                # This is a header row table - skip
                continue

            # If this looks like account data (has institution name, amount, etc.)
            if len(cells) >= 4 and cells and cells[0] and not any(
                h in cells[0] for h in ['管理机构', '账户标识', '账户类型']
            ):
                account = {
                    "account_type": "贷款",
                    "institution": cells[0] if cells else None,
                    "amount": None,
                    "balance": None,
                    "status": "正常",
                    "data_json": {"cells": cells[:8]},
                }
                accounts.append(account)

        return accounts

    def _extract_query_records_from_ocr(self, text: str) -> list:
        records = []
        # Find query records section
        qi = text.find('查询记录')
        if qi == -1:
            return records
        query_text = text[qi:]

        # Pattern: date + org + reason in table cells
        pattern = re.compile(
            r'<td[^>]*>(\d{4}[./]\d{2}[./]\d{2})</td>\s*<td[^>]*>([\u4e00-\u9fa5\w（）、\s]+?)</td>\s*<td[^>]*>([\u4e00-\u9fa5]+)</td>',
            re.DOTALL
        )
        for m in pattern.finditer(query_text):
            records.append({
                "query_date": m.group(1),
                "query_org": m.group(2).strip(),
                "query_reason": m.group(3).strip(),
            })
        return records

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
