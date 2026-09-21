"""
Forensic SQLite deleted record recovery.

Scans only locations that can hold superseded rows:
1. Freelist pages (space freed when rows were deleted)
2. WAL frames that may still contain an older row version

Live table pages are not carved. Doing so would re-label active messages as
deleted and is the source of bogus reconstructed text.
"""
from pathlib import Path
from typing import List, Optional

from app.forensic.snapshot_diff import is_schema_noise
import struct
import re
from dataclasses import dataclass, field

SQLITE_MAGIC = b"SQLite format 3\x00"


@dataclass
class RecoveredFragment:
    """A text fragment recovered from raw database pages."""
    source: str           # "freelist_page" | "wal_frame"
    page_number: int
    raw_bytes: bytes
    text_fragments: List[str] = field(default_factory=list)
    confidence: str = "medium"   # high / medium / low


@dataclass
class DeletedRecoveryResult:
    db_path: str
    is_readable: bool
    is_encrypted: bool
    encryption_hint: str = ""
    recovered_texts: List[str] = field(default_factory=list)
    recovered_fragments: List[RecoveredFragment] = field(default_factory=list)
    total_pages_scanned: int = 0
    freelist_pages: int = 0
    error: Optional[str] = None


def _detect_encryption_type(path: Path) -> tuple[bool, str]:
    try:
        with open(path, "rb") as f:
            header = f.read(100)
    except Exception:
        return False, ""

    if header[:16] == SQLITE_MAGIC:
        return False, ""

    if path.name.lower().endswith((".crypt5", ".crypt7", ".crypt8", ".crypt12", ".crypt14", ".crypt15")):
        return True, "WhatsApp encrypted backup container. A matching authorized key is required."

    return False, "Not a readable SQLite database or recognized encrypted backup."


def _extract_printable_texts(data: bytes, min_length: int = 8) -> List[str]:
    texts = []
    pattern = r'[a-zA-Z0-9\s.,!?\'"()\[\]:;\-]{' + str(min_length) + r',}'
    try:
        text = data.decode("utf-8", errors="replace")
        for match in re.finditer(pattern, text):
            fragment = match.group(0).strip()
            letter_space_count = sum(1 for c in fragment if c.isalpha() or c.isspace())
            if (
                len(fragment) >= min_length
                and letter_space_count / len(fragment) > 0.5
                and not is_schema_noise(fragment)
            ):
                texts.append(fragment)
    except Exception:
        pass
    return texts


def _read_page_size(path: Path) -> int:
    try:
        with open(path, "rb") as f:
            f.seek(16)
            data = f.read(2)
        if len(data) == 2:
            size = struct.unpack(">H", data)[0]
            return size if size > 0 else 4096
    except Exception:
        pass
    return 4096


def _get_freelist_pages(path: Path, page_size: int) -> List[int]:
    freelist_page_nums = []
    try:
        with open(path, "rb") as f:
            f.seek(32)
            first_trunk = struct.unpack(">I", f.read(4))[0]
            total_free = struct.unpack(">I", f.read(4))[0]

        if first_trunk == 0 or total_free == 0:
            return []

        with open(path, "rb") as f:
            trunk = first_trunk
            seen = set()
            while trunk != 0 and trunk not in seen:
                seen.add(trunk)
                freelist_page_nums.append(trunk)
                offset = (trunk - 1) * page_size
                f.seek(offset)
                page_data = f.read(page_size)
                if len(page_data) < 8:
                    break
                next_trunk = struct.unpack(">I", page_data[:4])[0]
                leaf_count = struct.unpack(">I", page_data[4:8])[0]
                for i in range(min(leaf_count, (page_size - 8) // 4)):
                    leaf_offset = 8 + i * 4
                    if leaf_offset + 4 <= len(page_data):
                        leaf_num = struct.unpack(">I", page_data[leaf_offset:leaf_offset + 4])[0]
                        if leaf_num > 0:
                            freelist_page_nums.append(leaf_num)
                trunk = next_trunk
    except Exception:
        pass

    return freelist_page_nums


def _add_texts(result: DeletedRecoveryResult, source: str, page_number: int,
               data: bytes, confidence: str) -> None:
    texts = _extract_printable_texts(data, min_length=10)
    if not texts:
        return
    result.recovered_fragments.append(RecoveredFragment(
        source=source,
        page_number=page_number,
        raw_bytes=data[:64],
        text_fragments=texts,
        confidence=confidence,
    ))
    for text in texts:
        if text not in result.recovered_texts:
            result.recovered_texts.append(text)


def recover_deleted_from_sqlite(db_path: str) -> DeletedRecoveryResult:
    """Recover candidate deleted text from freelist pages and a companion WAL."""
    path = Path(db_path)
    result = DeletedRecoveryResult(db_path=db_path, is_readable=False, is_encrypted=False)

    if not path.exists():
        result.error = "File does not exist"
        return result

    is_enc, enc_hint = _detect_encryption_type(path)
    result.is_encrypted = is_enc
    result.encryption_hint = enc_hint

    if path.stat().st_size == 0:
        result.error = "File is empty"
        return result

    if is_enc:
        result.error = "Encrypted data cannot be carved reliably. Supply the matching decryption key first."
        return result

    with open(path, "rb") as handle:
        magic = handle.read(16)
    if magic != SQLITE_MAGIC:
        result.error = "Not a readable SQLite database."
        return result

    result.is_readable = True
    page_size = _read_page_size(path)
    freelist_pages = _get_freelist_pages(path, page_size)
    result.freelist_pages = len(freelist_pages)
    result.total_pages_scanned = len(freelist_pages)

    try:
        with open(path, "rb") as f:
            for page_num in freelist_pages:
                try:
                    f.seek((page_num - 1) * page_size)
                    page_data = f.read(page_size)
                    _add_texts(result, "freelist_page", page_num, page_data, "high")
                except Exception:
                    continue
    except Exception as exc:
        result.error = str(exc)

    wal_path = Path(str(path) + "-wal")
    if wal_path.exists() and wal_path.stat().st_size > 32:
        try:
            wal_bytes = wal_path.read_bytes()
            # WAL header is 32 bytes; frames follow. Scan frames only.
            _add_texts(result, "wal_frame", 0, wal_bytes[32:], "medium")
        except OSError:
            pass

    return result
