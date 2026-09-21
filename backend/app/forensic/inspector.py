"""
SQLite database inspector for forensic analysis.

Reads database structure in read-only mode.
Never modifies the original evidence.
"""
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


SQLITE_MAGIC = b"SQLite format 3\x00"


@dataclass
class ColumnInfo:
    cid: int
    name: str
    type: str
    notnull: bool
    default_value: Optional[str]
    is_pk: bool


@dataclass
class TableInfo:
    name: str
    row_count: int
    columns: List[ColumnInfo] = field(default_factory=list)


@dataclass
class IndexInfo:
    name: str
    table: str
    unique: bool
    columns: List[str] = field(default_factory=list)


@dataclass
class DatabaseInspection:
    filename: str
    is_valid_sqlite: bool
    page_size: Optional[int]
    tables: List[TableInfo] = field(default_factory=list)
    indexes: List[IndexInfo] = field(default_factory=list)
    total_records: int = 0
    wal_path: Optional[str] = None
    shm_path: Optional[str] = None
    journal_path: Optional[str] = None
    wal_detected: bool = False
    shm_detected: bool = False
    journal_detected: bool = False
    error: Optional[str] = None


def _read_page_size(db_path: Path) -> Optional[int]:
    """Read page size from SQLite header bytes 16–17."""
    try:
        with open(db_path, "rb") as f:
            f.seek(16)
            data = f.read(2)
        if len(data) == 2:
            return int.from_bytes(data, "big")
    except Exception:
        pass
    return None


def _detect_companions(db_path: Path) -> Dict[str, Optional[str]]:
    """Detect WAL/SHM/journal companion files."""
    result = {"wal": None, "shm": None, "journal": None}
    wal = Path(str(db_path) + "-wal")
    shm = Path(str(db_path) + "-shm")
    journal = Path(str(db_path) + "-journal")
    if wal.exists():
        result["wal"] = str(wal)
    if shm.exists():
        result["shm"] = str(shm)
    if journal.exists():
        result["journal"] = str(journal)
    return result


def inspect_database(db_path: str) -> DatabaseInspection:
    """
    Inspect a SQLite database in read-only mode.

    Parameters
    ----------
    db_path : str
        Absolute path to the SQLite file.

    Returns
    -------
    DatabaseInspection
        Full schema and structural metadata.
    """
    path = Path(db_path)
    inspection = DatabaseInspection(filename=path.name, is_valid_sqlite=False, page_size=None)

    # Validate magic bytes
    try:
        with open(path, "rb") as f:
            magic = f.read(16)
        if magic != SQLITE_MAGIC:
            inspection.error = "Not a valid SQLite database (invalid magic bytes)."
            return inspection
    except Exception as e:
        inspection.error = f"Cannot read file: {e}"
        return inspection

    inspection.is_valid_sqlite = True
    inspection.page_size = _read_page_size(path)

    # Detect companions
    companions = _detect_companions(path)
    inspection.wal_path = companions["wal"]
    inspection.shm_path = companions["shm"]
    inspection.journal_path = companions["journal"]
    inspection.wal_detected = companions["wal"] is not None
    inspection.shm_detected = companions["shm"] is not None
    inspection.journal_detected = companions["journal"] is not None

    # Open read-only
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
    except Exception as e:
        inspection.error = f"Cannot open database: {e}"
        return inspection

    try:
        # Retrieve tables
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        table_names = [row["name"] for row in cur.fetchall()]

        for tname in table_names:
            # Row count
            try:
                count_row = conn.execute(f'SELECT COUNT(*) FROM "{tname}"').fetchone()
                row_count = count_row[0] if count_row else 0
            except Exception:
                row_count = -1

            # Column info
            columns: List[ColumnInfo] = []
            try:
                for col in conn.execute(f'PRAGMA table_info("{tname}")'):
                    columns.append(ColumnInfo(
                        cid=col["cid"],
                        name=col["name"],
                        type=col["type"],
                        notnull=bool(col["notnull"]),
                        default_value=col["dflt_value"],
                        is_pk=bool(col["pk"]),
                    ))
            except Exception:
                pass

            inspection.tables.append(TableInfo(
                name=tname, row_count=row_count, columns=columns
            ))

        inspection.total_records = sum(
            t.row_count for t in inspection.tables if t.row_count > 0
        )

        # Indexes
        cur = conn.execute(
            "SELECT name, tbl_name, \"unique\" FROM sqlite_master WHERE type='index'"
        )
        for row in cur.fetchall():
            idx = IndexInfo(name=row[0], table=row[1], unique=bool(row[2]))
            try:
                col_rows = conn.execute(f'PRAGMA index_info("{row[0]}")')
                idx.columns = [c["name"] for c in col_rows.fetchall()]
            except Exception:
                pass
            inspection.indexes.append(idx)

    except Exception as e:
        inspection.error = f"Inspection error: {e}"
    finally:
        conn.close()

    return inspection


def get_table_rows(
    db_path: str,
    table: str,
    page: int = 1,
    page_size: int = 50,
    search: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Return a paginated, read-only view of a table's rows.

    Returns
    -------
    dict with keys: columns, rows, total_rows, page, page_size
    """
    path = Path(db_path)
    result: Dict[str, Any] = {
        "columns": [], "rows": [], "total_rows": 0,
        "page": page, "page_size": page_size,
    }

    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row

        # Columns
        col_rows = conn.execute(f'PRAGMA table_info("{table}")')
        result["columns"] = [r["name"] for r in col_rows.fetchall()]

        # Total count
        total = conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        result["total_rows"] = total

        offset = (page - 1) * page_size
        rows_cur = conn.execute(
            f'SELECT * FROM "{table}" LIMIT ? OFFSET ?',
            (page_size, offset),
        )
        result["rows"] = [dict(r) for r in rows_cur.fetchall()]
        conn.close()
    except Exception as e:
        result["error"] = str(e)

    return result
