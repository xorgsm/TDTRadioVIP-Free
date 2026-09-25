import json
from datetime import datetime, timedelta

import pytest

from core import recording_schedule as schedule
from core.epg import parse_xmltv_time


def _recording(title, start, stop, status="pending"):
    return schedule.ScheduledRecording(
        tvg_id=title,
        channel_name="Canal",
        channel_url="https://stream.test/live",
        title=title,
        start=start,
        stop=stop,
        status=status,
    )


def test_find_conflicts_detects_overlap_and_ignores_touching_intervals():
    existing = _recording("Noticias", "20260824200000", "20260824210000")

    assert schedule.find_conflicts(
        _recording("Película", "20260824203000", "20260824220000"), [existing]
    ) == [existing]
    assert schedule.find_conflicts(
        _recording("Después", "20260824210000", "20260824220000"), [existing]
    ) == []


def test_find_conflicts_ignores_failed_and_same_reservation():
    failed = _recording("Fallida", "20260824200000", "20260824210000", "error")
    same = _recording("Programa", "20260824200000", "20260824210000")

    assert schedule.find_conflicts(same, [failed, same]) == []


def test_find_conflicts_accepts_xmltv_timezone_suffix():
    existing = _recording(
        "Noticias", "20260824200000 +0200", "20260824210000 +0200"
    )
    candidate = _recording(
        "Película", "20260824203000 +0200", "20260824220000 +0200"
    )

    assert schedule.find_conflicts(candidate, [existing]) == [existing]


# --------------------------------------------------------------------------
# Persistencia y ciclo de vida (pending -> recording -> done / error)
# --------------------------------------------------------------------------

@pytest.fixture
def profile_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(schedule, "get_profile_data_dir", lambda: tmp_path)
    return tmp_path


def _xmltv(dt):
    return dt.strftime("%Y%m%d%H%M%S")


def _write_raw(profile_dir, data):
    (profile_dir / schedule.SCHEDULE_FILE).write_text(json.dumps(data), encoding="utf-8")


def test_add_scheduled_persists_and_ignores_duplicates(profile_dir):
    rec = _recording("Noticias", "20260824200000", "20260824210000")

    schedule.add_scheduled(rec)
    items = schedule.add_scheduled(_recording("Noticias", "20260824200000", "20260824210000"))

    assert items == [rec]
    assert schedule.load_scheduled() == [rec]
    assert schedule.has_scheduled("Noticias", "Noticias", "20260824200000")
    assert not schedule.has_scheduled("Noticias", "Noticias", "20260825200000")


def test_remove_scheduled_only_removes_matching_entry(profile_dir):
    a = _recording("A", "20260824200000", "20260824210000")
    b = _recording("B", "20260824200000", "20260824210000")
    schedule.add_scheduled(a)
    schedule.add_scheduled(b)

    assert schedule.remove_scheduled("A", "A", "20260824200000") == [b]
    assert schedule.load_scheduled() == [b]


def test_load_scheduled_returns_empty_for_missing_or_non_list_file(profile_dir):
    assert schedule.load_scheduled() == []
    _write_raw(profile_dir, {"no": "es una lista"})
    assert schedule.load_scheduled() == []


def test_load_scheduled_skips_malformed_entries(profile_dir):
    valida = {
        "tvg_id": "t", "channel_name": "C", "channel_url": "u", "title": "T",
        "start": "20260824200000", "stop": "20260824210000", "status": "pending",
    }
    _write_raw(profile_dir, [
        valida,
        "no es un dict",
        {"tvg_id": "t"},                                            # faltan campos
        {**valida, "extra": 1},                                     # campo desconocido
        {**valida, "title": "Numérica", "start": 20260824200000},   # tipo incorrecto
        {**valida, "title": "Estado raro", "status": "???"},
        {**valida, "title": "Nula", "stop": None},
    ])

    cargadas = schedule.load_scheduled()

    assert [r.title for r in cargadas] == ["T"]


