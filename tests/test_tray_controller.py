"""
Cobertura de ui/tray_controller.py: avisos EPG y arranque/parada real de
grabaciones programadas -- el único sitio que toca win.recorder por una
programación (ver core/recording_schedule.py).

Se usa una ventana simulada (SimpleNamespace + Mock) en vez de MainWindow:
lo que se prueba es la coordinación entre la programación en disco, el
Recorder y los avisos, no los widgets. core.recording_schedule y
core.epg_reminders escriben de verdad en un tmp_path.
"""
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core import epg_reminders, recording_schedule, recurring_recordings
from ui import tray_controller
from ui.tray_controller import TrayReminderController


def _xmltv(dt):
    return dt.strftime("%Y%m%d%H%M%S")


@pytest.fixture
def profile_dir(tmp_path, monkeypatch):
    for modulo in (recording_schedule, recurring_recordings, epg_reminders):
        monkeypatch.setattr(modulo, "get_profile_data_dir", lambda: tmp_path)
    return tmp_path


@pytest.fixture
def qt_stubs(monkeypatch):
    """QTimer.singleShot y make_glow no hacen falta de verdad aquí."""
    timer = Mock()
    monkeypatch.setattr(tray_controller, "QTimer", timer)
    monkeypatch.setattr(tray_controller, "make_glow", Mock(return_value="glow"), raising=False)
    monkeypatch.setattr(tray_controller.rec_module.Recorder, "ffmpeg_available", staticmethod(lambda: True))
    return timer


@pytest.fixture
def win(profile_dir, qt_stubs):
    recorder = Mock(is_recording=False, current_file=None)
    recorder.start.return_value = "C:/grab/la1.mp4"
    recorder.stop.return_value = ("C:/grab/la1.mp4", True)
    status = Mock()
    return SimpleNamespace(
        _is_closing=False,
        _tray_icon=Mock(),
        _pending_reminder_tune=None,
        _scheduled_recording_active=None,
        recorder=recorder,
        record_btn=Mock(),
        _make_glow=Mock(return_value="glow"),  # interfaz de la edición Free
        statusBar=Mock(return_value=status),
        epg=Mock(),
        showNormal=Mock(), raise_=Mock(), activateWindow=Mock(),
    )


def _schedule(title, start, stop, status="pending"):
    rec = recording_schedule.ScheduledRecording(
        tvg_id=f"id-{title}", channel_name="La 1", channel_url="https://stream.test/la1",
        title=title, start=_xmltv(start), stop=_xmltv(stop), status=status,
    )
    recording_schedule.add_scheduled(rec)
    return rec


def _statuses():
    return {r.title: r.status for r in recording_schedule.load_scheduled()}


# --------------------------------------------------------------------------
# Avisos EPG
# --------------------------------------------------------------------------

def test_due_reminder_shows_tray_message_and_remembers_channel(win):
    epg_reminders.add_reminder(epg_reminders.Reminder(
        tvg_id="La1.es", channel_name="La 1", title="Telediario",
        start=_xmltv(datetime.now() - timedelta(minutes=1)),
    ))

    TrayReminderController(win).check_epg_reminders()

    assert win._tray_icon.showMessage.call_args.args[:2] == ("Empieza ahora", "Telediario — La 1")
    assert win._pending_reminder_tune == "La1.es"


def test_clicking_tray_message_tunes_pending_channel_once(win):
    ctrl = TrayReminderController(win)
    win._pending_reminder_tune = "La1.es"

    ctrl.on_tray_message_clicked()
    ctrl.on_tray_message_clicked()

    win.epg.tune_to_tvg_id.assert_called_once_with("La1.es")
    assert win._pending_reminder_tune is None
    win.showNormal.assert_called_once()


def test_nothing_runs_while_window_is_closing(win):
    win._is_closing = True
    ahora = datetime.now()
    _schedule("Noticias", ahora - timedelta(minutes=1), ahora + timedelta(hours=1))
    ctrl = TrayReminderController(win)

    ctrl.check_epg_reminders()
    ctrl.check_scheduled_recordings()

    win.recorder.start.assert_not_called()
    assert _statuses() == {"Noticias": "pending"}


def test_notify_without_tray_icon_does_nothing(win):
    win._tray_icon = None
    TrayReminderController(win).notify("t", "m")  # no revienta


# --------------------------------------------------------------------------
# Arranque de grabaciones programadas
# --------------------------------------------------------------------------

def test_due_recording_starts_recorder_and_schedules_alive_check(win, qt_stubs):
    ahora = datetime.now()
    _schedule("Noticias", ahora - timedelta(minutes=1), ahora + timedelta(hours=1))

    TrayReminderController(win).check_scheduled_recordings()

    win.recorder.start.assert_called_once_with("https://stream.test/la1", "La 1")
    assert win._scheduled_recording_active.title == "Noticias"
    win.record_btn.setChecked.assert_called_with(True)
    assert _statuses() == {"Noticias": "recording"}
    qt_stubs.singleShot.assert_called_once()


def test_due_recording_is_marked_error_when_another_is_already_recording(win):
    win.recorder.is_recording = True
    ahora = datetime.now()
    _schedule("Noticias", ahora - timedelta(minutes=1), ahora + timedelta(hours=1))

    TrayReminderController(win).check_scheduled_recordings()

    win.recorder.start.assert_not_called()
    assert _statuses() == {"Noticias": "error"}
    assert "no iniciada" in win._tray_icon.showMessage.call_args.args[0]


