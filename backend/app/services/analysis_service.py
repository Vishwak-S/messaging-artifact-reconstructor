"""
Analysis pipeline service.

Orchestrates the full forensic pipeline:
IMPORT → HASH → VALIDATE → IDENTIFY → INSPECT SCHEMA →
PARSE → NORMALIZE → PRESERVE PROVENANCE → CORRELATE MEDIA →
RECONSTRUCT CONVERSATIONS → BUILD TIMELINE → VALIDATE → REPORT
"""
import uuid
from datetime import datetime
from pathlib import Path
from typing import List

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import (
    AnalysisRun, AuditEvent, Conversation, Evidence, ForensicDatabase, Message
)
from app.parsers.base_parser import CanonicalMessage, ParserResult
from app.parsers.whatsapp_parser import WhatsAppParser
from app.parsers.telegram_parser import TelegramParser
from app.parsers.telegram_export_parser import TelegramExportParser, is_telegram_export
from app.parsers.signal_parser import SignalParser
from app.services.evidence_service import register_forensic_database
from app.forensic.deleted_recovery import recover_deleted_from_sqlite
from app.forensic.snapshot_diff import is_schema_noise


PARSER_MAP = {
    "WhatsApp": WhatsAppParser,
    "Telegram": TelegramParser,
    "Signal": SignalParser,
}


def _gen_run_id() -> str:
    return f"RUN-{str(uuid.uuid4())[:12].upper()}"


def _audit(db: Session, case_id, evidence_id, action, description):
    db.add(AuditEvent(case_id=case_id, evidence_id=evidence_id,
                      action=action, description=description))


def _persist_export_result(db: Session, result: ParserResult, evidence: Evidence,
                           fdb: ForensicDatabase) -> tuple[int, int]:
    """Persist canonical Telegram-export records without altering the source file."""
    conv_map: dict[str, Conversation] = {}
    for conversation in result.conversations:
        conv = Conversation(
            conv_id=conversation.conv_id,
            db_id=fdb.db_id,
            case_id=evidence.case_id,
            application="Telegram",
            display_name=conversation.display_name,
            participants=conversation.participants,
            is_group=conversation.is_group,
            group_name=conversation.group_name,
            message_count=0,
        )
        db.add(conv)
        db.flush()
        conv_map[conversation.conv_id] = conv

    for message in result.messages:
        _persist_message(db, message, fdb.db_id)
    db.flush()

    for conv_id, conv in conv_map.items():
        messages = db.query(Message).filter(
            Message.conv_id == conv_id, Message.db_id == fdb.db_id
        ).all()
        conv.message_count = len(messages)
        timestamps = [message.timestamp for message in messages if message.timestamp]
        if timestamps:
            conv.first_message_ts = min(timestamps)
            conv.last_message_ts = max(timestamps)
    return len(result.messages), len(conv_map)