def test_corrupt_field_types_do_not_break_the_periodic_checks(profile_dir):
    """Un archivo editado a mano (o corrupto) con una hora numérica no puede
    hacer que check_starts_due/check_stops_due revienten en cada tick del
    timer: eso bloquearía TODAS las grabaciones programadas."""
    base = {"tvg_id": "t", "channel_name": "C", "channel_url": "u", "title": "T"}
    _write_raw(profile_dir, [
        {**base, "start": 20260824200000, "stop": "20260824210000", "status": "pending"},
        {**base, "start": "20260824200000", "stop": 1, "status": "recording"},
    ])

    assert schedule.check_starts_due(parse_xmltv_time) == []
    assert schedule.check_stops_due(parse_xmltv_time) == []


def test_check_starts_due_starts_due_entries_and_expires_late_ones(profile_dir):
    ahora = datetime.now()
    toca = _recording("Toca", _xmltv(ahora - timedelta(minutes=1)), _xmltv(ahora + timedelta(hours=1)))
    futura = _recording("Futura", _xmltv(ahora + timedelta(hours=1)), _xmltv(ahora + timedelta(hours=2)))
    tarde = _recording("Tarde", _xmltv(ahora - timedelta(minutes=30)), _xmltv(ahora + timedelta(hours=1)))
    corrupta = _recording("Corrupta", "no-es-hora", _xmltv(ahora + timedelta(hours=1)))
    grabando = _recording("Grabando", _xmltv(ahora - timedelta(minutes=1)),
                          _xmltv(ahora + timedelta(hours=1)), status="recording")
    for rec in (toca, futura, tarde, corrupta, grabando):
        schedule.add_scheduled(rec)

    listas = schedule.check_starts_due(parse_xmltv_time)

    assert [r.title for r in listas] == ["Toca"]
    estados = {r.title: r.status for r in schedule.load_scheduled()}
    assert estados == {
        "Toca": "recording", "Futura": "pending", "Tarde": "error",
        "Corrupta": "error", "Grabando": "recording",
    }
    # Segunda pasada: ya no se devuelve la misma otra vez.
    assert schedule.check_starts_due(parse_xmltv_time) == []


def test_check_stops_due_returns_finished_and_corrupt_recordings(profile_dir):
    ahora = datetime.now()
    inicio = _xmltv(ahora - timedelta(hours=1))
    terminada = _recording("Terminada", inicio, _xmltv(ahora - timedelta(seconds=1)), "recording")
    en_curso = _recording("EnCurso", inicio, _xmltv(ahora + timedelta(hours=1)), "recording")
    sin_fin = _recording("SinFin", inicio, "corrupta", "recording")
    pendiente = _recording("Pendiente", inicio, _xmltv(ahora - timedelta(seconds=1)))
    for rec in (terminada, en_curso, sin_fin, pendiente):
        schedule.add_scheduled(rec)

    assert [r.title for r in schedule.check_stops_due(parse_xmltv_time)] == ["Terminada", "SinFin"]


def test_mark_done_removes_and_mark_error_keeps_entry_visible(profile_dir):
    a = _recording("A", "20260824200000", "20260824210000", "recording")
    b = _recording("B", "20260824200000", "20260824210000", "recording")
    schedule.add_scheduled(a)
    schedule.add_scheduled(b)

    schedule.mark_done("A", "A", "20260824200000")
    schedule.mark_error("B", "B", "20260824200000")

    assert [(r.title, r.status) for r in schedule.load_scheduled()] == [("B", "error")]


def test_find_conflicts_reads_from_disk_and_ignores_invalid_intervals(profile_dir):
    existente = _recording("Noticias", "20260824200000", "20260824210000")
    schedule.add_scheduled(existente)
    schedule.add_scheduled(_recording("Rota", "corrupta", "20260824210000"))

    assert schedule.find_conflicts(
        _recording("Película", "20260824203000", "20260824220000")
    ) == [existente]
    assert schedule.find_conflicts(
        _recording("Al revés", "20260824220000", "20260824200000")
    ) == []
