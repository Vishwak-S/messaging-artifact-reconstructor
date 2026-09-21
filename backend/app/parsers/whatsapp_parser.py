"""
WhatsApp SQLite artifact parser.

Dynamically inspects the available schema — WhatsApp DB versions vary.
Does not assume a single fixed schema.
Preserves all provenance information.
"""
import uuid
from typing import Any, Dict, List, Optional

from app.forensic.detector import DetectionResult, detect_application
from app.parsers.base_parser import (
    BaseParser, CanonicalContact, CanonicalConversation,
    CanonicalMessage, ParserResult
)

VERSION = "1.0"
APPLICATION = "WhatsApp"

# Known WhatsApp message type mappings (type integer → label)
WA_MSG_TYPES = {
    0: "text",
    1: "image",
    2: "audio",
    3: "video",
    4: "contact",
    5: "location",
    6: "system",
    7: "video_call",
    8: "audio_call",
    9: "document",
    10: "sticker",
    11: "gif",
    13: "sticker",
    14: "deleted",
    15: "product",
    20: "voice_message",
}


def _resolve_msg_type(type_val: Any) -> str:
    if type_val is None:
        return "unknown"
    try:
        return WA_MSG_TYPES.get(int(type_val), f"type_{type_val}")
    except (ValueError, TypeError):
        return str(type_val)


class WhatsAppParser(BaseParser):
    VERSION = "1.0"
    APPLICATION = "WhatsApp"

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
            self._extract_contacts(result)
            self._extract_conversations(result)
            self._extract_messages(result)
        except Exception as e:
            result.errors.append(f"Extraction error: {e}")
        finally:
            self._close()

        return result

    # ── Contacts ──────────────────────────────────────────────────────────────

    def _extract_contacts(self, result: ParserResult):
        # Try 'jid' table (newer WhatsApp)
        if self._has_table("jid"):
            cols = self._get_columns("jid")
            rows = self._safe_query('SELECT * FROM "jid" LIMIT 5000')
            for row in rows:
                d = dict(row)
                cid = str(d.get("_id") or d.get("user") or uuid.uuid4())
                result.contacts.append(CanonicalContact(
                    contact_id=cid,
                    display_name=d.get("display_name") or d.get("name"),
                    phone_or_username=d.get("user") or d.get("raw_string"),
                    source_table="jid",
                    source_record=cid,
                    raw_record=d,
                ))
        # Try 'wa_contacts' table (older WhatsApp)
        elif self._has_table("wa_contacts"):
            rows = self._safe_query('SELECT * FROM "wa_contacts" LIMIT 5000')
            for row in rows:
                d = dict(row)
                cid = str(d.get("jid") or d.get("_id") or uuid.uuid4())
                result.contacts.append(CanonicalContact(
                    contact_id=cid,
                    display_name=d.get("display_name") or d.get("wa_name"),
                    phone_or_username=d.get("jid") or d.get("number"),
                    source_table="wa_contacts",
                    source_record=cid,
                    raw_record=d,
                ))

    # ── Conversations ─────────────────────────────────────────────────────────

    def _extract_conversations(self, result: ParserResult):
        if self._has_table("chat"):
            cols = self._get_columns("chat")
            rows = self._safe_query('SELECT * FROM "chat" LIMIT 5000')
            for row in rows:
                d = dict(row)
                conv_id = str(d.get("jid_row_id") or d.get("_id") or uuid.uuid4())
                is_group = "@g.us" in str(d.get("jid") or "")
                result.conversations.append(CanonicalConversation(
                    conv_id=conv_id,
                    display_name=d.get("subject") or d.get("display_name") or d.get("jid"),
                    participants=[],
                    is_group=is_group,
                    group_name=d.get("subject") if is_group else None,
                    application=APPLICATION,
                    source_table="chat",
                ))

    # ── Messages ──────────────────────────────────────────────────────────────

    def _extract_messages(self, result: ParserResult):
        # Determine which message table is available
        msg_table = None
        for candidate in ("message", "messages", "wa_message"):
            if self._has_table(candidate):
                msg_table = candidate
                break

        if msg_table is None:
            result.warnings.append(
                "No recognized message table found (tried: message, messages, wa_message)."
            )
            return

        cols = self._get_columns(msg_table)
        col_set = set(cols)

        # Dynamic column mapping — gracefully handle missing fields
        def col(name): return name if name in col_set else None

        text_col = col("data") or col("body") or col("text") or col("message")
        ts_col = col("timestamp") or col("date") or col("date_sent")
        sender_col = col("sender_jid_row_id") or col("from_me") or col("sender")
        type_col = col("type") or col("message_type")
        status_col = col("status") or col("read_device_timestamp")
        media_col = col("media_name") or col("file_path") or col("media_url")
        chat_col = col("chat_row_id") or col("chat_id") or col("key_remote_jid")
        key_col = col("_id") or col("rowid") or "rowid"

        rows = self._safe_query(f'SELECT rowid, * FROM "{msg_table}" ORDER BY {ts_col or "rowid"} ASC')

        if not rows:
            result.warnings.append(f"No rows found in table '{msg_table}'.")
            return

        known_convs = {c.conv_id for c in result.conversations}

        for row in rows:
            d = dict(row)
            record_id = str(d.get("_id") or d.get("rowid") or uuid.uuid4())

            # Timestamps
            raw_ts = d.get(ts_col) if ts_col else None
            ts_dt, ts_orig, tz_info = self._parse_ts(raw_ts)

            # Message type
            msg_type = _resolve_msg_type(d.get(type_col) if type_col else None)

            # Direction
            from_me = d.get("from_me")
            if from_me is not None:
                direction = "outgoing" if int(from_me) == 1 else "incoming"
            else:
                direction = None

            # Attachment
            att_name = d.get(media_col) if media_col else None
            has_att = att_name is not None and att_name != ""

            # Conversation
            conv_id = str(d.get(chat_col)) if chat_col else None

            # Evidence status
            ev_status = "ACTIVE"
            if msg_type == "deleted":
                ev_status = "DELETED"

            result.messages.append(CanonicalMessage(
                message_id=record_id,
                conv_id=conv_id,
                case_id=self.case_id,
                evidence_id=self.evidence_id,
                db_id=self.db_id,
                application=APPLICATION,
                sender=str(d.get("sender_jid_row_id") or d.get("sender") or ""),
                recipient=str(d.get("key_remote_jid") or ""),
                message_text=d.get(text_col) if text_col else None,
                message_type=msg_type,
                direction=direction,
                status=str(d.get(status_col)) if status_col and d.get(status_col) is not None else None,
                evidence_status=ev_status,
                timestamp=ts_dt,
                timestamp_original=ts_orig,
                timezone_info=tz_info,
                has_attachment=has_att,
                attachment_name=att_name,
                source_database=self.db_filename,
                source_table=msg_table,
                source_column=text_col,
                source_record=record_id,
                raw_record=d,
                extraction_method="direct_parse",
                parser_version=self.parser_label,
                confidence="high",
            ))
