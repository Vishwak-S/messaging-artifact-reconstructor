"""Forensic provenance utilities — source traceability for every extracted record."""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class ProvenanceInfo:
    """
    Full source traceability for an extracted forensic artifact.
    Every extracted message must carry this information.
    """
    application: str
    source_database: str          # filename of the evidence DB
    source_table: str             # table name
    source_column: Optional[str]  # primary content column
    source_record: str            # rowid / primary key
    parser_name: str
    parser_version: str
    extraction_timestamp: datetime = None
    raw_record: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.extraction_timestamp is None:
            self.extraction_timestamp = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "application": self.application,
            "source_database": self.source_database,
            "source_table": self.source_table,
            "source_column": self.source_column,
            "source_record": str(self.source_record),
            "parser_name": self.parser_name,
            "parser_version": self.parser_version,
            "extraction_timestamp": self.extraction_timestamp.isoformat(),
        }
