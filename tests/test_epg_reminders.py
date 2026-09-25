"""
Cobertura de core/epg_reminders.py: persistencia de avisos "empieza
ahora" de la EPG y su disparo único con margen de tolerancia.
"""
import json
from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest

from core import epg_reminders
from core.epg import parse_xmltv_time
from core.epg_reminders import Reminder


@pytest.fixture
def profile_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(epg_reminders, "get_profile_data_dir", lambda: tmp_path)
    return tmp_path


def _reminder(title, start):
    return Reminder(tvg_id="la1", channel_name="La 1", title=title, start=start)


def _xmltv(dt):
    return dt.strftime("%Y%m%d%H%M%S")


def _write_raw(profile_dir, data):
    (profile_dir / epg_reminders.REMINDERS_FILE).write_text(json.dumps(data), encoding="utf-8")


def test_add_reminder_persists_and_ignores_duplicates(profile_dir):
    aviso = _reminder("Telediario", "20260924210000")

    epg_reminders.add_reminder(aviso)
    epg_reminders.add_reminder(_reminder("Telediario", "20260924210000"))

    assert epg_reminders.load_reminders() == [aviso]
    assert epg_reminders.has_reminder("la1", "Telediario", "20260924210000")
    assert not epg_reminders.has_reminder("la2", "Telediario", "20260924210000")


def test_remove_reminder_only_removes_matching(profile_dir):
    a = _reminder("A", "20260924210000")
    b = _reminder("B", "20260924210000")
    epg_reminders.add_reminder(a)
    epg_reminders.add_reminder(b)

    assert epg_reminders.remove_reminder("la1", "A", "20260924210000") == [b]
    assert epg_reminders.load_reminders() == [b]


def test_load_reminders_returns_empty_for_missing_or_non_list_file(profile_dir):
    assert epg_reminders.load_reminders() == []
    _write_raw(profile_dir, {"a": 1})
    assert epg_reminders.load_reminders() == []


def test_load_reminders_skips_malformed_entries(profile_dir):
    valido = {"tvg_id": "la1", "channel_name": "La 1", "title": "T", "start": "20260924210000"}
    _write_raw(profile_dir, [
        valido,
        "texto",
        {"tvg_id": "la1"},
        {**valido, "extra": True},
        {**valido, "title": "Numérico", "start": 20260924210000},
        {**valido, "title": None},
    ])

    assert [r.title for r in epg_reminders.load_reminders()] == ["T"]


def test_corrupt_start_type_does_not_break_check_due(profile_dir):
    """Una hora numérica (archivo editado a mano o dañado) no puede hacer
    que check_due reviente en cada tick del timer de avisos."""
    _write_raw(profile_dir, [
        {"tvg_id": "la1", "channel_name": "La 1", "title": "T", "start": 20260924210000},
    ])

    assert epg_reminders.check_due(parse_xmltv_time) == []


def test_check_due_fires_once_keeps_future_and_drops_stale(profile_dir):
    ahora = datetime.now()
    toca = _reminder("Toca", _xmltv(ahora - timedelta(minutes=1)))
    futuro = _reminder("Futuro", _xmltv(ahora + timedelta(hours=1)))
    pasado = _reminder("Pasado", _xmltv(ahora - timedelta(hours=1)))
    corrupto = _reminder("Corrupto", "no-es-hora")
    for aviso in (toca, futuro, pasado, corrupto):
        epg_reminders.add_reminder(aviso)

    assert epg_reminders.check_due(parse_xmltv_time) == [toca]
    assert epg_reminders.load_reminders() == [futuro]
    assert epg_reminders.check_due(parse_xmltv_time) == []


def test_check_due_does_not_rewrite_file_when_nothing_changes(profile_dir, monkeypatch):
    epg_reminders.add_reminder(_reminder("Futuro", _xmltv(datetime.now() + timedelta(hours=1))))
    save = Mock()
    monkeypatch.setattr(epg_reminders, "_save", save)

    epg_reminders.check_due(parse_xmltv_time)

    save.assert_not_called()
