from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database.db import get_db
from app.models.models import Conversation, Message
from app.schemas.schemas import ConversationResponse, MessageResponse

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.get("", response_model=List[ConversationResponse])
def list_conversations(
    case_id: Optional[str] = Query(None),
    application: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    q = db.query(Conversation)
    if case_id:
        q = q.filter(Conversation.case_id == case_id)
    if application:
        q = q.filter(Conversation.application == application)
    return q.order_by(Conversation.last_message_ts.desc().nulls_last()).all()


@router.get("/{conv_id}", response_model=ConversationResponse)
def get_conversation(conv_id: str, db: Session = Depends(get_db)):
    c = db.query(Conversation).filter(Conversation.conv_id == conv_id).first()
    if not c:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return c


@router.get("/{conv_id}/messages", response_model=List[MessageResponse])
def get_conversation_messages(
    conv_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    offset = (page - 1) * page_size
    msgs = (
        db.query(Message)
        .filter(Message.conv_id == conv_id)
        .order_by(Message.timestamp.asc().nulls_last())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    return msgs
