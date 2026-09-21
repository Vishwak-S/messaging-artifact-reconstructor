from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database.db import get_db
from app.models.models import Message
from app.schemas.schemas import TimelineEntry

router = APIRouter(prefix="/timeline", tags=["Timeline"])


@router.get("", response_model=List[TimelineEntry])
def get_timeline(
    case_id: Optional[str] = Query(None),
    application: Optional[str] = Query(None),
    conv_id: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    q = db.query(Message)
    if case_id:
        q = q.filter(Message.case_id == case_id)
    if application:
        q = q.filter(Message.application == application)
    if conv_id:
        q = q.filter(Message.conv_id == conv_id)
    if from_date:
        from datetime import datetime
        try:
            q = q.filter(Message.timestamp >= datetime.fromisoformat(from_date))
        except ValueError:
            pass
    if to_date:
        from datetime import datetime
        try:
            q = q.filter(Message.timestamp <= datetime.fromisoformat(to_date))
        except ValueError:
            pass

    offset = (page - 1) * page_size
    msgs = (
        q.order_by(Message.timestamp.asc().nulls_last())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    return [
        TimelineEntry(
            timestamp=m.timestamp,
            timestamp_original=m.timestamp_original,
            application=m.application,
            sender=m.sender,
            message_type=m.message_type,
            message_text=m.message_text,
            conv_id=m.conv_id,
            message_id=m.message_id,
            evidence_status=m.evidence_status,
        )
        for m in msgs
    ]
