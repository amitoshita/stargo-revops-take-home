"""Time zone helpers. Everything is compared in Asia/Jerusalem; offsets are never hardcoded."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

IL_TZ = ZoneInfo("Asia/Jerusalem")


def parse_aware(value: str) -> datetime:
    """Parse an ISO-8601 timestamp that must carry an offset (Z or +hh:mm)."""
    parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp has no time zone offset")
    return parsed


def to_il(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("naive datetime cannot be converted safely")
    return value.astimezone(IL_TZ)


def now_il() -> datetime:
    return datetime.now(IL_TZ)


def il_midnight(day: date) -> datetime:
    return datetime.combine(day, time(0, 0), tzinfo=IL_TZ)


def week_containing(moment: datetime) -> date:
    """Sunday (IL) that starts the reporting week containing `moment`."""
    local = to_il(moment).date()
    # Python: Monday=0 ... Sunday=6. Days since the last Sunday:
    return local - timedelta(days=(local.weekday() + 1) % 7)
