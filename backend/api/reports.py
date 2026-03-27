import os
import shutil
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from backend.core.database import get_db
from backend.core.config import settings
from backend.api.auth import get_current_user
from backend.models.db import User, Report
from backend.services.report_service import ReportService

router = APIRouter()


@router.post("/upload")
def upload_report(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{file.filename}"
    file_path = os.path.join(settings.UPLOAD_DIR, filename)

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    service = ReportService(db=db)
    try:
        report_id = service.process_report(file_path=file_path, user_id=current_user.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"report_id": report_id, "message": "解析完成"}


@router.get("")
def list_reports(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    reports = (
        db.query(Report)
        .filter(Report.user_id == current_user.id)
        .order_by(Report.created_at.desc())
        .all()
    )
    return [
        {
            "id": r.id,
            "report_type": r.report_type,
            "subject_name": r.subject_name,
            "report_number": r.report_number,
            "report_date": r.report_date,
            "parse_status": r.parse_status,
            "is_valid": r.is_valid,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in reports
    ]


@router.get("/{report_id}")
def get_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = db.query(Report).filter(
        Report.id == report_id,
        Report.user_id == current_user.id,
    ).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    detail = None
    if report.enterprise_report:
        detail = report.enterprise_report.data_json
    elif report.personal_report:
        detail = report.personal_report.data_json

    return {
        "id": report.id,
        "report_type": report.report_type,
        "subject_name": report.subject_name,
        "report_number": report.report_number,
        "report_date": report.report_date,
        "is_valid": report.is_valid,
        "parse_status": report.parse_status,
        "detail": detail,
        "credit_accounts": [
            {"account_type": a.account_type, "institution": a.institution,
             "balance": a.balance, "status": a.status}
            for a in report.credit_accounts
        ],
        "query_records": [
            {"query_date": q.query_date, "query_org": q.query_org}
            for q in report.query_records
        ],
    }


@router.delete("/{report_id}", status_code=204)
def delete_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    report = db.query(Report).filter(
        Report.id == report_id,
        Report.user_id == current_user.id,
    ).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    db.delete(report)
    db.commit()
