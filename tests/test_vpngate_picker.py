"""
Cobertura de ui/dialogs/vpngate_picker.py: descargar la lista de VPNGate
en un hilo aparte (_FetchWorker) en vez de llamar a fetch_servers()
directamente desde __init__.

Motivación: fetch_servers() es una petición HTTP (hasta 10s de timeout,
ver core/vpngate.py) contra un tercero que puede no responder -- llamada
tal cual desde __init__ bloqueaba toda la ventana antes de que el diálogo
llegara siquiera a verse, el mismo patrón que las últimas versiones ya
corrigieron para connect()/disconnect()/status() (ver
ui/dialogs/vpn_dialog.py y tests/test_vpn_dialog.py, mismo patrón de
espera con worker.wait() + app.processEvents()).
"""
import threading

import pytest
from PySide6.QtWidgets import QApplication

from core.vpngate import VpnGateError
from ui.dialogs.vpngate_picker import VpnGatePickerDialog

_SERVERS = [
    {"country_long": "Japón", "ping": 40, "speed": 50_000_000, "hostname": "jp1.vpngate.net",
     "ovpn_text": "client\nremote jp1.vpngate.net 1194\n"},
    {"country_long": "Francia", "ping": 120, "speed": 10_000_000, "hostname": "fr1.example.com",
     "ovpn_text": "client\nremote fr1.example.com 1194\n"},
]


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def _wait_worker(dialog, app, timeout_ms=3000):
    worker = dialog._fetch_worker
    assert worker is not None, "no se lanzó ningún _FetchWorker"
    assert worker.wait(timeout_ms), "el _FetchWorker no terminó a tiempo"
    app.processEvents()


def test_fetch_runs_off_the_ui_thread_and_populates_the_list(app):
    caller_threads = []

    def _fake_fetch():
        caller_threads.append(threading.current_thread())
        return list(_SERVERS)

    dialog = VpnGatePickerDialog(fetch_servers=_fake_fetch)
    _wait_worker(dialog, app)

    assert caller_threads, "fetch_servers() no se llegó a llamar"
    assert caller_threads[0] is not threading.main_thread()
    assert dialog.list_widget.count() == 2
    assert dialog.status_label.text() == "2 servidores disponibles."


def test_slow_fetch_does_not_block_dialog_construction(app):
    release = threading.Event()

    def _slow_fetch():
        release.wait(timeout=2)
        return list(_SERVERS)

    dialog = VpnGatePickerDialog(fetch_servers=_slow_fetch)

    # El diálogo debe existir ya (constructor devuelto) con la descarga
    # todavía en marcha -- antes de este fix, __init__ no habría vuelto
    # hasta que _slow_fetch() terminara.
    assert dialog._fetch_worker is not None
    assert dialog._fetch_worker.isRunning()
    assert dialog.status_label.text() == "Descargando lista de servidores…"

    release.set()
    _wait_worker(dialog, app)
    assert dialog.list_widget.count() == 2


def test_fetch_failure_shows_the_error_without_crashing(app):
    def _raise():
        raise VpnGateError("VPNGate no responde")

    dialog = VpnGatePickerDialog(fetch_servers=_raise)
    _wait_worker(dialog, app)

    assert dialog.status_label.text() == "No se pudo cargar la lista: VPNGate no responde"
    assert dialog.list_widget.count() == 0


def test_empty_server_list_shows_a_dedicated_message(app):
    dialog = VpnGatePickerDialog(fetch_servers=lambda: [])
    _wait_worker(dialog, app)

    assert dialog.status_label.text() == "VPNGate no tiene servidores disponibles ahora mismo."


def test_closing_the_dialog_waits_for_a_running_fetch_instead_of_leaking_it(app):
    release = threading.Event()

    def _slow_fetch():
        release.wait(timeout=2)
        return list(_SERVERS)

    dialog = VpnGatePickerDialog(fetch_servers=_slow_fetch)
    worker = dialog._fetch_worker
    assert worker is not None and worker.isRunning()

    release.set()
    dialog.reject()  # emite `finished` -> _wait_for_fetch_worker()

    assert worker.isFinished()
