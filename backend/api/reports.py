import os
import pathlib
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from backend.core.database import get_db
from backend.core.config import settings
from backend.api.auth import get_current_user
from backend.models.db import User, Report
from backend.services.report_service import ReportService

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


@router.post("/upload")
async def upload_report(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Check allowed extensions
    file_ext = pathlib.Path(file.filename).suffix.lower()
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="不支持的文件格式，仅支持 PDF、JPG、PNG")

    # Read file bytes and check size
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="文件过大，最大支持 50MB")

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Sanitize filename to prevent path traversal
    safe_name = os.path.basename(file.filename)
    if not safe_name:
        safe_name = "upload"
    filename = f"{timestamp}_{safe_name}"
    file_path = os.path.join(settings.UPLOAD_DIR, filename)
    # Verify path stays within upload dir
    upload_dir_abs = os.path.realpath(settings.UPLOAD_DIR)
    file_path_abs = os.path.realpath(file_path)
    if not file_path_abs.startswith(upload_dir_abs + os.sep) and file_path_abs != upload_dir_abs:
        raise HTTPException(status_code=400, detail="无效的文件名")

    with open(file_path, "wb") as f:
        f.write(file_bytes)

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
    file_path = report.file_path
    db.delete(report)
    db.commit()
    # Clean up uploaded file
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass  # Don't fail the delete if file cleanup fails