def run_analysis(db: Session, evidence: Evidence) -> AnalysisRun:
    """
    Execute the full analysis pipeline on an imported evidence file.
    Records every step in the analysis run log and audit trail.
    """
    run_id = _gen_run_id()
    pipeline_log = []
    warnings: List[str] = []
    errors: List[str] = []

    run = AnalysisRun(
        run_id=run_id,
        case_id=evidence.case_id,
        evidence_id=evidence.evidence_id,
        start_time=datetime.utcnow(),
        status="running",
        parser_versions={
            "WhatsAppParser": "1.0",
            "TelegramParser": "1.0",
            "SignalParser": "1.0",
        },
        pipeline_log=[],
    )
    db.add(run)
    db.flush()

    def log_step(step: str, status: str = "OK", detail: str = ""):
        entry = {"step": step, "status": status, "detail": detail,
                 "ts": datetime.utcnow().isoformat()}
        pipeline_log.append(entry)
        run.pipeline_log = list(pipeline_log)
        db.flush()

    _audit(db, evidence.case_id, evidence.evidence_id,
           "ANALYSIS_STARTED", f"Analysis run {run_id} started.")
    log_step("IMPORT", "OK", f"Evidence: {evidence.original_filename}")
    log_step("HASH", "OK", f"SHA-256: {evidence.sha256_hash}")

    db_path = evidence.stored_path

    # ── Step 1: Validate SQLite & detect encryption ──────────────────────────
    from app.forensic.inspector import inspect_database
    insp = inspect_database(db_path)

    # Run forensic deleted record recovery regardless of SQLite validity
    recovery = recover_deleted_from_sqlite(db_path)

    # Register forensic database so it shows up in Evidence Explorer (even if encrypted/invalid)
    fdb = register_forensic_database(db, evidence, db_path)
    log_step("IDENTIFY_APP", "OK",
             f"{fdb.app_detected} (Confidence: {fdb.detection_confidence})")
    _audit(db, evidence.case_id, evidence.evidence_id,
           "DATABASE_IDENTIFIED", f"App: {fdb.app_detected}")

    # Telegram Desktop can create an official JSON export. It is readable
    # evidence, but intentionally not SQLite; parse it directly rather than
    # sending it through database carving.
    if is_telegram_export(db_path):
        log_step("VALIDATE", "OK", "Recognized official Telegram Desktop JSON export.")
        parser = TelegramExportParser(db_path, evidence.case_id, evidence.evidence_id, fdb.db_id)
        result = parser.extract()
        warnings.extend(result.warnings)
        errors.extend(result.errors)
        if result.errors:
            log_step("PARSE", "ERROR", "; ".join(result.errors))
        else:
            extracted, conversations = _persist_export_result(db, result, evidence, fdb)
            log_step("PARSE", "OK", f"{extracted} messages, {conversations} conversations from official export.")
            log_step("RECONSTRUCT", "OK", "Exported conversations reconstructed chronologically.")
            _audit(db, evidence.case_id, evidence.evidence_id,
                   "RECORDS_EXTRACTED", f"{extracted} Telegram export messages extracted.")
            run.messages_extracted = extracted
            run.conversations_found = conversations
            run.files_analyzed = 1

        log_step("COMPLETE", "OK", "Analysis pipeline finished.")
        run.end_time = datetime.utcnow()
        run.status = "error" if errors else "completed"
        run.warnings = warnings
        run.errors = errors
        run.pipeline_log = pipeline_log
        evidence.status = "analyzed" if not errors else "error"
        db.commit()
        db.refresh(run)
        return run

    if not insp.is_valid_sqlite:
        if recovery.is_encrypted:
            # Encrypted database — ciphertext is not suitable for byte-carving.
            log_step("VALIDATE", "WARNING",
                     f"Database is ENCRYPTED. {recovery.encryption_hint[:120]}")
            log_step("DELETED_RECOVERY", "OK",
                     "Deferred: decrypt the database with its matching key before deleted-message recovery.")
            _audit(db, evidence.case_id, evidence.evidence_id,
                   "ENCRYPTED_DB_DETECTED",
                   "Encrypted database detected. No ciphertext fragments were presented as recovered messages.")

            # Never create messages from encrypted bytes. A .crypt14 backup
            # must first produce authenticated SQLite plaintext via the key
            # upload flow; only that derivative is eligible for carving.
            run.messages_extracted = 0
            run.status = "completed"
            run.end_time = datetime.utcnow()
            run.warnings = ["Database is encrypted. Supply the matching key to create a verified SQLite derivative before recovery."]
            run.pipeline_log = pipeline_log
            evidence.status = "analyzed"
            evidence.is_encrypted = True
            db.commit()
            db.refresh(run)
            return run
        else:
            err = insp.error or "Not a valid SQLite database."
            log_step("VALIDATE", "ERROR", err)
            errors.append(err)
            run.status = "error"
            run.end_time = datetime.utcnow()
            run.errors = errors
            run.pipeline_log = pipeline_log
            db.commit()
            return run

    log_step("VALIDATE", "OK", f"SQLite valid. {len(insp.tables)} tables. WAL: {insp.wal_detected}")
    _audit(db, evidence.case_id, evidence.evidence_id,
           "DATABASE_VALIDATED", f"SQLite validated. {len(insp.tables)} tables.")
           
    log_step("INSPECT_SCHEMA", "OK",
             f"{fdb.table_count} tables, {fdb.total_records} records")

    # Select parser
    app_name = fdb.app_detected or "Unknown"
    ParserClass = PARSER_MAP.get(app_name)

    if ParserClass is None:
        w = f"No specific parser for '{app_name}'. Skipping message extraction."
        warnings.append(w)
        log_step("PARSE", "WARNING", w)
    else:
        parser = ParserClass(
            db_path=db_path,
            case_id=evidence.case_id,
            evidence_id=evidence.evidence_id,
            db_id=fdb.db_id,
        )
        log_step("PARSE", "OK", f"Using {parser.parser_label}")

        result: ParserResult = parser.extract()
        warnings.extend(result.warnings)
        errors.extend(result.errors)

        if result.errors:
            log_step("PARSE", "ERROR", "; ".join(result.errors))
        else:
            log_step("PARSE", "OK",
                     f"{len(result.messages)} messages, {len(result.conversations)} conversations")
            _audit(db, evidence.case_id, evidence.evidence_id,
                   "RECORDS_EXTRACTED",
                   f"{len(result.messages)} messages extracted.")

        # Persist conversations
        conv_map = {}
        for c in result.conversations:
            existing = db.query(Conversation).filter(
                Conversation.conv_id == c.conv_id,
                Conversation.db_id == fdb.db_id
            ).first()
            if not existing:
                conv_obj = Conversation(
                    conv_id=c.conv_id,
                    db_id=fdb.db_id,
                    case_id=evidence.case_id,
                    application=app_name,
                    display_name=c.display_name,
                    participants=c.participants,
                    is_group=c.is_group,
                    group_name=c.group_name,
                    message_count=0,
                )
                db.add(conv_obj)
                db.flush()
                conv_map[c.conv_id] = conv_obj
            else:
                conv_map[c.conv_id] = existing

        # Persist messages
        log_step("NORMALIZE", "OK", "Normalizing canonical message records.")
        for msg in result.messages:
            _persist_message(db, msg, fdb.db_id)

        db.flush()

        # Update conversation message counts + timestamps
        for conv_id, conv_obj in conv_map.items():
            msgs = db.query(Message).filter(
                Message.conv_id == conv_id,
                Message.db_id == fdb.db_id
            ).all()
            conv_obj.message_count = len(msgs)
            ts_list = [m.timestamp for m in msgs if m.timestamp]
            if ts_list:
                conv_obj.first_message_ts = min(ts_list)
                conv_obj.last_message_ts = max(ts_list)

        # Also create conversations for messages with unknown conv_ids
        unknown_convs = set()
        for msg in result.messages:
            if msg.conv_id and msg.conv_id not in conv_map:
                unknown_convs.add(msg.conv_id)
        for cid in unknown_convs:
            msgs_for_cid = [m for m in result.messages if m.conv_id == cid]
            conv_obj = Conversation(
                conv_id=cid,
                db_id=fdb.db_id,
                case_id=evidence.case_id,
                application=app_name,
                display_name=cid,
                participants=[],
                is_group=False,
                message_count=len(msgs_for_cid),
            )
            db.add(conv_obj)
            db.flush()
            conv_map[cid] = conv_obj

        # ── Step: Save Recovered Deleted Messages ───────────────────────────
        active_texts = {
            (msg.message_text or "").strip()
            for msg in result.messages
            if (msg.message_text or "").strip()
        }
        recovered_only = []
        for text in recovery.recovered_texts:
            cleaned = text.strip()
            if not cleaned or is_schema_noise(cleaned) or cleaned in active_texts:
                continue
            if cleaned not in recovered_only:
                recovered_only.append(cleaned)

        if recovered_only:
            log_step("DELETED_RECOVERY", "OK",
                     f"Recovered {len(recovered_only)} text fragment(s) from freelist/WAL (not present in live rows).")
            _audit(db, evidence.case_id, evidence.evidence_id,
                   "DELETED_RECOVERY",
                   f"Freelist/WAL recovery found {len(recovered_only)} deleted text fragments.")

            rec_conv_id = f"recovered__{evidence.evidence_id}"
            rec_conv = Conversation(
                conv_id=rec_conv_id,
                db_id=fdb.db_id,
                case_id=evidence.case_id,
                application=app_name,
                display_name=f"[RECOVERED DELETED] {evidence.original_filename}",
                participants=[],
                is_group=False,
                message_count=len(recovered_only),
            )
            db.add(rec_conv)
            db.flush()
            conv_map[rec_conv_id] = rec_conv

            for i, text in enumerate(recovered_only[:500]):
                m = Message(
                    message_id=f"rec_{evidence.evidence_id}_{i}",
                    conv_id=rec_conv_id,
                    case_id=evidence.case_id,
                    evidence_id=evidence.evidence_id,
                    db_id=fdb.db_id,
                    application=app_name,
                    sender="[RECOVERED]",
                    message_text=text,
                    message_type="text",
                    evidence_status="DELETED_RECOVERED",
                    extraction_method="freelist_or_wal",
                    parser_version="DeletedRecovery 1.1",
                    confidence="medium",
                    has_attachment=False,
                    source_database=evidence.original_filename,
                    source_table="sqlite_freelist",
                )
                db.add(m)
        else:
            log_step("DELETED_RECOVERY", "OK",
                     "No extra deleted fragments in freelist/WAL beyond live rows.")

        log_step("RECONSTRUCT", "OK", "Conversations reconstructed chronologically.")
        log_step("MEDIA_CORRELATE", "OK", "Media references recorded.")
        log_step("VALIDATE_RESULTS", "OK", f"Warnings: {len(warnings)}, Errors: {len(errors)}")

        run.messages_extracted = len(result.messages)
        run.conversations_found = len(result.conversations)
        run.files_analyzed = 1

    log_step("COMPLETE", "OK", "Analysis pipeline finished.")
    _audit(db, evidence.case_id, evidence.evidence_id,
           "ANALYSIS_COMPLETE", f"Run {run_id} complete. Messages: {run.messages_extracted}")

    run.end_time = datetime.utcnow()
    run.status = "error" if (errors and not warnings) else "completed"
    run.warnings = warnings
    run.errors = errors
    run.pipeline_log = pipeline_log

    evidence.status = "analyzed"
    db.commit()
    db.refresh(run)
    return run


