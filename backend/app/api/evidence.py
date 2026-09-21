from datetime import datetime
import hashlib
from pathlib import Path
from typing import List

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.models.models import AuditEvent, Evidence, ForensicDatabase
from app.schemas.schemas import EvidenceResponse, HashVerifyResponse
from app.services.analysis_service import run_analysis
from app.services.evidence_service import ingest_evidence, verify_hash, auto_acquire_local_databases
from app.forensic.whatsapp_crypt14 import Crypt14Error, decrypt_crypt14

router = APIRouter(tags=["Evidence"])


@router.post("/cases/{case_id}/evidence", response_model=EvidenceResponse, status_code=201)
async def upload_evidence(
    case_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    filename = file.filename or "uploaded.db"
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        digest = hashlib.sha256(content).hexdigest()
        existing = db.query(Evidence).filter(
            Evidence.case_id == case_id,
            Evidence.sha256_hash == digest,
        ).first()
        if existing:
            return existing
        ev = ingest_evidence(db, case_id, filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    # Kick off analysis in background
    background_tasks.add_task(_bg_analyze, ev.evidence_id)
    return ev


@router.post("/cases/{case_id}/auto-acquire")
def api_auto_acquire(
    case_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """
    Scans REAL local PC messaging app locations for databases and ingests them.
    Only scans genuine Windows app data paths (Signal, Telegram, WhatsApp).
    Returns an empty list if no messaging apps are installed on this PC.
    """
    from app.services.evidence_service import _get_real_scan_targets
    
    # Report which real paths were scanned (for transparency)
    all_targets = _get_real_scan_targets()
    scanned_paths = [str(p) for p, _ in all_targets]
    
    ingested_evidence = auto_acquire_local_databases(db, case_id)
    
    # Start analysis for all found files
    for ev in ingested_evidence:
        background_tasks.add_task(_bg_analyze, ev.evidence_id)
    
    if ingested_evidence:
        message = f"Found and acquired {len(ingested_evidence)} real messaging database(s) from this PC."
    else:
        message = (
            "No supported message SQLite database was found on this PC. "
            "WhatsApp Desktop may store current data in IndexedDB or a Windows-protected "
            "session store; configuration/cache files are intentionally skipped. "
            "Close WhatsApp/Telegram/Signal completely and scan again after it has synced."
        )
    
    return {
        "message": message,
        "evidence_ids": [ev.evidence_id for ev in ingested_evidence],
        "count": len(ingested_evidence),
        "scanned_paths": scanned_paths,
        "found": len(ingested_evidence) > 0,
    }

def _bg_analyze(evidence_id: str):
    """Background analysis task — runs after response is sent."""
    from app.database.db import SessionLocal
    db = SessionLocal()
    try:
        ev = db.query(Evidence).filter(Evidence.evidence_id == evidence_id).first()
        if ev:
            run_analysis(db, ev)
    except Exception as e:
        pass  # Errors are recorded inside run_analysis
    finally:
        db.close()


@router.get("/evidence/{evidence_id}", response_model=EvidenceResponse)
def get_evidence(evidence_id: str, db: Session = Depends(get_db)):
    ev = db.query(Evidence).filter(Evidence.evidence_id == evidence_id).first()
    if not ev:
        raise HTTPException(status_code=404, detail="Evidence not found")
    return ev


@router.post("/evidence/{evidence_id}/analyze")
def analyze_evidence(evidence_id: str, background_tasks: BackgroundTasks,
                     db: Session = Depends(get_db)):
    ev = db.query(Evidence).filter(Evidence.evidence_id == evidence_id).first()
    if not ev:
        raise HTTPException(status_code=404, detail="Evidence not found")
    background_tasks.add_task(_bg_analyze, evidence_id)
    return {"message": "Analysis started", "evidence_id": evidence_id}


@router.post("/evidence/{evidence_id}/decrypt-crypt14", response_model=EvidenceResponse, status_code=201)
async def decrypt_whatsapp_crypt14(
    evidence_id: str,
    background_tasks: BackgroundTasks,
    key_file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Create an auditable derived SQLite evidence item using a supplied key.

    The supplied key is held only for this request and is deliberately neither
    written to disk nor included in logs/audit descriptions.
    """
    ev = db.query(Evidence).filter(Evidence.evidence_id == evidence_id).first()
    if not ev:
        raise HTTPException(status_code=404, detail="Evidence not found")
    if not ev.original_filename.lower().endswith(".crypt14"):
        raise HTTPException(status_code=400, detail="This action is available only for .crypt14 evidence files.")

    key_bytes = await key_file.read()
    if not key_bytes:
        raise HTTPException(status_code=400, detail="The supplied key file is empty.")
    try:
        backup = Path(ev.stored_path).read_bytes()
        decrypted = decrypt_crypt14(backup, key_bytes)
    except Crypt14Error as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    derived_name = f"{Path(ev.original_filename).stem}.decrypted.db"
    derived = ingest_evidence(db, ev.case_id, derived_name, decrypted.plaintext)
    db.add(AuditEvent(
        case_id=ev.case_id,
        evidence_id=derived.evidence_id,
        action="CRYPT14_DECRYPTED",
        description=(f"Derived from {ev.evidence_id} after authenticated .crypt14 decryption "
                     f"({decrypted.layout}); supplied key was not retained."),
    ))
    db.commit()
    db.refresh(derived)
    background_tasks.add_task(_bg_analyze, derived.evidence_id)
    return derived


@router.get("/evidence/{evidence_id}/verify-hash", response_model=HashVerifyResponse)
def verify_evidence_hash(evidence_id: str, db: Session = Depends(get_db)):
    result = verify_hash(db, evidence_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return HashVerifyResponse(**result)


@router.get("/evidence/{evidence_id}/status")
def evidence_status(evidence_id: str, db: Session = Depends(get_db)):
    from app.models.models import AnalysisRun
    ev = db.query(Evidence).filter(Evidence.evidence_id == evidence_id).first()
    if not ev:
        raise HTTPException(status_code=404, detail="Evidence not found")
    latest_run = (
        db.query(AnalysisRun)
        .filter(AnalysisRun.evidence_id == evidence_id)
        .order_by(AnalysisRun.start_time.desc())
        .first()
    )
    return {
        "evidence_id": evidence_id,
        "status": ev.status,
        "app_detected": ev.app_detected,
        "sha256": ev.sha256_hash,
        "latest_run": {
            "run_id": latest_run.run_id if latest_run else None,
            "status": latest_run.status if latest_run else None,
            "pipeline_log": latest_run.pipeline_log if latest_run else [],
            "messages_extracted": latest_run.messages_extracted if latest_run else 0,
        } if latest_run else None,
    }
