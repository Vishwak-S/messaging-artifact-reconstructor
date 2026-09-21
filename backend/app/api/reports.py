from typing import List
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.database.db import get_db
from app.models.models import Report
from app.schemas.schemas import ReportGenerateRequest, ReportResponse
from app.services.report_service import generate_report

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.post("/generate", response_model=ReportResponse, status_code=201)
def api_generate_report(req: ReportGenerateRequest, db: Session = Depends(get_db)):
    try:
        rpt = generate_report(db, req.case_id, req.format, req.include_raw_records)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return rpt


@router.get("", response_model=List[ReportResponse])
def list_reports(db: Session = Depends(get_db)):
    return db.query(Report).order_by(Report.generated_at.desc()).all()


@router.get("/{report_id}/download")
def download_report(report_id: str, db: Session = Depends(get_db)):
    rpt = db.query(Report).filter(Report.report_id == report_id).first()
    if not rpt or not rpt.file_path:
        raise HTTPException(status_code=404, detail="Report not found")
    from pathlib import Path
    path = Path(rpt.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report file missing")
    return FileResponse(
        str(path),
        filename=path.name,
        media_type="application/octet-stream",
    )
