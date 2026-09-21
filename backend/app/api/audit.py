from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database.db import get_db
from app.models.models import AuditEvent, AnalysisRun
from app.schemas.schemas import AuditEventResponse, AnalysisRunResponse

router = APIRouter(tags=["Audit"])


@router.get("/audit-log", response_model=List[AuditEventResponse])
def get_audit_log(
    case_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(AuditEvent)
    if case_id:
        q = q.filter(AuditEvent.case_id == case_id)
    return q.order_by(AuditEvent.timestamp.desc()).limit(500).all()


@router.get("/analysis-runs", response_model=List[AnalysisRunResponse])
def get_analysis_runs(
    case_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(AnalysisRun)
    if case_id:
        q = q.filter(AnalysisRun.case_id == case_id)
    return q.order_by(AnalysisRun.start_time.desc()).all()
