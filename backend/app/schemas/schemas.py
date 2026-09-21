"""Pydantic schemas for request/response validation."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ─── Cases ────────────────────────────────────────────────────────────────────

class CaseCreate(BaseModel):
    name: str
    description: Optional[str] = None
    investigator: Optional[str] = None


class CaseResponse(BaseModel):
    id: int
    case_id: str
    name: str
    description: Optional[str]
    investigator: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─── Evidence ─────────────────────────────────────────────────────────────────

class EvidenceResponse(BaseModel):
    id: int
    evidence_id: str
    case_id: str
    original_filename: str
    original_size_bytes: Optional[int]
    sha256_hash: Optional[str]
    import_timestamp: datetime
    status: str
    app_detected: Optional[str]
    detection_confidence: Optional[str]
    detection_reasons: Optional[List[str]]
    is_encrypted: bool

    class Config:
        from_attributes = True


class EvidenceDetailResponse(EvidenceResponse):
    companion_files: List[Dict[str, Any]] = []
    databases: List[Dict[str, Any]] = []


# ─── Forensic Database ────────────────────────────────────────────────────────

class DatabaseResponse(BaseModel):
    id: int
    db_id: str
    evidence_id: str
    case_id: str
    db_filename: str
    app_detected: Optional[str]
    detection_confidence: Optional[str]
    detection_reasons: Optional[List[str]]
    table_count: Optional[int]
    total_records: Optional[int]
    sqlite_valid: bool
    wal_detected: bool
    shm_detected: bool
    journal_detected: bool
    page_size: Optional[int]
    schema_info: Optional[Dict[str, Any]]
    analyzed_at: Optional[datetime]

    class Config:
        from_attributes = True


# ─── Conversations ────────────────────────────────────────────────────────────

class ConversationResponse(BaseModel):
    id: int
    conv_id: str
    db_id: str
    case_id: str
    application: Optional[str]
    display_name: Optional[str]
    participants: Optional[List[str]]
    message_count: int
    first_message_ts: Optional[datetime]
    last_message_ts: Optional[datetime]
    is_group: bool
    group_name: Optional[str]

    class Config:
        from_attributes = True


# ─── Messages ─────────────────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    id: int
    message_id: str
    conv_id: Optional[str]
    case_id: str
    evidence_id: str
    db_id: str
    application: Optional[str]
    sender: Optional[str]
    recipient: Optional[str]
    message_text: Optional[str]
    message_type: str
    direction: Optional[str]
    status: Optional[str]
    evidence_status: str
    timestamp: Optional[datetime]
    timestamp_original: Optional[str]
    timezone_info: Optional[str]
    has_attachment: bool
    attachment_name: Optional[str]
    attachment_found: Optional[bool]
    attachment_sha256: Optional[str]
    source_database: Optional[str]
    source_table: Optional[str]
    source_column: Optional[str]
    source_record: Optional[str]
    raw_record: Optional[Dict[str, Any]]
    extraction_method: Optional[str]
    parser_version: Optional[str]
    confidence: str

    class Config:
        from_attributes = True


# ─── Timeline ─────────────────────────────────────────────────────────────────

class TimelineEntry(BaseModel):
    timestamp: Optional[datetime]
    timestamp_original: Optional[str]
    application: Optional[str]
    sender: Optional[str]
    message_type: str
    message_text: Optional[str]
    conv_id: Optional[str]
    message_id: str
    evidence_status: str


# ─── Search ───────────────────────────────────────────────────────────────────

class SearchResult(BaseModel):
    total: int
    page: int
    page_size: int
    results: List[MessageResponse]


# ─── Analysis Runs ────────────────────────────────────────────────────────────

class AnalysisRunResponse(BaseModel):
    id: int
    run_id: str
    case_id: str
    evidence_id: str
    start_time: datetime
    end_time: Optional[datetime]
    status: str
    parser_versions: Optional[Dict[str, str]]
    files_analyzed: int
    messages_extracted: int
    conversations_found: int
    attachments_found: int
    warnings: Optional[List[str]]
    errors: Optional[List[str]]
    pipeline_log: Optional[List[Dict[str, Any]]]

    class Config:
        from_attributes = True


# ─── Audit ────────────────────────────────────────────────────────────────────

class AuditEventResponse(BaseModel):
    id: int
    case_id: Optional[str]
    evidence_id: Optional[str]
    timestamp: datetime
    action: str
    description: Optional[str]

    class Config:
        from_attributes = True


# ─── Reports ──────────────────────────────────────────────────────────────────

class ReportGenerateRequest(BaseModel):
    case_id: str
    format: str = Field(..., pattern="^(pdf|csv|json|html)$")
    include_raw_records: bool = False


class ReportResponse(BaseModel):
    id: int
    report_id: str
    case_id: str
    format: str
    generated_at: datetime
    file_size_bytes: Optional[int]
    download_url: Optional[str] = None

    class Config:
        from_attributes = True


# ─── Hash verification ────────────────────────────────────────────────────────

class HashVerifyResponse(BaseModel):
    evidence_id: str
    original_hash: str
    current_hash: str
    match: bool
    verified_at: datetime


# ─── Database table rows ──────────────────────────────────────────────────────

class TableRowsResponse(BaseModel):
    database: str
    table: str
    total_rows: int
    page: int
    page_size: int
    columns: List[str]
    rows: List[Dict[str, Any]]
