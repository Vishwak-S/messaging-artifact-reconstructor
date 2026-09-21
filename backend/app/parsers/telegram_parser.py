"""
Telegram SQLite artifact parser.

Inspects the schema dynamically and gracefully handles
both Telegram Desktop and Telegram Android/iOS schemas.
"""
import uuid
from typing import Any, Dict, List, Optional

from app.forensic.detector import DetectionResult, detect_application
from app.parsers.base_parser import (
    BaseParser, CanonicalContact, CanonicalConversation,
    CanonicalMessage, ParserResult
)

VERSION = "1.0"
APPLICATION = "Telegram"

TG_MSG_TYPES = {
    0: "text",
    1: "photo",
    2: "video",
    3: "audio",
    4: "document",
    5: "contact",
    6: "location",
    7: "sticker",
    8: "voice_message",
}


def _resolve_msg_type(t: Any) -> str:
    if t is None:
        return "unknown"
    try:
        return TG_MSG_TYPES.get(int(t), f"type_{t}")
    except (ValueError, TypeError):
        return str(t)


class TelegramParser(BaseParser):
    VERSION = "1.0"
    APPLICATION = "Telegram"

    def detect(self) -> DetectionResult:
        return detect_application(str(self.db_path))

    def extract(self) -> ParserResult:
        result = ParserResult(
            application=APPLICATION,
            parser_version=self.parser_label,
        )

        if not self._open_readonly():
            result.errors.append(f"Cannot open database: {self.db_path.name}")
            return result

        try:
            self._extract_users(result)
            self._extract_chats(result)
            self._extract_messages(result)
        except Exception as e:
            result.errors.append(f"Extraction error: {e}")
        finally:
            self._close()

        return result

    def _extract_users(self, result: ParserResult):
        for table in ("users", "contacts"):
            if not self._has_table(table):
                continue
            rows = self._safe_query(f'SELECT * FROM "{table}" LIMIT 5000')
            for row in rows:
                d = dict(row)
                uid = str(d.get("uid") or d.get("_id") or d.get("id") or uuid.uuid4())
                name_parts = [d.get("first_name") or "", d.get("last_name") or ""]
                name = " ".join(p for p in name_parts if p).strip() or d.get("name")
                result.contacts.append(CanonicalContact(
                    contact_id=uid,
                    display_name=name,
                    phone_or_username=d.get("username") or d.get("phone"),
                    source_table=table,
                    source_record=uid,
                    raw_record=d,
                ))
            break  # only use first matched table

    def _extract_chats(self, result: ParserResult):
        for table in ("dialogs", "chats", "enc_chats"):
            if not self._has_table(table):
                continue
            rows = self._safe_query(f'SELECT * FROM "{table}" LIMIT 5000')
            for row in rows:
                d = dict(row)
                cid = str(d.get("did") or d.get("uid") or d.get("_id") or uuid.uuid4())
                is_group = d.get("type") in (1, 2) or "channel" in str(d.get("title") or "").lower()
                result.conversations.append(CanonicalConversation(
                    conv_id=cid,
                    display_name=d.get("name") or d.get("title") or d.get("did"),
                    participants=[],
                    is_group=is_group,
                    group_name=d.get("title") or d.get("name") if is_group else None,
                    application=APPLICATION,
                    source_table=table,
                ))

    def _extract_messages(self, result: ParserResult):
        msg_table = None
        for candidate in ("messages", "messages_v2", "message"):
            if self._has_table(candidate):
                msg_table = candidate
                break

        if msg_table is None:
            result.warnings.append("No recognized Telegram messages table found.")
            return

        cols = self._get_columns(msg_table)
        col_set = set(cols)

        def col(name): return name if name in col_set else None

        text_col = col("message") or col("text") or col("data") or col("body")
        ts_col = col("date") or col("timestamp") or col("send_date")
        from_col = col("from_id") or col("uid") or col("sender_id")
        did_col = col("did") or col("dialog_id") or col("chat_id")
        type_col = col("type")
        mid_col = col("mid") or col("_id")

        rows = self._safe_query(
            f'SELECT rowid, * FROM "{msg_table}" ORDER BY {ts_col or "rowid"} ASC'
        )

        if not rows:
            result.warnings.append(f"No rows in '{msg_table}'.")
            return

        for row in rows:
            d = dict(row)
            record_id = str(d.get("mid") or d.get("_id") or d.get("rowid") or uuid.uuid4())
            raw_ts = d.get(ts_col) if ts_col else None
            ts_dt, ts_orig, tz_info = self._parse_ts(raw_ts)
            msg_type = _resolve_msg_type(d.get(type_col) if type_col else None)
            conv_id = str(d.get(did_col)) if did_col else None

            from_me_flag = d.get("out")
            if from_me_flag is not None:
                direction = "outgoing" if int(from_me_flag) == 1 else "incoming"
            else:
                direction = None

            result.messages.append(CanonicalMessage(
                message_id=record_id,
                conv_id=conv_id,
                case_id=self.case_id,
                evidence_id=self.evidence_id,
                db_id=self.db_id,
                application=APPLICATION,
                sender=str(d.get(from_col) or ""),
                recipient=str(conv_id or ""),
                message_text=d.get(text_col) if text_col else None,
                message_type=msg_type,
                direction=direction,
                status=str(d.get("read_state") or d.get("status") or ""),
                evidence_status="ACTIVE",
                timestamp=ts_dt,
                timestamp_original=ts_orig,
                timezone_info=tz_info,
                has_attachment=False,
                source_database=self.db_filename,
                source_table=msg_table,
                source_column=text_col,
                source_record=record_id,
                raw_record=d,
                extraction_method="direct_parse",
                parser_version=self.parser_label,
                confidence="high",
            ))
