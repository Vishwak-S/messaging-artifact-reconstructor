"""Local, evidence-preserving support for common WhatsApp .crypt14 backups.

The caller supplies a key that they are authorized to use.  This module never
attempts to obtain keys from a phone, account, or operating-system keystore.
"""
from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from Crypto.Cipher import AES

SQLITE_MAGIC = b"SQLite format 3\x00"


class Crypt14Error(ValueError):
    """A supplied backup/key pair could not be verified and decrypted."""


@dataclass(frozen=True)
class Crypt14DecryptResult:
    plaintext: bytes
    layout: str


def _key_candidates(raw: bytes) -> Iterable[bytes]:
    """Accept a raw 32-byte data key or the common 158-byte key-file format."""
    values = [raw]
    try:
        text = raw.decode("ascii").strip()
        if len(text) == 64:
            values.append(bytes.fromhex(text))
        else:
            values.append(base64.b64decode(text, validate=True))
    except (UnicodeDecodeError, ValueError, binascii.Error):
        pass

    seen: set[bytes] = set()
    for value in values:
        # Common Android WhatsApp key file: AES key is the final 32 bytes.
        options = [value]
        if len(value) == 158:
            options.append(value[126:158])
        if len(value) >= 32:
            options.append(value[-32:])
        for candidate in options:
            if len(candidate) == 32 and candidate not in seen:
                seen.add(candidate)
                yield candidate


def decrypt_crypt14(backup: bytes, supplied_key: bytes) -> Crypt14DecryptResult:
    """Decrypt common AES-GCM .crypt14 layouts and verify SQLite output.

    Format details vary between WhatsApp versions, so a small set of known
    header/nonce layouts is attempted. Success is accepted only if GCM
    authentication succeeds *and* the resulting bytes are SQLite.
    """
    if len(backup) < 128:
        raise Crypt14Error("The backup is too small to be a .crypt14 database.")

    # (ciphertext start, nonce start, nonce length) for observed local backups.
    layouts = ((191, 8, 16), (191, 8, 12), (190, 8, 16), (67, 51, 16), (67, 51, 12))
    for key in _key_candidates(supplied_key):
        for payload_start, nonce_start, nonce_length in layouts:
            if len(backup) <= payload_start + 16 or len(backup) < nonce_start + nonce_length:
                continue
            nonce = backup[nonce_start:nonce_start + nonce_length]
            ciphertext, tag = backup[payload_start:-16], backup[-16:]
            try:
                plaintext = AES.new(key, AES.MODE_GCM, nonce=nonce).decrypt_and_verify(ciphertext, tag)
            except (ValueError, KeyError):
                continue
            if plaintext.startswith(SQLITE_MAGIC):
                return Crypt14DecryptResult(plaintext, f"header={payload_start}, nonce={nonce_length} bytes")
    raise Crypt14Error(
        "Decryption could not be verified. Check that this is a matching .crypt14 backup and authorized key."
    )
