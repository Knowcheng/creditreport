from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(16), default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    reports: Mapped[list["Report"]] = relationship("Report", back_populates="user")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    report_type: Mapped[str] = mapped_column(String(32))
    file_path: Mapped[str] = mapped_column(String(512))
    file_type: Mapped[str] = mapped_column(String(16))
    report_number: Mapped[Optional[str]] = mapped_column(String(64))
    subject_name: Mapped[Optional[str]] = mapped_column(String(128))
    report_date: Mapped[Optional[str]] = mapped_column(String(32))
    is_valid: Mapped[Optional[bool]] = mapped_column(Boolean)
    parse_status: Mapped[str] = mapped_column(String(16), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="reports")
    enterprise_report: Mapped[Optional["EnterpriseReport"]] = relationship(
        "EnterpriseReport", back_populates="report", uselist=False
    )
    personal_report: Mapped[Optional["PersonalReport"]] = relationship(
        "PersonalReport", back_populates="report", uselist=False
    )
    credit_accounts: Mapped[list["CreditAccount"]] = relationship("CreditAccount", back_populates="report")
    query_records: Mapped[list["QueryRecord"]] = relationship("QueryRecord", back_populates="report")


class EnterpriseReport(Base):
    __tablename__ = "enterprise_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(Integer, ForeignKey("reports.id"), unique=True, nullable=False)
    credit_code: Mapped[Optional[str]] = mapped_column(String(32))
    company_name: Mapped[Optional[str]] = mapped_column(String(256))
    credit_num: Mapped[Optional[str]] = mapped_column(String(64))
    registered_capital: Mapped[Optional[str]] = mapped_column(String(64))
    query_org: Mapped[Optional[str]] = mapped_column(String(256))
    data_json: Mapped[Optional[dict]] = mapped_column(JSON)

    report: Mapped["Report"] = relationship("Report", back_populates="enterprise_report")


class PersonalReport(Base):
    __tablename__ = "personal_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(Integer, ForeignKey("reports.id"), unique=True, nullable=False)
    id_number: Mapped[Optional[str]] = mapped_column(String(32))
    name: Mapped[Optional[str]] = mapped_column(String(64))
    age: Mapped[Optional[int]] = mapped_column(Integer)
    marital_status: Mapped[Optional[str]] = mapped_column(String(16))
    data_json: Mapped[Optional[dict]] = mapped_column(JSON)

    report: Mapped["Report"] = relationship("Report", back_populates="personal_report")


class CreditAccount(Base):
    __tablename__ = "credit_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(Integer, ForeignKey("reports.id"), nullable=False)
    account_type: Mapped[Optional[str]] = mapped_column(String(64))
    institution: Mapped[Optional[str]] = mapped_column(String(256))
    amount: Mapped[Optional[float]] = mapped_column(Float)
    balance: Mapped[Optional[float]] = mapped_column(Float)
    status: Mapped[Optional[str]] = mapped_column(String(16))
    data_json: Mapped[Optional[dict]] = mapped_column(JSON)

    report: Mapped["Report"] = relationship("Report", back_populates="credit_accounts")


class QueryRecord(Base):
    __tablename__ = "query_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(Integer, ForeignKey("reports.id"), nullable=False)
    query_date: Mapped[Optional[str]] = mapped_column(String(32))
    query_org: Mapped[Optional[str]] = mapped_column(String(256))
    query_reason: Mapped[Optional[str]] = mapped_column(String(128))

    report: Mapped["Report"] = relationship("Report", back_populates="query_records")
