from datetime import datetime, timedelta, timezone

from core.epg import _parse_xmltv_time


def test_parse_without_timezone_is_treated_as_local():
    assert _parse_xmltv_time("20260824193000") == datetime(2026, 8, 24, 19, 30, 0)


def test_parse_with_utc_offset_converts_to_local_time():
    value = "20260824193000 +0200"
    parsed = _parse_xmltv_time(value)

    expected_utc = datetime(2026, 8, 24, 19, 30, 0, tzinfo=timezone(timedelta(hours=2)))
    expected_local = expected_utc.astimezone().replace(tzinfo=None)
    assert parsed == expected_local


def test_parse_with_z_suffix_is_treated_as_utc():
    parsed = _parse_xmltv_time("20260824193000 Z")

    expected_utc = datetime(2026, 8, 24, 19, 30, 0, tzinfo=timezone.utc)
    expected_local = expected_utc.astimezone().replace(tzinfo=None)
    assert parsed == expected_local


def test_parse_invalid_value_returns_none():
    assert _parse_xmltv_time("not-a-date") is None
    assert _parse_xmltv_time("") is None
