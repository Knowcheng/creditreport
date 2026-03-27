from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ReportResult:
    report_type: str
    report_number: Optional[str]
    subject_name: Optional[str]
    report_date: Optional[str]
    raw_data: dict = field(default_factory=dict)
    credit_accounts: list = field(default_factory=list)
    query_records: list = field(default_factory=list)


class BaseParser(ABC):
    def __init__(self, text: str, tables: list, file_path: str):
        self.text = text
        self.tables = tables
        self.file_path = file_path

    @abstractmethod
    def parse(self) -> ReportResult:
        raise NotImplementedError
