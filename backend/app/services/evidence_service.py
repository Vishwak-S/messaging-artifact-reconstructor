"""
Evidence ingestion service.

Handles file upload, SHA-256 hashing, preservation,
companion file detection, and app detection.
"""
import shutil
import uuid
import os
import glob
import hashlib
import stat
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.forensic.detector import detect_application
from app.forensic.hasher import sha256_file
from app.forensic.inspector import inspect_database
from app.models.models import AuditEvent, Evidence, EvidenceFile, ForensicDatabase

SQLITE_MAGIC = b"SQLite format 3\x00"
SQLITE_EXTENSIONS = {".db", ".sqlite", ".sqlite3", ".db3"}
CRYPT14_EXTENSION = ".crypt14"
TELEGRAM_EXPORT_EXTENSION = ".json"


def _gen_evidence_id() -> str:
    return f"EV-{str(uuid.uuid4())[:12].upper()}"


def _gen_db_id() -> str:
    return f"DB-{str(uuid.uuid4())[:12].upper()}"


def _store_path(evidence_id: str, filename: str) -> Path:
    """Return a safe storage path inside the evidence store."""
    base = Path(settings.EVIDENCE_STORE) / evidence_id
    base.mkdir(parents=True, exist_ok=True)
    return base / filename


def _audit(db: Session, case_id, evidence_id, action, description):
    db.add(AuditEvent(
        case_id=case_id, evidence_id=evidence_id,
        action=action, description=description,
    ))


def validate_evidence_upload(filename: str, file_bytes: bytes) -> None:
    """Reject arbitrary uploads before they enter the evidence store.

    Supported inputs are a structurally valid SQLite database or a plausibly
    sized WhatsApp .crypt14 container.  The server performs this check as the
    browser's file-type chooser can be bypassed.
    """
    suffix = Path(filename).suffix.lower()
    if suffix == CRYPT14_EXTENSION:
        if len(file_bytes) < 128:
            raise ValueError("The .crypt14 backup is too small to be valid.")
        return
    if suffix == TELEGRAM_EXPORT_EXTENSION:
        try:
            data = json.loads(file_bytes.decode("utf-8"))
            if isinstance(data, dict) and isinstance(data.get("chats", {}).get("list"), list):
                return
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            pass
        raise ValueError("This JSON file is not an official Telegram Desktop export.")
    if suffix not in SQLITE_EXTENSIONS:
        raise ValueError("Upload a SQLite database (.db, .sqlite, .sqlite3, .db3), WhatsApp .crypt14 backup, or Telegram Desktop export JSON.")
    if not file_bytes.startswith(SQLITE_MAGIC):
        raise ValueError("This .db file is not a valid SQLite database. Random or application-config files are not accepted.")


def ingest_evidence(
    db: Session,
    case_id: str,
    original_filename: str,
    file_bytes: bytes,
) -> Evidence:
    """
    Ingest a single evidence file.

    1. Generate Evidence ID.
    2. Preserve original file (never modify source).
    3. Calculate SHA-256.
    4. Detect application.
    5. Record metadata.
    6. Audit.
    """
    validate_evidence_upload(original_filename, file_bytes)
    digest = hashlib.sha256(file_bytes).hexdigest()

    existing = db.query(Evidence).filter(
        Evidence.case_id == case_id,
        Evidence.sha256_hash == digest,
    ).first()
    if existing:
        return existing

    evidence_id = _gen_evidence_id()
    dest_path = _store_path(evidence_id, original_filename)

    # Write file to evidence store (read-only preservation)
    with open(dest_path, "wb") as f:
        f.write(file_bytes)
    dest_path.chmod(0o444)  # mark read-only

    # Hash
    sha256 = sha256_file(dest_path)

    # Detect
    det = detect_application(str(dest_path))

    ev = Evidence(
        evidence_id=evidence_id,
        case_id=case_id,
        original_filename=original_filename,
        stored_path=str(dest_path),
        original_size_bytes=len(file_bytes),
        sha256_hash=sha256,
        import_timestamp=datetime.utcnow(),
        status="imported",
        app_detected=det.application,
        detection_confidence=det.confidence,
        detection_reasons=det.reasons,
        is_encrypted=det.is_encrypted,
    )
    db.add(ev)
    db.flush()

    _audit(db, case_id, evidence_id, "EVIDENCE_IMPORTED",
           f"Evidence '{original_filename}' imported. SHA-256: {sha256}")
    _audit(db, case_id, evidence_id, "HASH_CALCULATED",
           f"SHA-256: {sha256}")

    if det.application != "Unknown":
        _audit(db, case_id, evidence_id, "APPLICATION_IDENTIFIED",
               f"Detected: {det.application} (Confidence: {det.confidence})")

    db.commit()
    db.refresh(ev)
    return ev


