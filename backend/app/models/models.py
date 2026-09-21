"""
SQLAlchemy ORM models for application metadata.

IMPORTANT: These tables store analysis metadata ONLY.
Original evidence databases are NEVER modified.
"""
from datetime import datetime
from sqlalchemy import (
    Column, String, Integer, BigInteger, DateTime, Text,
    ForeignKey, Boolean, Float, JSON
)
from sqlalchemy.orm import relationship
from app.database.db import Base


class Case(Base):
    __tablename__ = "cases"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    investigator = Column(String(255), nullable=True)
    status = Column(String(50), default="open")  # open / closed / archived
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    evidence = relationship("Evidence", back_populates="case", cascade="all, delete-orphan")
    audit_events = relationship("AuditEvent", back_populates="case")
    reports = relationship("Report", back_populates="case")
    analysis_runs = relationship("AnalysisRun", back_populates="case")


class Evidence(Base):
    __tablename__ = "evidence"

    id = Column(Integer, primary_key=True, index=True)
    evidence_id = Column(String(50), unique=True, index=True, nullable=False)
    case_id = Column(String(50), ForeignKey("cases.case_id"), nullable=False)
    original_filename = Column(String(500), nullable=False)
    stored_path = Column(String(1000), nullable=False)  # path in evidence_store
    original_size_bytes = Column(BigInteger, nullable=True)
    sha256_hash = Column(String(64), nullable=True)
    import_timestamp = Column(DateTime, default=datetime.utcnow)
    status = Column(String(50), default="imported")  # imported / analyzed / error
    app_detected = Column(String(50), nullable=True)   # WhatsApp / Telegram / Signal / Unknown
    detection_confidence = Column(String(20), nullable=True)  # High / Medium / Low
    detection_reasons = Column(JSON, nullable=True)
    is_encrypted = Column(Boolean, default=False)
    notes = Column(Text, nullable=True)

    case = relationship("Case", back_populates="evidence")
    companion_files = relationship("EvidenceFile", back_populates="evidence", cascade="all, delete-orphan")
    databases = relationship("ForensicDatabase", back_populates="evidence", cascade="all, delete-orphan")
    analysis_runs = relationship("AnalysisRun", back_populates="evidence")


class EvidenceFile(Base):
    """WAL / SHM / journal companion files."""
    __tablename__ = "evidence_files"

    id = Column(Integer, primary_key=True, index=True)
    evidence_id = Column(String(50), ForeignKey("evidence.evidence_id"), nullable=False)
    file_type = Column(String(20), nullable=False)   # wal / shm / journal
    original_filename = Column(String(500), nullable=False)
    stored_path = Column(String(1000), nullable=False)
    sha256_hash = Column(String(64), nullable=True)

    evidence = relationship("Evidence", back_populates="companion_files")


