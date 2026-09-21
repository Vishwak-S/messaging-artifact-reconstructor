"""
Signal SQLite artifact parser.

Signal Desktop stores data in an SQLite database.
Signal Mobile uses an encrypted SQLite DB (SQLCipher).
This parser works only with readable (unencrypted or pre-decrypted) artifacts.
"""
import uuid
from typing import Any, Dict, List, Optional

from app.forensic.detector import DetectionResult, detect_application
from app.parsers.base_parser import (
    BaseParser, CanonicalContact, CanonicalConversation,
    CanonicalMessage, ParserResult
)

VERSION = "1.0"
APPLICATION = "Signal"

SIGNAL_MSG_TYPES = {
    "incoming": "text",
    "outgoing": "text",
    "keychange": "system",
    "group-v1-migration": "system",
    "group-v2-change": "system",
    "call-history": "call",
}


def _resolve_msg_type(t: Any, direction: str = None) -> str:
    if t is None and direction:
        return SIGNAL_MSG_TYPES.get(direction, "text")
    if isinstance(t, str):
        return SIGNAL_MSG_TYPES.get(t, t)
    return "unknown"


class SignalParser(BaseParser):
    VERSION = "1.0"
    APPLICATION = "Signal"

    def detect(self) -> DetectionResult:
        return detect_application(str(self.db_path))

    def extract(self) -> ParserResult:
        result = ParserResult(
            application=APPLICATION,
            parser_version=self.parser_label,
        )

        if not self._open_readonly():
            result.errors.append(
                f"Cannot open {self.db_path.name}. "
                "If this is an encrypted Signal database, "
                "please provide a pre-decrypted artifact."
            )
            return result

        try:
            self._extract_recipients(result)
            self._extract_threads(result)
            self._extract_messages(result)
        except Exception as e:
            result.errors.append(f"Extraction error: {e}")
        finally:
            self._close()

        return result

    def _extract_recipients(self, result: ParserResult):
        if not self._has_table("recipient"):
            result.warnings.append("No 'recipient' table found.")
            return
        rows = self._safe_query('SELECT * FROM "recipient" LIMIT 5000')
        for row in rows:
            d = dict(row)
            rid = str(d.get("_id") or d.get("id") or uuid.uuid4())
            result.contacts.append(CanonicalContact(
                contact_id=rid,
                display_name=d.get("system_display_name") or d.get("profile_name"),
                phone_or_username=d.get("phone") or d.get("username") or d.get("service_id"),
                source_table="recipient",
                source_record=rid,
                raw_record=d,
            ))

    def _extract_threads(self, result: ParserResult):
        if not self._has_table("thread"):
            result.warnings.append("No 'thread' table found.")
            return
        rows = self._safe_query('SELECT * FROM "thread" LIMIT 5000')
        for row in rows:
            d = dict(row)
            tid = str(d.get("_id") or uuid.uuid4())
            is_group = bool(d.get("group_id") or d.get("is_group_v1"))
            result.conversations.append(CanonicalConversation(
                conv_id=tid,
                display_name=d.get("display_name") or str(d.get("recipient_id") or tid),
                participants=[],
                is_group=is_group,
                group_name=d.get("display_name") if is_group else None,
                application=APPLICATION,
                source_table="thread",
            ))

    def _extract_messages(self, result: ParserResult):
        # Signal Desktop uses 'messages', Android uses 'sms'/'mms'
        msg_table = None
        for candidate in ("messages", "signal_messages", "sms", "mms"):
            if self._has_table(candidate):
                msg_table = candidate
                break

        if msg_table is None:
            result.warnings.append("No recognized Signal messages table found.")
            return

        cols = self._get_columns(msg_table)
        col_set = set(cols)

        def col(name): return name if name in col_set else None

        text_col = col("body") or col("message") or col("text")
        ts_col = col("sent_at") or col("date_sent") or col("date") or col("timestamp")
        thread_col = col("thread_id") or col("conversation_id")
        type_col = col("type")
        from_col = col("from_id") or col("source") or col("source_uuid") or col("recipient_id")
        att_col = col("has_attachment") or col("attachment_count")

        rows = self._safe_query(
            f'SELECT rowid, * FROM "{msg_table}" ORDER BY {ts_col or "rowid"} ASC'
        )

        if not rows:
            result.warnings.append(f"No rows in '{msg_table}'.")
            return

        for row in rows:
            d = dict(row)
            record_id = str(d.get("_id") or d.get("rowid") or uuid.uuid4())
            raw_ts = d.get(ts_col) if ts_col else None
            ts_dt, ts_orig, tz_info = self._parse_ts(raw_ts)

            raw_type = d.get(type_col) if type_col else None
            # Signal uses numeric flags in type field for incoming/outgoing
            direction = None
            if raw_type is not None:
                try:
                    t_int = int(raw_type)
                    # Signal Desktop: 1 = outgoing, 2 = incoming
                    if t_int in (1, 87):
                        direction = "outgoing"
                    elif t_int in (2, 20):
                        direction = "incoming"
                except (ValueError, TypeError):
                    if isinstance(raw_type, str):
                        if "outgoing" in raw_type:
                            direction = "outgoing"
                        elif "incoming" in raw_type:
                            direction = "incoming"

            msg_type = _resolve_msg_type(raw_type, direction) if not direction else "text"
            conv_id = str(d.get(thread_col)) if thread_col else None

            has_att = False
            if att_col:
                val = d.get(att_col)
                has_att = bool(val) and val not in (0, "0", False)

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
                status=str(d.get("read") or d.get("status") or ""),
                evidence_status="ACTIVE",
                timestamp=ts_dt,
                timestamp_original=ts_orig,
                timezone_info=tz_info,
                has_attachment=has_att,
                source_database=self.db_filename,
                source_table=msg_table,
                source_column=text_col,
                source_record=record_id,
                raw_record=d,
                extraction_method="direct_parse",
                parser_version=self.parser_label,
                confidence="high",
            ))
