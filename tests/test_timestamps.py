"""Unit tests for ``symphony_dj.timestamps``."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

import pytest

from symphony_dj.timestamps import (
    DOTNET_EPOCH,
    datetime_to_ticks,
    parse_iso,
    parse_legacy_string,
    split_dotnet_pair,
    ticks_to_datetime,
)


def test_dotnet_epoch_is_unix_ad1():
    assert DOTNET_EPOCH == datetime(1, 1, 1, tzinfo=timezone.utc)


def test_round_trip_zero():
    dt = ticks_to_datetime(0, 0.0)
    assert dt == DOTNET_EPOCH
    assert datetime_to_ticks(dt) == 0


def test_round_trip_arbitrary():
    # 2026-04-10T09:00:00 UTC → ticks → datetime
    target = datetime(2026, 4, 10, 9, 0, 0, tzinfo=timezone.utc)
    ticks = datetime_to_ticks(target)
    back = ticks_to_datetime(ticks, 0.0)
    assert back == target


def test_offset_hours_preserved_in_wallclock():
    target = datetime(2026, 4, 10, 9, 0, 0, tzinfo=timezone.utc)
    ticks = datetime_to_ticks(target)
    # As displayed in Pacific time:
    pst = ticks_to_datetime(ticks, -7.0)
    assert pst.tzinfo is not None
    assert pst.utcoffset() == timedelta(hours=-7)
    # Same instant, different wall-clock representation.
    assert pst.astimezone(timezone.utc) == target


def test_parse_legacy_string():
    dt = parse_legacy_string("04/10/2026 09:00:00:000000")
    assert dt == datetime(2026, 4, 10, 9, 0, 0)


def test_parse_legacy_string_none():
    assert parse_legacy_string(None) is None
    assert parse_legacy_string("") is None


def test_parse_iso():
    dt = parse_iso("2026-04-10T09:00:00-07:00")
    assert dt is not None
    assert dt.utcoffset() == timedelta(hours=-7)


def test_split_dotnet_pair_present():
    record = {
        "fooDotNetDateTimeOffsetTicks": 638790336000000000,
        "fooDotNetDateTimeOffsetOffsetHours": -7.0,
    }
    dt, off = split_dotnet_pair(record, "foo")
    assert dt is not None
    assert off == -7.0


def test_split_dotnet_pair_missing():
    record = {}
    dt, off = split_dotnet_pair(record, "foo")
    assert dt is None
    assert off is None
