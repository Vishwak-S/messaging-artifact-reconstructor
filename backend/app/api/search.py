from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.database.db import get_db
from app.models.models import Message
from app.schemas.schemas import MessageResponse, SearchResult

router = APIRouter(prefix="/search", tags=["Search"])


@router.get("", response_model=SearchResult)
def search(
    q: Optional[str] = Query(None, description="Search term"),
    application: Optional[str] = Query(None),
    case_id: Optional[str] = Query(None),
    conv_id: Optional[str] = Query(None),
    message_type: Optional[str] = Query(None),
    evidence_status: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(Message)

    if case_id:
        query = query.filter(Message.case_id == case_id)
    if application:
        query = query.filter(Message.application == application)
    if conv_id:
        query = query.filter(Message.conv_id == conv_id)
    if message_type:
        query = query.filter(Message.message_type == message_type)
    if evidence_status:
        query = query.filter(Message.evidence_status == evidence_status)

    if q:
        term = f"%{q}%"
        query = query.filter(or_(
            Message.message_text.ilike(term),
            Message.sender.ilike(term),
            Message.recipient.ilike(term),
            Message.message_id.ilike(term),
            Message.attachment_name.ilike(term),
            Message.source_database.ilike(term),
        ))

    if from_date:
        from datetime import datetime
        try:
            query = query.filter(Message.timestamp >= datetime.fromisoformat(from_date))
        except ValueError:
            pass
    if to_date:
        from datetime import datetime
        try:
            query = query.filter(Message.timestamp <= datetime.fromisoformat(to_date))
        except ValueError:
            pass

    total = query.count()
    offset = (page - 1) * page_size
    results = (
        query.order_by(Message.timestamp.asc().nulls_last())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    return SearchResult(total=total, page=page, page_size=page_size, results=results)
