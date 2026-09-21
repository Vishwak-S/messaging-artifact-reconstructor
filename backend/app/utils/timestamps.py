"""
Timestamp conversion utilities for forensic messaging analysis.

Messaging applications use a variety of timestamp formats.
Every conversion preserves the original raw value.
"""
from datetime import datetime, timezone
from typing import Optional, Tuple


# Common epoch offsets used by messaging apps
UNIX_EPOCH_SECONDS = 1_000_000_000        # 10-digit epoch
UNIX_EPOCH_MILLISECONDS = 1_000_000_000_000  # 13-digit epoch
UNIX_EPOCH_MICROSECONDS = 1_000_000_000_000_000  # 16-digit epoch

# WhatsApp often stores timestamps as milliseconds since Unix epoch
# Signal also uses milliseconds
# Telegram uses seconds since Unix epoch


def _classify_epoch(value: int) -> str:
    """Guess timestamp unit based on magnitude."""
    if value >= UNIX_EPOCH_MICROSECONDS:
        return "microseconds"
    elif value >= UNIX_EPOCH_MILLISECONDS:
        return "milliseconds"
    elif value >= UNIX_EPOCH_SECONDS:
        return "seconds"
    else:
        return "unknown"


def parse_timestamp(
    raw_value: any,
) -> Tuple[Optional[datetime], Optional[str], str]:
    """
    Convert a raw timestamp to a UTC datetime.

    Returns
    -------
    (interpreted_datetime, timezone_label, conversion_method)

    If conversion fails, returns (None, None, 'unsupported').
    The original raw_value is NEVER discarded by this function.
    """
    if raw_value is None:
        return None, None, "null_value"

    # Already an ISO string
    if isinstance(raw_value, str):
        for fmt in (
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
        ):
            try:
                dt = datetime.strptime(raw_value, fmt)
                return dt.replace(tzinfo=timezone.utc), "UTC (assumed)", f"string_parse:{fmt}"
            except ValueError:
                continue
        return None, None, "unsupported_string_format"

    # Numeric epoch
    try:
        numeric = int(raw_value)
    except (ValueError, TypeError):
        return None, None, "non_numeric"

    if numeric <= 0:
        return None, None, "non_positive_epoch"

    unit = _classify_epoch(numeric)
    try:
        if unit == "milliseconds":
            dt = datetime.fromtimestamp(numeric / 1000, tz=timezone.utc)
            method = "epoch_milliseconds"
        elif unit == "microseconds":
            dt = datetime.fromtimestamp(numeric / 1_000_000, tz=timezone.utc)
            method = "epoch_microseconds"
        elif unit == "seconds":
            dt = datetime.fromtimestamp(numeric, tz=timezone.utc)
            method = "epoch_seconds"
        else:
            return None, None, "unrecognized_epoch_magnitude"

        return dt, "UTC", method
    except (OSError, OverflowError, ValueError):
        return None, None, "epoch_out_of_range"


def format_for_display(dt: Optional[datetime]) -> str:
    """Return a human-readable forensic timestamp string."""
    if dt is None:
        return "Unknown"
    return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