class ForensicDatabase(Base):
    """Metadata about an inspected SQLite database (evidence artifact)."""
    __tablename__ = "forensic_databases"

    id = Column(Integer, primary_key=True, index=True)
    db_id = Column(String(50), unique=True, index=True, nullable=False)
    evidence_id = Column(String(50), ForeignKey("evidence.evidence_id"), nullable=False)
    case_id = Column(String(50), nullable=False)
    db_filename = Column(String(500), nullable=False)
    app_detected = Column(String(50), nullable=True)
    detection_confidence = Column(String(20), nullable=True)
    detection_reasons = Column(JSON, nullable=True)
    table_count = Column(Integer, nullable=True)
    total_records = Column(Integer, nullable=True)
    sqlite_valid = Column(Boolean, default=False)
    wal_detected = Column(Boolean, default=False)
    shm_detected = Column(Boolean, default=False)
    journal_detected = Column(Boolean, default=False)
    page_size = Column(Integer, nullable=True)
    schema_info = Column(JSON, nullable=True)   # table → [column, ...]
    analyzed_at = Column(DateTime, nullable=True)

    evidence = relationship("Evidence", back_populates="databases")
    conversations = relationship("Conversation", back_populates="database", cascade="all, delete-orphan")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    conv_id = Column(String(100), index=True, nullable=False)
    db_id = Column(String(50), ForeignKey("forensic_databases.db_id"), nullable=False)
    case_id = Column(String(50), nullable=False)
    application = Column(String(50), nullable=True)
    display_name = Column(String(500), nullable=True)
    participants = Column(JSON, nullable=True)
    message_count = Column(Integer, default=0)
    first_message_ts = Column(DateTime, nullable=True)
    last_message_ts = Column(DateTime, nullable=True)
    is_group = Column(Boolean, default=False)
    group_name = Column(String(500), nullable=True)

    database = relationship("ForensicDatabase", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    message_id = Column(String(100), index=True, nullable=False)
    conv_id = Column(String(100), ForeignKey("conversations.conv_id"), nullable=True)
    case_id = Column(String(50), nullable=False)
    evidence_id = Column(String(50), nullable=False)
    db_id = Column(String(50), nullable=False)
    application = Column(String(50), nullable=True)

    sender = Column(String(500), nullable=True)
    recipient = Column(String(500), nullable=True)
    message_text = Column(Text, nullable=True)
    message_type = Column(String(50), default="text")
    direction = Column(String(20), nullable=True)   # incoming / outgoing
    status = Column(String(50), nullable=True)
    evidence_status = Column(String(20), default="ACTIVE")  # ACTIVE / DELETED / RECOVERED / PARTIAL / UNKNOWN

    # Timestamps
    timestamp = Column(DateTime, nullable=True)      # interpreted
    timestamp_original = Column(String(100), nullable=True)  # raw value
    timezone_info = Column(String(100), nullable=True)

    # Attachment
    has_attachment = Column(Boolean, default=False)
    attachment_name = Column(String(500), nullable=True)
    attachment_path = Column(String(1000), nullable=True)
    attachment_found = Column(Boolean, nullable=True)
    attachment_sha256 = Column(String(64), nullable=True)

    # Provenance
    source_database = Column(String(500), nullable=True)
    source_table = Column(String(200), nullable=True)
    source_column = Column(String(200), nullable=True)
    source_record = Column(String(100), nullable=True)
    raw_record = Column(JSON, nullable=True)
    extraction_method = Column(String(100), nullable=True)
    parser_version = Column(String(50), nullable=True)
    confidence = Column(String(20), default="high")

    conversation = relationship("Conversation", back_populates="messages")


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(50), unique=True, index=True, nullable=False)
    case_id = Column(String(50), ForeignKey("cases.case_id"), nullable=False)
    evidence_id = Column(String(50), ForeignKey("evidence.evidence_id"), nullable=False)
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    status = Column(String(50), default="running")   # running / completed / error
    parser_versions = Column(JSON, nullable=True)
    files_analyzed = Column(Integer, default=0)
    messages_extracted = Column(Integer, default=0)
    conversations_found = Column(Integer, default=0)
    attachments_found = Column(Integer, default=0)
    warnings = Column(JSON, nullable=True)
    errors = Column(JSON, nullable=True)
    pipeline_log = Column(JSON, nullable=True)

    case = relationship("Case", back_populates="analysis_runs")
    evidence = relationship("Evidence", back_populates="analysis_runs")


class AuditEvent(Base):
    """Append-only chain-of-custody log."""
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, index=True)
    case_id = Column(String(50), ForeignKey("cases.case_id"), nullable=True)
    evidence_id = Column(String(50), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    action = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    session_id = Column(String(100), nullable=True)

    case = relationship("Case", back_populates="audit_events")


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(String(50), unique=True, index=True)
    case_id = Column(String(50), ForeignKey("cases.case_id"), nullable=False)
    format = Column(String(20), nullable=False)   # pdf / csv / json / html
    file_path = Column(String(1000), nullable=True)
    generated_at = Column(DateTime, default=datetime.utcnow)
    file_size_bytes = Column(BigInteger, nullable=True)

    case = relationship("Case", back_populates="reports")
