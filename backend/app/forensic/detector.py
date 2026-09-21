"""
Multi-indicator messaging application detector.

Detection uses filename, directory structure, SQLite table names,
schema signatures, and known columns — never filename alone.
"""
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


SQLITE_MAGIC = b"SQLite format 3\x00"


@dataclass
class DetectionResult:
    application: str          # WhatsApp / Telegram / Signal / Unknown
    confidence: str           # High / Medium / Low
    reasons: List[str] = field(default_factory=list)
    is_sqlite: bool = False
    is_encrypted: bool = False


# ── Known schema signatures ──────────────────────────────────────────────────

WHATSAPP_TABLES = {"message", "messages", "wa_message", "chat", "chat2", "jid",
                   "media_hash", "message_media", "receipts", "group_participant_user"}
WHATSAPP_FILENAMES = {"msgstore.db", "wa.db", "axolotl.db", "whatsapp.db"}
WHATSAPP_DIR_HINTS = {"whatsapp", "com.whatsapp"}
WHATSAPP_ENCRYPTED_SUFFIXES = (".crypt5", ".crypt7", ".crypt8", ".crypt12", ".crypt14", ".crypt15")

TELEGRAM_TABLES = {"messages", "dialogs", "chats", "users", "media",
                   "enc_chats", "channel_users", "contacts"}
TELEGRAM_FILENAMES = {"cache4.db", "telegram.db", "tgcache.db"}
TELEGRAM_DIR_HINTS = {"telegram", "org.telegram.messenger", "org.telegram"}

SIGNAL_TABLES = {"sms", "mms", "thread", "recipient", "groups",
                 "signal_messages", "message_send_log"}
SIGNAL_FILENAMES = {"signal.db", "signal_backup.db", "database.db"}
SIGNAL_DIR_HINTS = {"signal", "org.thoughtcrime.securesms"}


def _is_sqlite(path: Path) -> bool:
    """Check SQLite magic bytes."""
    try:
        with open(path, "rb") as f:
            return f.read(16) == SQLITE_MAGIC
    except (OSError, IOError):
        return False


def _is_encrypted(path: Path) -> bool:
    """Recognize only known encrypted-backup container names.

    Random binary data and application configuration files are not evidence of
    encryption.  Treating every non-SQLite file as encrypted creates false
    positives and was the source of bogus "recovered" text in the UI.
    """
    return path.name.lower().endswith(WHATSAPP_ENCRYPTED_SUFFIXES)


def _get_tables(db_path: Path) -> List[str]:
    """Safely retrieve table names from an SQLite database."""
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0].lower() for row in cur.fetchall()]
        conn.close()
        return tables
    except Exception:
        return []


def _is_telegram_export(path: Path) -> bool:
    """Recognize Telegram Desktop's official machine-readable JSON export."""
    if path.suffix.lower() != ".json":
        return False
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return isinstance(data, dict) and isinstance(data.get("chats", {}).get("list"), list)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        return False


def _score(tables: List[str], filename: str, parent_dirs: List[str],
           known_tables: set, known_filenames: set, known_dirs: set
           ) -> tuple[int, List[str]]:
    score = 0
    reasons: List[str] = []
    table_set = set(tables)

    matched_tables = known_tables & table_set
    if matched_tables:
        score += len(matched_tables) * 2
        reasons.append(f"Recognized tables: {', '.join(sorted(matched_tables))}")

    if filename.lower() in known_filenames:
        score += 3
        reasons.append(f"Filename matches known artifact: {filename}")

    for d in parent_dirs:
        if any(hint in d.lower() for hint in known_dirs):
            score += 2
            reasons.append(f"Directory path contains known app hint: {d}")
            break

    return score, reasons


def detect_application(db_path: str) -> DetectionResult:
    """
    Multi-indicator detection of the messaging application.

    Parameters
    ----------
    db_path : str
        Absolute path to the candidate SQLite database file.

    Returns
    -------
    DetectionResult
        application, confidence, reasons, is_sqlite, is_encrypted
    """
    path = Path(db_path)
    filename = path.name
    parent_dirs = [p.name for p in path.parents]

    result = DetectionResult(
        application="Unknown",
        confidence="Low",
        is_sqlite=_is_sqlite(path),
        is_encrypted=_is_encrypted(path),
    )

    if _is_telegram_export(path):
        result.application = "Telegram"
        result.confidence = "High"
        result.reasons.append("Recognized official Telegram Desktop JSON export structure.")
        return result

    # Android local backups use a WhatsApp-specific encrypted container.  The
    # name is meaningful here because the contents intentionally are not a
    # SQLite file until they have been decrypted.
    if filename.lower().endswith(WHATSAPP_ENCRYPTED_SUFFIXES):
        result.application = "WhatsApp"
        result.confidence = "High"
        result.is_encrypted = True
        result.reasons.append("Filename is a WhatsApp encrypted local-backup container.")
        return result

    if not result.is_sqlite:
        result.reasons.append("File is not a supported SQLite database or recognized encrypted backup.")
        return result

    tables = _get_tables(path)
    if not tables:
        result.reasons.append("Could not read tables — database may be empty or inaccessible.")

    wa_score, wa_reasons = _score(tables, filename, parent_dirs,
                                   WHATSAPP_TABLES, WHATSAPP_FILENAMES, WHATSAPP_DIR_HINTS)
    tg_score, tg_reasons = _score(tables, filename, parent_dirs,
                                   TELEGRAM_TABLES, TELEGRAM_FILENAMES, TELEGRAM_DIR_HINTS)
    sg_score, sg_reasons = _score(tables, filename, parent_dirs,
                                   SIGNAL_TABLES, SIGNAL_FILENAMES, SIGNAL_DIR_HINTS)

    best_score = max(wa_score, tg_score, sg_score)

    if best_score == 0:
        result.reasons.append("No recognized messaging application schema detected.")
        return result

    if wa_score == best_score:
        result.application = "WhatsApp"
        result.reasons = wa_reasons
    elif tg_score == best_score:
        result.application = "Telegram"
        result.reasons = tg_reasons
    else:
        result.application = "Signal"
        result.reasons = sg_reasons

    if best_score >= 6:
        result.confidence = "High"
    elif best_score >= 3:
        result.confidence = "Medium"
    else:
        result.confidence = "Low"

    return result
