"""Case management service."""
import uuid
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.models import Case, AuditEvent
from app.schemas.schemas import CaseCreate


def _gen_case_id() -> str:
    year = datetime.utcnow().year
    uid = str(uuid.uuid4())[:8].upper()
    return f"CASE-{year}-{uid}"


def create_case(db: Session, data: CaseCreate) -> Case:
    case = Case(
        case_id=_gen_case_id(),
        name=data.name,
        description=data.description,
        investigator=data.investigator,
        status="open",
    )
    db.add(case)
    db.flush()
    _audit(db, case.case_id, None, "CASE_CREATED", f"Case '{data.name}' created.")
    db.commit()
    db.refresh(case)
    return case


def get_cases(db: Session):
    return db.query(Case).order_by(Case.created_at.desc()).all()


def get_case(db: Session, case_id: str):
    return db.query(Case).filter(Case.case_id == case_id).first()


def _audit(db: Session, case_id, evidence_id, action, description):
    event = AuditEvent(
        case_id=case_id,
        evidence_id=evidence_id,
        action=action,
        description=description,
    )
    db.add(event)
