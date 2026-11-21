"""ui.vpn_status.VpnStatusPoller: estado real de la VPN para la tarjeta del
raíl, consultado fuera del hilo de la UI. Sin subprocesos reales: la consulta
es un doble."""
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication

from ui import vpn_status
from ui.vpn_status import VPN_STATUS_POLL_MS, VpnStatusPoller


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def _make_win():
    return SimpleNamespace(_is_closing=False, nav_rail=SimpleNamespace(set_vpn_status=Mock()))


def _wait(poller, app):
    worker = poller._worker
    assert worker is not None, "no se lanzó ningún worker"
    assert worker.wait(3000), "el worker no terminó a tiempo"
    app.processEvents()


def test_poll_interval_is_slow(app):
    assert VPN_STATUS_POLL_MS == 20000


def test_connected_result_shows_the_card(app):
    win = _make_win()
    poller = VpnStatusPoller(win, query=lambda: (True, "Japón (VPNGate)"))
    poller.refresh()
    _wait(poller, app)
    win.nav_rail.set_vpn_status.assert_called_once_with(True, "Japón (VPNGate)")


def test_disconnected_result_hides_the_card(app):
    win = _make_win()
    poller = VpnStatusPoller(win, query=lambda: (False, ""))
    poller.refresh()
    _wait(poller, app)
    win.nav_rail.set_vpn_status.assert_called_once_with(False, "")


def test_failed_query_hides_the_card(app):
    """Nunca un «VPN activa» sin verificar: un fallo cuenta como apagada."""
    def _boom():
        raise OSError("powershell no disponible")

    win = _make_win()
    poller = VpnStatusPoller(win, query=_boom)
    poller.refresh()
    _wait(poller, app)
    win.nav_rail.set_vpn_status.assert_called_once_with(False, "")


def test_overlapping_refreshes_are_skipped(app):
    release = threading.Event()
    calls = []

    def _slow():
        calls.append(1)
        release.wait(timeout=2)
        return (True, "Japón")

    win = _make_win()
    poller = VpnStatusPoller(win, query=_slow)
    poller.refresh()
    first = poller._worker
    poller.refresh()
    assert poller._worker is first
    release.set()
    _wait(poller, app)
    assert len(calls) == 1
    win.nav_rail.set_vpn_status.assert_called_once_with(True, "Japón")


def test_requested_refresh_while_a_query_runs_runs_again_afterwards(app):
    """El diálogo de VPN pide refrescar tras ver un cambio: si justo hay una
    consulta en marcha (que empezó antes del cambio), se repite al acabar en
    vez de perderse."""
    release = threading.Event()
    answers = [(True, "Japón"), (False, "")]
    calls = []

    def _query():
        calls.append(1)
        if len(calls) == 1:
            release.wait(timeout=2)
        return answers[len(calls) - 1]

    win = _make_win()
    poller = VpnStatusPoller(win, query=_query)
    poller.refresh()
    first = poller._worker
    poller.request_refresh()
    assert poller._worker is first  # sin dos consultas a la vez
    release.set()
    _wait(poller, app)
    _wait(poller, app)
    assert len(calls) == 2
    assert win.nav_rail.set_vpn_status.call_args_list[-1].args == (False, "")


def test_requested_refresh_when_idle_queries_now(app):
    win = _make_win()
    poller = VpnStatusPoller(win, query=lambda: (True, "Japón"))
    poller.request_refresh()
    _wait(poller, app)
    win.nav_rail.set_vpn_status.assert_called_once_with(True, "Japón")


def test_closing_window_neither_starts_nor_applies(app):
    win = _make_win()
    poller = VpnStatusPoller(win, query=lambda: (True, "Japón"))
    poller.refresh()
    win._is_closing = True
    _wait(poller, app)
    win.nav_rail.set_vpn_status.assert_not_called()
    poller._worker = None
    poller.refresh()
    assert poller._worker is None


def test_start_checks_once_and_arms_the_timer(app):
    win = _make_win()
    poller = VpnStatusPoller(win, query=lambda: (False, ""))
    assert not poller.is_active()
    poller.start()
    try:
        assert poller.is_active()
        assert poller._timer.interval() == VPN_STATUS_POLL_MS
        _wait(poller, app)
        win.nav_rail.set_vpn_status.assert_called_once_with(False, "")
    finally:
        poller.stop()
    assert not poller.is_active()


def test_default_query_imports_vpn_modules_lazily():
    """La edición Free no tiene core.vpn_client: el módulo no lo importa."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(vpn_status))
    top_level = [
        node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    names = {
        (node.module or "") + "." + alias.name if isinstance(node, ast.ImportFrom) else alias.name
        for node in top_level for alias in node.names
    }
    assert not any("vpn_client" in name or "vpn_profiles" in name for name in names)


def test_default_query_reports_the_first_connected_profile(monkeypatch):
    vpn_client = pytest.importorskip("core.vpn_client")
    vpn_profiles = pytest.importorskip("core.vpn_profiles")
    monkeypatch.setattr(vpn_profiles, "list_profiles", lambda *a, **k: [
        {"name": "Corea", "tunnel": "corea"}, {"name": "Japón", "tunnel": "japon"},
    ])
    monkeypatch.setattr(vpn_client, "status", lambda tunnel: tunnel == "japon")
    assert vpn_status.query_vpn_status() == (True, "Japón")
    monkeypatch.setattr(vpn_client, "status", lambda tunnel: False)
    assert vpn_status.query_vpn_status() == (False, "")
