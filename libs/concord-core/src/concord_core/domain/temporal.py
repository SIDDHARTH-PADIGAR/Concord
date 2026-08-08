"""Timezone validation shared across domain entities."""

from datetime import datetime, timedelta


def require_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware, got naive datetime")
    if value.utcoffset() != timedelta(0):
        raise ValueError(f"timestamp must be UTC, got offset {value.utcoffset()}")
    return value
