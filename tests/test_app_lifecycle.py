"""
Cobertura del cierre ordenado de ui/app_lifecycle.py (AppLifecycle.shutdown).

Lo que se prueba es que un fallo en un paso del cierre no se salte los
siguientes: antes, por ejemplo, un fallo de libVLC en player.stop() dejaba
sin ejecutar el cierre de descargas (yt-dlp.exe seguía vivo), la espera de
los hilos en segundo plano y player.release() -- el mismo cuelgue al salir
que se corrigió en VLCPlayer.release() en 8.6.13.

Se usa una ventana simulada (SimpleNamespace + Mock) en vez de MainWindow.
FetchWorker y shutdown_workers se sustituyen en el módulo: el
FetchWorker.begin_shutdown() real cambia un registro global compartido por
toda la suite.
"""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core import recording_schedule
from ui import app_lifecycle
from ui.app_lifecycle import AppLifecycle


@pytest.fixture
def stubs(monkeypatch):
    fetch_worker = Mock()
    fetch_worker.active_workers.return_value = ("worker-a",)
    shutdown_workers = Mock()
    monkeypatch.setattr(app_lifecycle, "FetchWorker", fetch_worker)
    monkeypatch.setattr(app_lifecycle, "shutdown_workers", shutdown_workers)
    if app_lifecycle.vpn_client is not None:  # None en la edición Free
        monkeypatch.setattr(app_lifecycle.vpn_client, "is_openvpn_installed", lambda: False)
    return SimpleNamespace(fetch_worker=fetch_worker, shutdown_workers=shutdown_workers)


@pytest.fixture
def win():
    catalog = Mock()
    catalog.cancel_background_diagnostics.return_value = None
    return SimpleNamespace(
        _is_closing=False,
        _reminder_timer=Mock(),
        _tray_icon=Mock(),
        _media_keys=Mock(),
        _scheduled_recording_active=None,
        _cast_session=Mock(),
        _dlna_session=Mock(),
        _taskbar=Mock(),
        recorder=Mock(is_recording=False),
        player=Mock(),
        equalizer=Mock(),
        download_panel=Mock(),
        catalog=catalog,
    )


def _assert_rest_of_shutdown_ran(win, stubs):
    win.download_panel.shutdown.assert_called_once()
    win._taskbar.cleanup.assert_called_once()
    stubs.shutdown_workers.assert_called_once()
    win.player.release.assert_called_once()


def test_shutdown_runs_every_step_and_releases_player_last(win, stubs):
    orden = []
    stubs.shutdown_workers.side_effect = lambda workers: orden.append("workers")
    win.player.release.side_effect = lambda: orden.append("release")

    AppLifecycle(win).shutdown()

    assert win._is_closing is True
    stubs.fetch_worker.begin_shutdown.assert_called_once()
    win._reminder_timer.stop.assert_called_once()
    win._tray_icon.hide.assert_called_once()
    win._media_keys.stop.assert_called_once()
    win.player.stop.assert_called_once()
    win.equalizer.stop.assert_called_once()
    win._cast_session.disconnect.assert_called_once()
    win._dlna_session.disconnect.assert_called_once()
    _assert_rest_of_shutdown_ran(win, stubs)
    assert orden == ["workers", "release"]


def test_player_stop_failure_does_not_skip_rest_of_shutdown(win, stubs):
    win.player.stop.side_effect = OSError("libVLC no responde")

    AppLifecycle(win).shutdown()

    win.equalizer.stop.assert_called_once()
    _assert_rest_of_shutdown_ran(win, stubs)


def test_recorder_stop_failure_does_not_skip_rest_of_shutdown(win, stubs):
    win.recorder.is_recording = True
    win.recorder.stop.side_effect = RuntimeError("ffmpeg colgado")

    AppLifecycle(win).shutdown()

    win.player.stop.assert_called_once()
    _assert_rest_of_shutdown_ran(win, stubs)


def test_cast_disconnect_failure_still_disconnects_dlna(win, stubs):
    win._cast_session.disconnect.side_effect = RuntimeError("pychromecast")

    AppLifecycle(win).shutdown()

    win._dlna_session.disconnect.assert_called_once()
    _assert_rest_of_shutdown_ran(win, stubs)


def test_download_panel_failure_still_waits_workers_and_releases_player(win, stubs):
    win.download_panel.shutdown.side_effect = RuntimeError("libtorrent")

    AppLifecycle(win).shutdown()

    stubs.shutdown_workers.assert_called_once()
    win.player.release.assert_called_once()


@pytest.mark.skipif(app_lifecycle.vpn_client is None, reason="VPN solo en la edición con licencia")
def test_vpn_profile_listing_failure_does_not_abort_shutdown(win, stubs, monkeypatch):
    monkeypatch.setattr(app_lifecycle.vpn_client, "is_openvpn_installed", lambda: True)

    def _roto(*_args, **_kwargs):
        raise OSError("índice VPN ilegible")

    monkeypatch.setattr(app_lifecycle.vpn_profiles, "list_profiles", _roto)

    AppLifecycle(win).shutdown()

    _assert_rest_of_shutdown_ran(win, stubs)


def test_shutdown_never_raises_even_if_player_release_fails(win, stubs):
    win.player.release.side_effect = OSError("libVLC")

    AppLifecycle(win).shutdown()  # no debe propagar: closeEvent tiene que poder aceptar


def test_scheduled_recording_is_closed_when_app_closes_mid_recording(win, stubs, monkeypatch):
    rec = SimpleNamespace(tvg_id="La1.es", title="Telediario", start="20260928200000")
    win.recorder.is_recording = True
    win._scheduled_recording_active = rec
    mark_done = Mock()
    monkeypatch.setattr(recording_schedule, "mark_done", mark_done)

    AppLifecycle(win).shutdown()

    win.recorder.stop.assert_called_once()
    mark_done.assert_called_once_with("La1.es", "Telediario", "20260928200000")
    assert win._scheduled_recording_active is None


def test_background_diagnostics_worker_is_waited_with_the_others(win, stubs):
    win.catalog.cancel_background_diagnostics.return_value = "diagnostico"

    AppLifecycle(win).shutdown()

    stubs.shutdown_workers.assert_called_once_with(("worker-a", "diagnostico"))
