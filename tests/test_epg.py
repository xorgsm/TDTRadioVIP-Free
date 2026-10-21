from datetime import datetime, timedelta, timezone

from core.epg import Programme, _parse_xmltv_time, _prepare_guide, get_now_next


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


def test_prepared_guide_sorts_and_get_now_next_reuses_parsed_dates(monkeypatch):
    now = datetime.now()
    current = Programme(
        "canal", "Ahora",
        (now - timedelta(minutes=10)).strftime("%Y%m%d%H%M%S"),
        (now + timedelta(minutes=10)).strftime("%Y%m%d%H%M%S"),
    )
    upcoming = Programme(
        "canal", "Después",
        (now + timedelta(minutes=10)).strftime("%Y%m%d%H%M%S"),
        (now + timedelta(minutes=20)).strftime("%Y%m%d%H%M%S"),
    )
    guide = {"canal": [upcoming, current]}
    _prepare_guide(guide)
    assert guide["canal"] == [current, upcoming]

    def fail_if_reparsed(_value):
        raise AssertionError("get_now_next no debe volver a parsear una guía preparada")

    monkeypatch.setattr("core.epg._parse_xmltv_time", fail_if_reparsed)
    assert get_now_next(guide, "canal") == (current, upcoming)
