from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database.db import get_db
from app.models.models import ForensicDatabase
from app.schemas.schemas import DatabaseResponse, TableRowsResponse
from app.forensic.inspector import get_table_rows

router = APIRouter(prefix="/databases", tags=["Databases"])


@router.get("", response_model=List[DatabaseResponse])
def list_databases(
    case_id: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    q = db.query(ForensicDatabase)
    if case_id:
        q = q.filter(ForensicDatabase.case_id == case_id)
    return q.all()


@router.get("/{db_id}", response_model=DatabaseResponse)
def get_database(db_id: str, db: Session = Depends(get_db)):
    fdb = db.query(ForensicDatabase).filter(ForensicDatabase.db_id == db_id).first()
    if not fdb:
        raise HTTPException(status_code=404, detail="Database not found")
    return fdb


@router.get("/{db_id}/tables/{table}/rows", response_model=TableRowsResponse)
def get_table_data(
    db_id: str,
    table: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    fdb = db.query(ForensicDatabase).filter(ForensicDatabase.db_id == db_id).first()
    if not fdb:
        raise HTTPException(status_code=404, detail="Database not found")

    # Validate table name against known schema
    schema = fdb.schema_info or {}
    if table not in schema:
        raise HTTPException(status_code=404, detail=f"Table '{table}' not found in schema")

    from app.models.models import Evidence
    ev = db.query(Evidence).filter(Evidence.evidence_id == fdb.evidence_id).first()
    if not ev:
        raise HTTPException(status_code=404, detail="Evidence file not found")

    result = get_table_rows(ev.stored_path, table, page, page_size)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])

    return TableRowsResponse(
        database=fdb.db_filename,
        table=table,
        total_rows=result["total_rows"],
        page=page,
        page_size=page_size,
        columns=result["columns"],
        rows=result["rows"],
    )
