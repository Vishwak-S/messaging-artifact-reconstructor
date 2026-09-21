"""
Base parser interface.

All application-specific parsers must inherit from BaseParser and implement
all abstract methods. This ensures the parser architecture is extensible.
"""
import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.forensic.detector import DetectionResult
from app.forensic.provenance import ProvenanceInfo
from app.utils.timestamps import parse_timestamp


# ── Canonical data model ─────────────────────────────────────────────────────

@dataclass
class CanonicalContact:
    contact_id: str
    display_name: Optional[str]
    phone_or_username: Optional[str]
    source_table: str
    source_record: str
    raw_record: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CanonicalConversation:
    conv_id: str
    display_name: Optional[str]
    participants: List[str] = field(default_factory=list)
    is_group: bool = False
    group_name: Optional[str] = None
    application: str = ""
    source_table: str = ""


@dataclass
class CanonicalMessage:
    """
    Canonical message record preserving all forensic provenance.
    Fields marked Optional may be absent — they must NEVER be fabricated.
    """
    message_id: str
    conv_id: Optional[str]
    case_id: str
    evidence_id: str
    db_id: str
    application: str

    sender: Optional[str]
    recipient: Optional[str]
    message_text: Optional[str]
    message_type: str                  # text / image / video / audio / document / sticker / ...
    direction: Optional[str]           # incoming / outgoing
    status: Optional[str]
    evidence_status: str = "ACTIVE"   # ACTIVE / DELETED / RECOVERED / PARTIAL / UNKNOWN

    # Timestamps
    timestamp: Optional[datetime] = None
    timestamp_original: Optional[str] = None
    timezone_info: Optional[str] = None

    # Attachment
    has_attachment: bool = False
    attachment_name: Optional[str] = None
    attachment_path: Optional[str] = None
    attachment_found: Optional[bool] = None
    attachment_sha256: Optional[str] = None

    # Provenance
    source_database: str = ""
    source_table: str = ""
    source_column: Optional[str] = None
    source_record: str = ""
    raw_record: Dict[str, Any] = field(default_factory=dict)
    extraction_method: str = "direct_parse"
    parser_version: str = "BaseParser v1.0"
    confidence: str = "high"


@dataclass
class ParserResult:
    application: str
    parser_version: str
    contacts: List[CanonicalContact] = field(default_factory=list)
    conversations: List[CanonicalConversation] = field(default_factory=list)
    messages: List[CanonicalMessage] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


# ── Base parser ───────────────────────────────────────────────────────────────

class BaseParser(ABC):
    """Abstract base class for all messaging application parsers."""

    VERSION = "1.0"
    APPLICATION = "Unknown"

    def __init__(self, db_path: str, case_id: str, evidence_id: str, db_id: str):
        self.db_path = Path(db_path)
        self.case_id = case_id
        self.evidence_id = evidence_id
        self.db_id = db_id
        self.db_filename = self.db_path.name
        self._conn: Optional[sqlite3.Connection] = None
        self._tables: List[str] = []

    def _open_readonly(self) -> bool:
        """Open the database in read-only mode. Returns False on failure."""
        try:
            self._conn = sqlite3.connect(
                f"file:{self.db_path}?mode=ro", uri=True
            )
            self._conn.row_factory = sqlite3.Row
            cur = self._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            self._tables = [r["name"].lower() for r in cur.fetchall()]
            return True
        except Exception as e:
            self._tables = []
            return False

    def _close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def _has_table(self, name: str) -> bool:
        return name.lower() in self._tables

    def _get_columns(self, table: str) -> List[str]:
        try:
            cur = self._conn.execute(f'PRAGMA table_info("{table}")')
            return [r["name"] for r in cur.fetchall()]
        except Exception:
            return []

    def _safe_query(self, sql: str, params: tuple = ()) -> List[sqlite3.Row]:
        try:
            return self._conn.execute(sql, params).fetchall()
        except Exception:
            return []

    def _parse_ts(self, raw) -> tuple:
        dt, tz, method = parse_timestamp(raw)
        return dt, str(raw) if raw is not None else None, tz

    @abstractmethod
    def detect(self) -> DetectionResult:
        """Detect whether this database belongs to the target application."""
        ...

    @abstractmethod
    def extract(self) -> ParserResult:
        """Extract all available forensic records from the database."""
        ...

    @property
    def parser_label(self) -> str:
        return f"{self.__class__.__name__} v{self.VERSION}"