def test_due_recording_is_marked_error_without_ffmpeg(win, monkeypatch):
    monkeypatch.setattr(tray_controller.rec_module.Recorder, "ffmpeg_available", staticmethod(lambda: False))
    ahora = datetime.now()
    _schedule("Noticias", ahora - timedelta(minutes=1), ahora + timedelta(hours=1))

    TrayReminderController(win).check_scheduled_recordings()

    win.recorder.start.assert_not_called()
    assert _statuses() == {"Noticias": "error"}


def test_recorder_start_failure_marks_error_and_warns(win):
    win.recorder.start.side_effect = RuntimeError("ffmpeg no arranca")
    ahora = datetime.now()
    _schedule("Noticias", ahora - timedelta(minutes=1), ahora + timedelta(hours=1))

    TrayReminderController(win).check_scheduled_recordings()

    assert _statuses() == {"Noticias": "error"}
    assert win._scheduled_recording_active is None


def test_only_one_of_two_simultaneous_recordings_starts(win):
    ahora = datetime.now()
    _schedule("A", ahora - timedelta(minutes=1), ahora + timedelta(hours=1))
    _schedule("B", ahora - timedelta(minutes=1), ahora + timedelta(hours=1))

    def start(url, name):
        win.recorder.is_recording = True
        return "C:/grab/a.mp4"
    win.recorder.start.side_effect = start

    TrayReminderController(win).check_scheduled_recordings()

    assert win.recorder.start.call_count == 1
    assert sorted(_statuses().values()) == ["error", "recording"]


def test_recurring_rule_for_today_is_synced_and_started(win, monkeypatch):
    ahora = datetime.now()
    recurring_recordings.add_rule(
        "La 1", "https://stream.test/la1", [ahora.weekday()],
        (ahora - timedelta(minutes=1)).strftime("%H:%M"), 60,
    )
    if (ahora - timedelta(minutes=1)).date() != ahora.date():
        pytest.skip("justo al cruzar la medianoche")

    TrayReminderController(win).check_scheduled_recordings()

    win.recorder.start.assert_called_once()
    assert list(_statuses().values()) == ["recording"]


# --------------------------------------------------------------------------
# Comprobación tardía de que la grabación arrancó de verdad
# --------------------------------------------------------------------------

def test_alive_check_marks_error_when_ffmpeg_died_at_startup(win):
    ahora = datetime.now()
    rec = _schedule("Noticias", ahora - timedelta(minutes=1), ahora + timedelta(hours=1), "recording")
    win.recorder.is_recording = True
    win.recorder.current_file = "C:/grab/la1.mp4"
    win.recorder.check_early_failure.return_value = "ffmpeg se cerró"
    win._scheduled_recording_active = rec

    TrayReminderController(win).check_scheduled_recording_alive("C:/grab/la1.mp4", rec)

    assert _statuses() == {"Noticias": "error"}
    assert win._scheduled_recording_active is None
    win.record_btn.setChecked.assert_called_with(False)


def test_alive_check_ignores_a_different_or_stopped_recording(win):
    ahora = datetime.now()
    rec = _schedule("Noticias", ahora - timedelta(minutes=1), ahora + timedelta(hours=1), "recording")
    win.recorder.is_recording = True
    win.recorder.current_file = "C:/grab/otra.mp4"

    TrayReminderController(win).check_scheduled_recording_alive("C:/grab/la1.mp4", rec)

    win.recorder.check_early_failure.assert_not_called()
    assert _statuses() == {"Noticias": "recording"}


# --------------------------------------------------------------------------
# Parada de grabaciones programadas
# --------------------------------------------------------------------------

def test_finished_active_recording_is_stopped_saved_and_removed(win):
    ahora = datetime.now()
    rec = _schedule("Noticias", ahora - timedelta(hours=1), ahora - timedelta(seconds=1), "recording")
    win._scheduled_recording_active = rec
    win.recorder.is_recording = True

    TrayReminderController(win).check_scheduled_recordings()

    win.recorder.stop.assert_called_once()
    assert win._scheduled_recording_active is None
    assert _statuses() == {}
    assert "«Noticias» guardado." in win._tray_icon.showMessage.call_args.args[1]


def test_finished_recording_not_active_is_only_cleaned_up(win):
    ahora = datetime.now()
    _schedule("Noticias", ahora - timedelta(hours=1), ahora - timedelta(seconds=1), "recording")
    win.recorder.is_recording = True  # es otra grabación (manual)

    TrayReminderController(win).check_scheduled_recordings()

    win.recorder.stop.assert_not_called()
    assert _statuses() == {}


def test_empty_recording_is_reported(win):
    ahora = datetime.now()
    rec = _schedule("Noticias", ahora - timedelta(hours=1), ahora - timedelta(seconds=1), "recording")
    win._scheduled_recording_active = rec
    win.recorder.is_recording = True
    win.recorder.stop.return_value = (None, False)

    TrayReminderController(win).check_scheduled_recordings()

    assert "quedó vacía" in win._tray_icon.showMessage.call_args.args[1]


def test_window_closing_during_stop_cleans_up_and_starts_nothing_else(win):
    ahora = datetime.now()
    rec = _schedule("Fin", ahora - timedelta(hours=1), ahora - timedelta(seconds=1), "recording")
    _schedule("Siguiente", ahora - timedelta(minutes=1), ahora + timedelta(hours=1))
    win._scheduled_recording_active = rec
    win.recorder.is_recording = True

    def stop(on_wait):
        win._is_closing = True  # closeEvent entregado durante el bombeo de eventos
        return ("C:/grab/fin.mp4", True)
    win.recorder.stop.side_effect = stop

    TrayReminderController(win).check_scheduled_recordings()

    assert _statuses() == {"Siguiente": "pending"}
    win.recorder.start.assert_not_called()
    win.record_btn.setChecked.assert_not_called()
