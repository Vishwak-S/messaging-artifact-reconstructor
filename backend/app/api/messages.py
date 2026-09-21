from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.db import get_db
from app.models.models import Message
from app.schemas.schemas import MessageResponse

router = APIRouter(prefix="/messages", tags=["Messages"])


@router.get("/{message_id}/evidence", response_model=MessageResponse)
def get_message_evidence(message_id: str, db: Session = Depends(get_db)):
    msg = db.query(Message).filter(Message.message_id == message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    return msg
