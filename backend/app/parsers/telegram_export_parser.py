"""Parser for Telegram Desktop's official JSON data export."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.parsers.base_parser import CanonicalConversation, CanonicalMessage, ParserResult
from app.utils.timestamps import parse_timestamp

APPLICATION = "Telegram"
VERSION = "1.0"


def is_telegram_export(path: str | Path) -> bool:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return isinstance(data, dict) and isinstance(data.get("chats", {}).get("list"), list)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, AttributeError):
        return False


def _text(value: Any) -> str | None:
    if isinstance(value, str):
        return value or None
    if isinstance(value, list):
        pieces: list[str] = []
        for part in value:
            if isinstance(part, str):
                pieces.append(part)
            elif isinstance(part, dict) and isinstance(part.get("text"), str):
                pieces.append(part["text"])
        return "".join(pieces) or None
    return None


class TelegramExportParser:
    """Convert an official Telegram JSON export into canonical records."""

    def __init__(self, export_path: str, case_id: str, evidence_id: str, db_id: str):
        self.export_path = Path(export_path)
        self.case_id = case_id
        self.evidence_id = evidence_id
        self.db_id = db_id

    @property
    def parser_label(self) -> str:
        return f"TelegramExportParser v{VERSION}"

    def extract(self) -> ParserResult:
        result = ParserResult(application=APPLICATION, parser_version=self.parser_label)
        try:
            data = json.loads(self.export_path.read_text(encoding="utf-8"))
            chats = data["chats"]["list"]
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
            result.errors.append(f"Cannot read Telegram JSON export: {exc}")
            return result

        for chat_index, chat in enumerate(chats):
            if not isinstance(chat, dict):
                continue
            conv_id = str(chat.get("id") or f"export_chat_{chat_index}")
            chat_type = str(chat.get("type") or "")
            is_group = chat_type in {"private_group", "public_group", "private_supergroup", "public_supergroup", "channel"}
            display_name = chat.get("name") or chat.get("title") or conv_id
            result.conversations.append(CanonicalConversation(
                conv_id=conv_id,
                display_name=str(display_name),
                is_group=is_group,
                group_name=str(display_name) if is_group else None,
                application=APPLICATION,
                source_table="chats.list",
            ))

            for message_index, message in enumerate(chat.get("messages") or []):
                if not isinstance(message, dict) or message.get("type") != "message":
                    continue
                text = _text(message.get("text"))
                raw_date = message.get("date")
                timestamp, timezone, _method = parse_timestamp(raw_date)
                original_id = str(message.get("id") or message_index)
                media_type = str(message.get("media_type") or "")
                result.messages.append(CanonicalMessage(
                    message_id=f"{conv_id}:{original_id}",
                    conv_id=conv_id,
                    case_id=self.case_id,
                    evidence_id=self.evidence_id,
                    db_id=self.db_id,
                    application=APPLICATION,
                    sender=message.get("from"),
                    recipient=str(display_name),
                    message_text=text,
                    message_type="text" if text else (media_type or "message"),
                    direction=None,
                    status=None,
                    evidence_status="ACTIVE",
                    timestamp=timestamp,
                    timestamp_original=str(raw_date) if raw_date else None,
                    timezone_info=timezone,
                    has_attachment=bool(message.get("file") or media_type),
                    attachment_name=message.get("file_name"),
                    source_database=self.export_path.name,
                    source_table="chats.list.messages",
                    source_column="text",
                    source_record=original_id,
                    raw_record=message,
                    extraction_method="official_telegram_export",
                    parser_version=self.parser_label,
                    confidence="high",
                ))
        return result
