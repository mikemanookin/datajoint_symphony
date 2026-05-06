""".NET ``DateTimeOffset`` ↔ Python ``datetime`` conversions.

Symphony stores every timestamp as a pair of attributes:
``...DotNetDateTimeOffsetTicks`` (int64, 100-ns intervals since
0001-01-01 UTC) and ``...DotNetDateTimeOffsetOffsetHours`` (float, UTC
offset in hours, e.g. -5.0 for EST).

These helpers convert in both directions and parse the string format
(``MM/DD/YYYY HH:MM:SS:ffffff``) used by the legacy parse_data.py.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Union


# 0001-01-01T00:00:00 UTC — the .NET tick epoch.
DOTNET_EPOCH = datetime(1, 1, 1, tzinfo=timezone.utc)
# 1 tick = 100 ns
TICKS_PER_SECOND = 10_000_000
TICKS_PER_MICROSECOND = 10


def ticks_to_datetime(
    ticks: Union[int, float],
    offset_hours: float = 0.0,
) -> datetime:
    """Convert .NET ticks (+ offset hours) to a tz-aware ``datetime``.

    The returned datetime is in the *local* offset implied by
    ``offset_hours`` (so its wall-clock matches what the recording rig
    saw), not UTC.
    """
    micros = int(ticks) // TICKS_PER_MICROSECOND
    utc = DOTNET_EPOCH + timedelta(microseconds=micros)
    if offset_hours == 0.0:
        return utc
    tz = timezone(timedelta(hours=offset_hours))
    return utc.astimezone(tz)


def datetime_to_ticks(dt: datetime) -> int:
    """Convert a tz-aware ``datetime`` to .NET ticks.

    Naive datetimes are treated as UTC.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = dt.astimezone(timezone.utc) - DOTNET_EPOCH
    return int(round(delta.total_seconds() * TICKS_PER_SECOND))


def parse_legacy_string(s: Optional[str]) -> Optional[datetime]:
    """Parse the legacy ``MM/DD/YYYY HH:MM:SS:ffffff`` format used by
    parse_data.py's ``dotnet_ticks_to_datetime`` first return value.

    Returns ``None`` for ``None``/empty input.
    """
    if not s:
        return None
    return datetime.strptime(s, "%m/%d/%Y %H:%M:%S:%f")


def parse_iso(s: Optional[str]) -> Optional[datetime]:
    """Parse an ISO 8601 string from the DJ JSON's per-epoch convenience
    fields (``datetime``, ``start_time``, ``end_time``)."""
    if not s:
        return None
    # datetime.fromisoformat handles offsets in 3.11+; on earlier versions it
    # accepts naive only.
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        # Fall back to the legacy-string format if needed.
        return parse_legacy_string(s)


def split_dotnet_pair(
    record: dict, base_key: str
) -> Tuple[Optional[datetime], Optional[float]]:
    """Read a ``<base_key>DotNetDateTimeOffsetTicks`` /
    ``<base_key>DotNetDateTimeOffsetOffsetHours`` pair from a dict and
    return (datetime, offset_hours)."""
    ticks_key = f"{base_key}DotNetDateTimeOffsetTicks"
    offset_key = f"{base_key}DotNetDateTimeOffsetOffsetHours"
    ticks = record.get(ticks_key)
    if ticks is None:
        return None, None
    offset = float(record.get(offset_key, 0.0) or 0.0)
    return ticks_to_datetime(ticks, offset), offset
