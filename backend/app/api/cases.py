from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.db import get_db
from app.schemas.schemas import CaseCreate, CaseResponse
from app.services.case_service import create_case, get_case, get_cases
from typing import List

router = APIRouter(prefix="/cases", tags=["Cases"])


@router.post("", response_model=CaseResponse, status_code=201)
def api_create_case(data: CaseCreate, db: Session = Depends(get_db)):
    return create_case(db, data)


@router.get("", response_model=List[CaseResponse])
def api_list_cases(db: Session = Depends(get_db)):
    return get_cases(db)


@router.get("/{case_id}", response_model=CaseResponse)
def api_get_case(case_id: str, db: Session = Depends(get_db)):
    c = get_case(db, case_id)
    if not c:
        raise HTTPException(status_code=404, detail="Case not found")
    return c
