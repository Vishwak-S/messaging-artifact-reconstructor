"""SHA-256 hashing utilities for forensic evidence integrity."""
import hashlib
from pathlib import Path


CHUNK_SIZE = 65536  # 64 KB chunks for large file support


def sha256_file(file_path: str | Path) -> str:
    """Calculate SHA-256 hash of a file without loading it entirely into memory."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    """Calculate SHA-256 hash of raw bytes."""
    return hashlib.sha256(data).hexdigest()


def verify_file_hash(file_path: str | Path, expected_hash: str) -> bool:
    """
    Verify a file against its expected SHA-256 hash.
    Returns True if the file's current hash matches the expected hash.
    """
    current = sha256_file(file_path)
    return current.lower() == expected_hash.lower()