def verify_hash(db: Session, evidence_id: str) -> dict:
    """Re-compute SHA-256 and compare against stored hash."""
    ev = db.query(Evidence).filter(Evidence.evidence_id == evidence_id).first()
    if not ev:
        return {"error": "Evidence not found"}

    current = sha256_file(ev.stored_path)
    match = current.lower() == (ev.sha256_hash or "").lower()

    _audit(db, ev.case_id, evidence_id, "HASH_VERIFIED",
           f"Hash verification {'PASSED' if match else 'FAILED'}. Current: {current}")
    db.commit()

    return {
        "evidence_id": evidence_id,
        "original_hash": ev.sha256_hash,
        "current_hash": current,
        "match": match,
        "verified_at": datetime.utcnow().isoformat(),
    }


def register_forensic_database(db: Session, evidence: Evidence, db_path: str) -> ForensicDatabase:
    """Inspect and register a forensic database record."""
    insp = inspect_database(db_path)
    det = detect_application(db_path)
    db_id = _gen_db_id()

    schema_info = {
        t.name: [c.name for c in t.columns]
        for t in insp.tables
    }

    fdb = ForensicDatabase(
        db_id=db_id,
        evidence_id=evidence.evidence_id,
        case_id=evidence.case_id,
        db_filename=Path(db_path).name,
        app_detected=det.application,
        detection_confidence=det.confidence,
        detection_reasons=det.reasons,
        table_count=len(insp.tables),
        total_records=insp.total_records,
        sqlite_valid=insp.is_valid_sqlite,
        wal_detected=insp.wal_detected,
        shm_detected=insp.shm_detected,
        journal_detected=insp.journal_detected,
        page_size=insp.page_size,
        schema_info=schema_info,
        analyzed_at=datetime.utcnow(),
    )
    db.add(fdb)
    db.flush()
    return fdb


def _get_real_scan_targets() -> list[tuple[Path, str]]:
    """
    Returns a list of (path, description) tuples for every known real messaging
    database location on this Windows machine.

    IMPORTANT: This function ONLY returns real app paths. No sample, fake,
    synthetic, or demo data is ever included here.
    """
    appdata      = os.environ.get("APPDATA", "")
    localappdata = os.environ.get("LOCALAPPDATA", "")
    userprofile  = os.environ.get("USERPROFILE", str(Path.home()))

    targets: list[tuple[Path, str]] = []

    if not appdata or not localappdata:
        return targets

    # ── Signal Desktop ──────────────────────────────────────────────────────
    # Signal Desktop (Windows) stores messages in:
    #   %APPDATA%\Signal\sql\db.sqlite
    signal_path = Path(appdata) / "Signal" / "sql" / "db.sqlite"
    targets.append((signal_path, "Signal Desktop database"))

    # ── Telegram Desktop ────────────────────────────────────────────────────
    # Only readable SQLite (for example cache4.db). Encrypted tdata blobs are
    # not treated as message evidence and are never carved into fake chat text.
    for base in [appdata, localappdata]:
        tg_base = Path(base) / "Telegram Desktop" / "tdata"
        if not tg_base.exists():
            continue
        for p in tg_base.rglob("*"):
            if not p.is_file():
                continue
            if any(x in p.parts for x in ["emoji", "user_data", "dumps", "tdummy"]):
                continue
            if p.suffix.lower() in {".json", ".txt", ".log", ".mp4", ".jpg", ".png", ".webp"}:
                continue
            try:
                if p.stat().st_size < 1024:
                    continue
                with open(p, "rb") as handle:
                    magic = handle.read(16)
                if magic == SQLITE_MAGIC:
                    targets.append((p, f"Telegram Desktop SQLite ({p.name})"))
            except OSError:
                pass

    # ── WhatsApp Desktop (UWP — Microsoft Store version) ────────────────────
    # Package name contains "5319275A.WhatsAppDesktop"
    # Scan ALL .db files inside the LocalState directory tree (sessions subfolders)
    wa_base_glob = str(Path(localappdata) / "Packages" / "5319275A.WhatsAppDesktop_*" / "LocalState")
    for wa_base in glob.glob(wa_base_glob):
        # Recursively find all .db and .sqlite files in the WhatsApp LocalState tree
        for db_file in glob.glob(str(Path(wa_base) / "**" / "*.db"), recursive=True):
            targets.append((Path(db_file), "WhatsApp Desktop (UWP) session database"))
        for db_file in glob.glob(str(Path(wa_base) / "*.db")):
            targets.append((Path(db_file), "WhatsApp Desktop (UWP) root database"))

    # ── WhatsApp Desktop (Win32 / standalone installer) ──────────────────────
    # Newer WhatsApp Desktop (Win32) stores databases at:
    #   %APPDATA%\WhatsApp\IndexedDB\
    for db_file in glob.glob(str(Path(appdata) / "WhatsApp" / "IndexedDB" / "*.leveldb")):
        targets.append((Path(db_file), "WhatsApp Desktop (Win32) IndexedDB"))
    for db_file in glob.glob(str(Path(appdata) / "WhatsApp" / "*.db")):
        targets.append((Path(db_file), "WhatsApp Desktop (Win32) database"))
    for db_file in glob.glob(str(Path(appdata) / "WhatsApp" / "databases" / "*.db")):
        targets.append((Path(db_file), "WhatsApp Desktop (Win32) databases"))

    # ── WhatsApp Web / Electron app (Chrome-based caches) ───────────────────
    # Some WhatsApp Desktop versions use Chromium local storage
    for db_file in glob.glob(
        str(Path(localappdata) / "WhatsApp" / "**" / "*.db"), recursive=True
    ):
        targets.append((Path(db_file), "WhatsApp (LocalAppData) database"))

    # ── Viber ────────────────────────────────────────────────────────────────
    viber_path = Path(appdata) / "ViberPC" / "*.db"
    for db_file in glob.glob(str(viber_path)):
        targets.append((Path(db_file), "Viber database"))

    return targets