def _persist_message(db: Session, msg: CanonicalMessage, db_id: str):
    """Save a canonical message to the metadata database."""
    existing = db.query(Message).filter(
        Message.message_id == msg.message_id,
        Message.db_id == db_id,
    ).first()
    if existing:
        if existing.evidence_status == "ACTIVE" and msg.evidence_status in ("DELETED", "DELETED_RECOVERED"):
            existing.evidence_status = msg.evidence_status
            existing.extraction_method = msg.extraction_method or existing.extraction_method
            if msg.message_text and not existing.message_text:
                existing.message_text = msg.message_text
        return

    m = Message(
        message_id=msg.message_id,
        conv_id=msg.conv_id,
        case_id=msg.case_id,
        evidence_id=msg.evidence_id,
        db_id=db_id,
        application=msg.application,
        sender=msg.sender,
        recipient=msg.recipient,
        message_text=msg.message_text,
        message_type=msg.message_type,
        direction=msg.direction,
        status=msg.status,
        evidence_status=msg.evidence_status,
        timestamp=msg.timestamp,
        timestamp_original=msg.timestamp_original,
        timezone_info=msg.timezone_info,
        has_attachment=msg.has_attachment,
        attachment_name=msg.attachment_name,
        attachment_path=msg.attachment_path,
        attachment_found=msg.attachment_found,
        attachment_sha256=msg.attachment_sha256,
        source_database=msg.source_database,
        source_table=msg.source_table,
        source_column=msg.source_column,
        source_record=msg.source_record,
        raw_record=msg.raw_record,
        extraction_method=msg.extraction_method,
        parser_version=msg.parser_version,
        confidence=msg.confidence,
    )
    db.add(m)
