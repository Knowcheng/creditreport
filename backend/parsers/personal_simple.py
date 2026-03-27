import re
import logging
from datetime import datetime
from typing import Optional
from backend.parsers.base import BaseParser, ReportResult

logger = logging.getLogger(__name__)


class PersonalSimpleParser(BaseParser):
    """个人征信简版解析器（重构自旧代码 CR_PSParser）"""

    def parse(self) -> ReportResult:
        # Detect OCR mode: no tables and HTML table tags present in text
        if not self.tables and '<table' in self.text:
            return self._parse_ocr()

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

    def _parse_ocr(self) -> ReportResult:
        text = self.text

        # Extract report_number
        m = re.search(r'报告编号[：:]\s*(\d+)', text)
        report_number = m.group(1) if m else None

        # Extract report_date
        m = re.search(r'报告时间[：:]\s*([\d]{4}[\./][\d./ :]+)', text)
        report_date = m.group(1).strip() if m else None

        # Extract subject_name from HTML table: row after header with 被查询者姓名
        m = re.search(r'被查询者姓名.*?</tr>\s*<tr[^>]*>\s*<td[^>]*>(.*?)</td>', text, re.DOTALL)
        subject_name = m.group(1).strip() if m else None

        # Extract id_number (3rd td in same data row)
        id_match = re.search(
            r'被查询者姓名.*?</tr>\s*<tr[^>]*>\s*<td[^>]*>.*?</td>\s*<td[^>]*>.*?</td>\s*<td[^>]*>([\d]{15,18}[xX]?)</td>',
            text, re.DOTALL
        )
        id_number = id_match.group(1) if id_match else None

        # For OCR simple reports the credit/query text may still be plain text
        # Try the existing plain-text extractors which work on self.text
        credit_accounts = self._extract_credit_summary()
        query_records = self._extract_query_summary()

        base_info = {
            "报告编号": report_number,
            "报告日期": report_date,
            "姓名": subject_name,
            "证件号码": id_number,
        }

        return ReportResult(
            report_type="personal_simple",
            report_number=report_number,
            subject_name=subject_name,
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
        accounts = []

        # Clean page markers and join wrapped lines
        cleaned = re.sub(r'第 \d+ 页，共 \d+ 页', '', self.text)

        # Find the credit cards/loans section: from first card section marker to query records
        query_marker = '查询记录'
        query_idx = cleaned.find(query_marker)
        credit_section = cleaned[:query_idx] if query_idx >= 0 else cleaned

        # Join wrapped lines: lines that don't start a new numbered entry get appended
        raw_lines = credit_section.splitlines()
        joined_lines = []
        for line in raw_lines:
            stripped = line.strip()
            if not stripped:
                continue
            # New entry starts with a digit followed by . or space+digit
            if re.match(r'^\d+[.\s]', stripped) or joined_lines == []:
                joined_lines.append(stripped)
            else:
                # Continuation line - append to previous
                if joined_lines:
                    joined_lines[-1] += stripped
                else:
                    joined_lines.append(stripped)

        card_patterns = {
            '发卡日期': re.compile(r'(\d{4}年\d{2}月\d{2}日)'),
            '金融机构': re.compile(r'\d{4}年\d{2}月\d{2}日([\u4e00-\u9fa5]+(?:股份有限公司|有限责任公司|有限公司)[\u4e00-\u9fa5]*)发放的贷记卡'),
            '货币种类': re.compile(r'（([\u4e00-\u9fa5]+账户)'),
            '卡号尾号': re.compile(r'卡片尾号：(\d{4})'),
            '授信额度': re.compile(r'信用额度([\d,]+)'),
            '已用额度': re.compile(r'已使用额度([\d,]+)'),
            '余额': re.compile(r'余额(?:为)?([\d,]+)'),
        }

        loan_patterns = {
            '借款日期': re.compile(r'(\d{4}年\d{2}月\d{2}日)'),
            '金融机构': re.compile(r'\d{4}年\d{2}月\d{2}日([\u4e00-\u9fa5]+(?:股份有限公司|有限责任公司|有限公司|股份公司)[\u4e00-\u9fa5]*)(?:发放|为)'),
            '借款金额': re.compile(r'([\d,]+)元（人民币）'),
            '余额': re.compile(r'余额(?:为)?([\d,]+)'),
            '借款种类': re.compile(r'发放的[\d,]+元（人民币）([\u4e00-\u9fa5]+贷款)'),
        }

        for line in joined_lines:
            if '发放的贷记卡' in line:
                data = {}
                for field, pat in card_patterns.items():
                    m = pat.search(line)
                    data[field] = m.group(1) if m else None

                if '销户' in line:
                    status = '销户'
                elif '呆账' in line:
                    status = '呆账'
                elif '当前有逾期' in line:
                    status = '逾期'
                else:
                    status = '正常'

                institution = data.get('金融机构')
                amount = data.get('授信额度')
                balance = data.get('余额') or data.get('已用额度')

                accounts.append({
                    "account_type": "贷记卡",
                    "institution": institution,
                    "amount": amount,
                    "balance": balance,
                    "status": status,
                    "data_json": data,
                })

            elif '元（人民币）' in line and ('贷款' in line or '授信' in line):
                data = {}
                for field, pat in loan_patterns.items():
                    m = pat.search(line)
                    data[field] = m.group(1) if m else None

                if '销户' in line:
                    status = '销户'
                elif '呆账' in line:
                    status = '呆账'
                elif '当前有逾期' in line:
                    status = '逾期'
                else:
                    status = '正常'

                institution = data.get('金融机构')
                amount = data.get('借款金额')
                balance = data.get('余额')

                accounts.append({
                    "account_type": "贷款",
                    "institution": institution,
                    "amount": amount,
                    "balance": balance,
                    "status": status,
                    "data_json": data,
                })

        return accounts

    def _extract_query_summary(self) -> list:
        records = []
        query_marker = '查询记录'
        idx = self.text.find(query_marker)
        if idx < 0:
            return records

        query_section = self.text[idx:]

        header_marker = '编号 查询日期 查询机构 查询原因'
        header_idx = query_section.find(header_marker)
        if header_idx < 0:
            return records

        after_header = query_section[header_idx + len(header_marker):]

        # Clean page markers
        after_header = re.sub(r'第 \d+ 页，共 \d+ 页', '', after_header)

        # Join wrapped lines for query records
        raw_lines = after_header.splitlines()
        joined_lines = []
        for line in raw_lines:
            stripped = line.strip()
            if not stripped:
                continue
            if re.match(r'^\d+\s', stripped):
                joined_lines.append(stripped)
            else:
                if joined_lines:
                    joined_lines[-1] += stripped

        pattern = re.compile(
            r'(\d+)\s+(\d{4}年\d{2}月\d{2}日)\s+([\u4e00-\u9fa5\w（）、]+)\s+([\u4e00-\u9fa5]+)'
        )
        for line in joined_lines:
            m = pattern.search(line)
            if m:
                records.append({
                    "query_date": m.group(2),
                    "query_org": m.group(3),
                    "query_reason": m.group(4),
                })

        return records
