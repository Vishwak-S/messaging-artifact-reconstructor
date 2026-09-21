"""Classify message changes between two live database snapshots.

Reconstruction of a deletion does not invent text: it keeps the body that was
already observed in an earlier authorized snapshot of the same file.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping


@dataclass
class SnapshotDelta:
    added_ids: list[str] = field(default_factory=list)
    deleted_ids: list[str] = field(default_factory=list)
    still_active_ids: list[str] = field(default_factory=list)


def classify_snapshot_delta(
    previous: Mapping[str, str | None],
    current: Mapping[str, str | None],
) -> SnapshotDelta:
    """Return ids added, still present, or missing since the last snapshot."""
    prev_ids = set(previous)
    curr_ids = set(current)
    return SnapshotDelta(
        added_ids=sorted(curr_ids - prev_ids),
        deleted_ids=sorted(prev_ids - curr_ids),
        still_active_ids=sorted(prev_ids & curr_ids),
    )


def is_schema_noise(text: str) -> bool:
    """Reject SQLite catalog fragments that are not chat content."""
    if not text or not text.strip():
        return True
    upper = text.strip().upper()
    prefixes = (
        "CREATE TABLE",
        "CREATE INDEX",
        "CREATE UNIQUE",
        "SQLITE_AUTOINDEX",
        "SQLITE FORMAT",
        "WITHOUT ROWID",
        "PRIMARY KEY",
        "UNIQUE INDEX",
    )
    return any(upper.startswith(p) for p in prefixes)
