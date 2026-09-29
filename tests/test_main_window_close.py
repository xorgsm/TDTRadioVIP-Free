"""
Cierre ordenado de la ventana principal (MainWindow.closeEvent).

Lo que se prueba es que un fallo en un paso del cierre no se salte los
siguientes: antes, por ejemplo, un fallo de libVLC en player.stop() dejaba
sin ejecutar la limpieza de la barra de tareas, la espera de los hilos en
segundo plano y player.release() -- el mismo cuelgue al salir que se
corrigió en VLCPlayer.release() en 8.6.13.

Se usa una ventana simulada (SimpleNamespace + Mock) en vez de MainWindow.
FetchWorker y shutdown_workers se sustituyen en el módulo: el
FetchWorker.begin_shutdown() real cambia un registro global compartido por
toda la suite.
"""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core import recording_schedule
from ui import main_window
from ui.main_window import MainWindow


@pytest.fixture
def stubs(monkeypatch):
    fetch_worker = Mock()
    fetch_worker.active_workers.return_value = ("worker-a",)
    shutdown_workers = Mock()
    monkeypatch.setattr(main_window, "FetchWorker", fetch_worker)
    monkeypatch.setattr(main_window, "shutdown_workers", shutdown_workers)
    return SimpleNamespace(fetch_worker=fetch_worker, shutdown_workers=shutdown_workers)


@pytest.fixture
def win():
    return SimpleNamespace(
        _is_closing=False,
        _reminder_timer=Mock(),
        _tray_icon=Mock(),
        _media_keys=Mock(),
        _scheduled_recording_active=None,
        _taskbar=Mock(),
        recorder=Mock(is_recording=False),
        player=Mock(),
        equalizer=Mock(),
    )


def _close(win):
    event = Mock()
    MainWindow.closeEvent(win, event)
    return event


def _assert_rest_of_shutdown_ran(win, stubs, event):
    win._taskbar.cleanup.assert_called_once()
    stubs.shutdown_workers.assert_called_once_with(("worker-a",))
    win.player.release.assert_called_once()
    event.accept.assert_called_once()


def test_close_runs_every_step_and_releases_player_last(win, stubs):
    orden = []
    stubs.shutdown_workers.side_effect = lambda workers: orden.append("workers")
    win.player.release.side_effect = lambda: orden.append("release")

    event = _close(win)

    assert win._is_closing is True
    stubs.fetch_worker.begin_shutdown.assert_called_once()
    win._reminder_timer.stop.assert_called_once()
    win._tray_icon.hide.assert_called_once()
    win._media_keys.stop.assert_called_once()
    win.player.stop.assert_called_once()
    win.equalizer.stop.assert_called_once()
    _assert_rest_of_shutdown_ran(win, stubs, event)
    assert orden == ["workers", "release"]


def test_second_close_is_ignored(win, stubs):
    win._is_closing = True

    event = _close(win)

    event.ignore.assert_called_once()
    event.accept.assert_not_called()
    win.player.release.assert_not_called()


def test_player_stop_failure_does_not_skip_rest_of_close(win, stubs):
    win.player.stop.side_effect = OSError("libVLC no responde")

    event = _close(win)

    win.equalizer.stop.assert_called_once()
    _assert_rest_of_shutdown_ran(win, stubs, event)


def test_recorder_stop_failure_does_not_skip_rest_of_close(win, stubs):
    win.recorder.is_recording = True
    win.recorder.stop.side_effect = RuntimeError("ffmpeg colgado")

    event = _close(win)

    win.player.stop.assert_called_once()
    _assert_rest_of_shutdown_ran(win, stubs, event)


def test_tray_icon_failure_does_not_skip_rest_of_close(win, stubs):
    win._tray_icon.hide.side_effect = RuntimeError("bandeja")

    event = _close(win)

    win._media_keys.stop.assert_called_once()
    _assert_rest_of_shutdown_ran(win, stubs, event)


def test_workers_failure_still_releases_player(win, stubs):
    stubs.shutdown_workers.side_effect = RuntimeError("hilo colgado")

    event = _close(win)

    win.player.release.assert_called_once()
    event.accept.assert_called_once()


def test_release_failure_still_accepts_close(win, stubs):
    win.player.release.side_effect = OSError("libVLC")

    event = _close(win)

    event.accept.assert_called_once()


def test_scheduled_recording_is_marked_done_on_close(win, stubs, monkeypatch):
    mark_done = Mock()
    monkeypatch.setattr(recording_schedule, "mark_done", mark_done)
    win.recorder.is_recording = True
    win._scheduled_recording_active = SimpleNamespace(tvg_id="la1", title="Noticias", start="10:00")

    _close(win)

    win.recorder.stop.assert_called_once()
    mark_done.assert_called_once_with("la1", "Noticias", "10:00")
    assert win._scheduled_recording_active is None