def auto_acquire_local_databases(db: Session, case_id: str) -> list[Evidence]:
    """
    Scans REAL local PC locations for messaging application databases and ingests them.

    This function scans ONLY genuine Windows app data paths:
      - Signal Desktop (%APPDATA%\\Signal\\sql\\db.sqlite)
      - Telegram Desktop (%APPDATA%\\Telegram Desktop\\tdata\\cache4.db)
      - WhatsApp Desktop UWP (Microsoft Store)
      - WhatsApp Desktop Win32 (standalone installer)
      - Viber

    NO fake, synthetic, hardcoded, or sample data is ever included.
    If no messaging apps are installed or their databases are not accessible,
    the function returns an empty list — the caller should inform the user.
    """
    targets = _get_real_scan_targets()

    ingested: list[Evidence] = []
    seen_paths: set[str] = set()  # avoid ingesting the same file twice

    for target_path, description in targets:
        # Skip non-existent or duplicate files
        if not target_path.exists() or not target_path.is_file():
            continue

        resolved = str(target_path.resolve())
        if resolved in seen_paths:
            continue
        seen_paths.add(resolved)

        # Skip very small files — real databases are always at least a few KB
        if target_path.stat().st_size < 1024:
            continue

        # Only ingest a readable database whose schema identifies a supported
        # messaging app.  Desktop installations contain many encrypted/config
        # databases (contacts, settings, media caches) that are not messages.
        det = detect_application(str(target_path))
        if not det.is_sqlite or det.application == "Unknown":
            _audit(db, case_id, None, "ACQUISITION_SKIPPED",
                   f"Skipped non-message or unreadable file: {resolved} ({description})")
            db.commit()
            continue

        # Build a unique filename that encodes the app it came from
        filename = target_path.name
        parent_label = target_path.parent.name
        unique_filename = f"{parent_label}_{filename}" if filename in {p.name for p, _ in targets if p != target_path} else filename

        try:
            with open(target_path, "rb") as f:
                content = f.read()
            digest = sha256_file(target_path)
            if db.query(Evidence).filter(
                Evidence.case_id == case_id,
                Evidence.sha256_hash == digest,
            ).first():
                _audit(db, case_id, None, "ACQUISITION_SKIPPED",
                       f"Skipped duplicate evidence: {resolved}")
                db.commit()
                continue
            ev = ingest_evidence(db, case_id, unique_filename, content)
            # Store the original source path in audit
            _audit(db, case_id, ev.evidence_id, "SOURCE_PATH",
                   f"Acquired from real PC path: {resolved} ({description})")
            db.commit()
            ingested.append(ev)
        except PermissionError:
            # File is locked by the app — skip silently, will be noted in audit
            _audit(db, case_id, None, "ACQUISITION_SKIPPED",
                   f"Skipped (permission denied): {resolved}")
            db.commit()
        except Exception as e:
            _audit(db, case_id, None, "ACQUISITION_ERROR",
                   f"Error reading {resolved}: {e}")
            db.commit()

    return ingested


def clear_analysis_data_keep_cases() -> None:
    """Clear prior evidence/results at startup while retaining only cases."""
    from app.database.db import SessionLocal
    from app.models.models import AnalysisRun, Conversation, Message, Report

    db = SessionLocal()
    try:
        # Explicit order avoids relying on optional SQLite foreign-key settings.
        db.query(Message).delete(synchronize_session=False)
        db.query(Conversation).delete(synchronize_session=False)
        db.query(ForensicDatabase).delete(synchronize_session=False)
        db.query(AnalysisRun).delete(synchronize_session=False)
        db.query(EvidenceFile).delete(synchronize_session=False)
        db.query(AuditEvent).filter(AuditEvent.evidence_id.isnot(None)).delete(synchronize_session=False)
        db.query(Evidence).delete(synchronize_session=False)
        db.query(Report).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()

    def remove_readonly(func, path, _exc_info):
        """Retry cleanup after removing the read-only bit set on evidence."""
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except OSError:
            # A genuinely locked file is harmless after its metadata has been
            # cleared. Do not stop the whole application from launching.
            pass

    # The application owns these directories. Clear their contents, never the
    # case metadata database itself. Evidence files are read-only by design.
    for folder in (Path(settings.EVIDENCE_STORE), Path(settings.REPORTS_DIR)):
        if folder.exists():
            for child in folder.iterdir():
                if child.is_dir():
                    shutil.rmtree(child, onerror=remove_readonly)
                elif child.is_file():
                    try:
                        child.unlink()
                    except PermissionError:
                        remove_readonly(os.unlink, str(child), None)
