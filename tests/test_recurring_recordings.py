"""
Cobertura de core/recurring_recordings.py: validación y persistencia de
reglas, y su sincronización con core/recording_schedule.py (la grabación
concreta de HOY que genera cada regla).

Los detectores de solapamiento entre reglas ya tienen sus propios tests
en tests/test_recurring_conflicts.py.
"""
import json
from datetime import datetime

import pytest

from core import recording_schedule
from core import recurring_recordings as rr

LUNES = datetime(2026, 9, 21, 9, 0)  # weekday() == 0


@pytest.fixture
def profile_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(rr, "get_profile_data_dir", lambda: tmp_path)
    monkeypatch.setattr(recording_schedule, "get_profile_data_dir", lambda: tmp_path)
    return tmp_path


def _add(days=(0,), start="20:00", duration=60, name="La 1"):
    return rr.add_rule(name, "https://stream.test/la1", list(days), start, duration)


# --------------------------------------------------------------------------
# add_rule() / validación / load_rules()
# --------------------------------------------------------------------------

def test_add_rule_persists_with_sorted_unique_days(profile_dir):
    rule = _add(days=(4, 0, 4, 2))

    assert rule.days == [0, 2, 4]
    assert rr.load_rules() == [rule]
    assert len(rule.id) == 12


@pytest.mark.parametrize("kwargs", [
    {"channel_name": "  "},
    {"channel_url": ""},
    {"days": []},
    {"days": [7]},
    {"days": [True]},
    {"start_time": "24:00"},
    {"start_time": "8:00"},
    {"duration_minutes": 0},
    {"duration_minutes": rr.MAX_DURATION_MINUTES + 1},
    {"duration_minutes": 60.0},
])
def test_add_rule_rejects_invalid_values(profile_dir, kwargs):
    args = {
        "channel_name": "La 1", "channel_url": "https://x", "days": [0],
        "start_time": "20:00", "duration_minutes": 60, **kwargs,
    }
    with pytest.raises(ValueError):
        rr.add_rule(**args)
    assert rr.load_rules() == []


def test_load_rules_skips_invalid_entries(profile_dir):
    valida = {
        "id": "abc", "channel_name": "La 1", "channel_url": "https://x",
        "days": [0], "start_time": "20:00", "duration_minutes": 60, "enabled": True,
    }
    (profile_dir / rr.RULES_FILE).write_text(json.dumps([
        valida, "texto", {**valida, "id": "mala", "days": [9]}, {**valida, "raro": 1},
        {**valida, "id": "x", "enabled": "sí"},
    ]), encoding="utf-8")

    assert [r.id for r in rr.load_rules()] == ["abc"]


def test_load_rules_returns_empty_for_non_list_file(profile_dir):
    (profile_dir / rr.RULES_FILE).write_text('{"a": 1}', encoding="utf-8")
    assert rr.load_rules() == []


def test_remove_rule_and_set_enabled(profile_dir):
    a = _add(name="A")
    b = _add(name="B")

    assert [r.enabled for r in rr.set_rule_enabled(a.id, False)] == [False, True]
    with pytest.raises(ValueError):
        rr.set_rule_enabled(a.id, "no")
    assert rr.remove_rule(a.id) == [b]
    assert rr.load_rules() == [b]


# --------------------------------------------------------------------------
# sync_into_schedule()
# --------------------------------------------------------------------------

def test_sync_creates_todays_recording_once(profile_dir):
    rule = _add(days=(0,), start="23:30", duration=90)

    rr.sync_into_schedule(now=LUNES)
    rr.sync_into_schedule(now=LUNES)

    items = recording_schedule.load_scheduled()
    assert len(items) == 1
    rec = items[0]
    assert rec.tvg_id == f"recurring:{rule.id}"
    assert rec.channel_url == "https://stream.test/la1"
    assert rec.start == "20260921233000"
    assert rec.stop == "20260922010000"  # cruza la medianoche
    assert rec.status == "pending"


def test_sync_does_not_recreate_after_mark_done_same_day(profile_dir):
    _add(days=(0,))
    rr.sync_into_schedule(now=LUNES)
    rec = recording_schedule.load_scheduled()[0]

    recording_schedule.mark_done(rec.tvg_id, rec.title, rec.start)
    rr.sync_into_schedule(now=LUNES.replace(hour=22))

    assert recording_schedule.load_scheduled() == []


def test_sync_skips_other_days_and_disabled_rules(profile_dir):
    _add(days=(1, 2))
    desactivada = _add(days=(0,), name="Otra")
    rr.set_rule_enabled(desactivada.id, False)

    rr.sync_into_schedule(now=LUNES)

    assert recording_schedule.load_scheduled() == []


def test_sync_runs_again_next_matching_day(profile_dir):
    _add(days=(0, 1))

    rr.sync_into_schedule(now=LUNES)
    rr.sync_into_schedule(now=LUNES.replace(day=22))

    assert [r.start for r in recording_schedule.load_scheduled()] == [
        "20260921200000", "20260922200000",
    ]


def test_removing_rule_cancels_todays_pending_recording(profile_dir):
    """Borrar una regla después de que el timer ya creara la grabación de
    hoy no puede dejar esa grabación pendiente: arrancaría igualmente a su
    hora aunque la regla ya no exista."""
    rule = _add(days=(0,))
    otra = recording_schedule.ScheduledRecording(
        tvg_id="epg", channel_name="C", channel_url="u", title="De la EPG",
        start="20260921200000", stop="20260921210000",
    )
    recording_schedule.add_scheduled(otra)
    rr.sync_into_schedule(now=LUNES)

    rr.remove_rule(rule.id)

    assert recording_schedule.load_scheduled() == [otra]


def test_disabling_rule_cancels_todays_pending_recording(profile_dir):
    rule = _add(days=(0,))
    rr.sync_into_schedule(now=LUNES)

    rr.set_rule_enabled(rule.id, False)
    rr.sync_into_schedule(now=LUNES)

    assert recording_schedule.load_scheduled() == []


def test_reenabling_rule_same_day_schedules_it_again(profile_dir):
    rule = _add(days=(0,))
    rr.sync_into_schedule(now=LUNES)
    rr.set_rule_enabled(rule.id, False)

    rr.set_rule_enabled(rule.id, True)
    rr.sync_into_schedule(now=LUNES)

    assert [r.start for r in recording_schedule.load_scheduled()] == ["20260921200000"]


def test_disabling_rule_does_not_touch_recording_in_progress(profile_dir):
    """Si la grabación de hoy ya está en curso, desactivar la regla no la
    corta a medias ni la hace desaparecer: termina a su hora de fin."""
    rule = _add(days=(0,))
    rr.sync_into_schedule(now=LUNES)
    rec = recording_schedule.load_scheduled()[0]
    rec.status = "recording"
    recording_schedule._save([rec])

    rr.set_rule_enabled(rule.id, False)

    assert [r.status for r in recording_schedule.load_scheduled()] == ["recording"]
