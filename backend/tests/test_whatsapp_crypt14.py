import os
import json

import pytest
from Crypto.Cipher import AES

from app.forensic.detector import detect_application
from app.forensic.whatsapp_crypt14 import Crypt14Error, decrypt_crypt14
from app.forensic.deleted_recovery import recover_deleted_from_sqlite
from app.services.evidence_service import validate_evidence_upload
from app.parsers.telegram_export_parser import TelegramExportParser


def _crypt14_fixture(key: bytes, plaintext: bytes) -> bytes:
    """Build the supported header=191 fixture; it is not used by the app."""
    header = bytearray(os.urandom(191))
    nonce = os.urandom(16)
    header[8:24] = nonce
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext)
    return bytes(header) + ciphertext + tag


def test_decrypts_verified_sqlite_with_android_key_file():
    key = os.urandom(32)
    android_key_file = os.urandom(126) + key
    plaintext = b"SQLite format 3\x00" + b"\x00" * 128
    result = decrypt_crypt14(_crypt14_fixture(key, plaintext), android_key_file)
    assert result.plaintext == plaintext


def test_rejects_wrong_key():
    backup = _crypt14_fixture(os.urandom(32), b"SQLite format 3\x00" + b"\x00" * 128)
    with pytest.raises(Crypt14Error):
        decrypt_crypt14(backup, os.urandom(32))


def test_crypt14_filename_is_detected_as_encrypted_whatsapp(tmp_path):
    backup = tmp_path / "msgstore.db.crypt14"
    backup.write_bytes(os.urandom(300))
    result = detect_application(str(backup))
    assert (result.application, result.confidence, result.is_encrypted) == ("WhatsApp", "High", True)


def test_arbitrary_binary_is_not_reported_as_encrypted_or_recovered(tmp_path):
    candidate = tmp_path / "random.winmd"
    candidate.write_bytes(os.urandom(4096))
    result = recover_deleted_from_sqlite(str(candidate))
    assert result.is_encrypted is False
    assert result.recovered_texts == []


def test_upload_validation_rejects_random_files_and_allows_sqlite_or_crypt14():
    with pytest.raises(ValueError):
        validate_evidence_upload("notes.txt", b"not a database")
    with pytest.raises(ValueError):
        validate_evidence_upload("random.db", os.urandom(300))
    validate_evidence_upload("msgstore.db", b"SQLite format 3\x00" + b"\x00" * 100)
    validate_evidence_upload("msgstore.db.crypt14", os.urandom(256))


def test_parses_official_telegram_desktop_json_export(tmp_path):
    exported = {
        "chats": {"list": [{
            "name": "Test chat", "type": "personal_chat", "id": 42,
            "messages": [{
                "id": 7, "type": "message", "date": "2026-09-21T10:00:00",
                "from": "Test user", "text": "Telegram export test",
            }],
        }]},
    }
    path = tmp_path / "result.json"
    path.write_text(json.dumps(exported), encoding="utf-8")
    validate_evidence_upload(path.name, path.read_bytes())
    result = TelegramExportParser(str(path), "CASE-1", "EV-1", "DB-1").extract()
    assert result.errors == []
    assert result.conversations[0].display_name == "Test chat"
    assert result.messages[0].message_text == "Telegram export test"
