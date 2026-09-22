"""
Cobertura de ui/dialogs/vpn_dialog.py: mover connect()/disconnect()/status()
a un hilo aparte (_VpnWorker) en vez de llamarlos directamente desde un slot
de Qt.

Motivación (ver el docstring de _VpnWorker en el propio módulo): status()
puede lanzar un PowerShell por consulta y disconnect() puede tardar varios
segundos verificando que el proceso murió -- llamado en el hilo de la UI,
eso congela el diálogo entero (y con él toda la app, que comparte el mismo
bucle de eventos) mientras dura. Estos tests comprueban con un _VpnWorker
real (un QThread de verdad, no doblado) que el trabajo pesado corre fuera
del hilo principal y que la UI se actualiza correctamente cuando termina.

Patrón de espera: worker.wait() bloquea hasta que el hilo en segundo plano
termina de verdad; app.processEvents() entrega la señal en cola (Qt cruza
automáticamente threads con QueuedConnection) al slot del hilo principal.
Sin el processEvents() la señal quedaría pendiente y el test vería el
estado de antes de que el worker terminara.
"""
import threading

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from core import vpn_client, vpn_profiles
from ui.dialogs.vpn_dialog import VpnDialog


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


def _wait_worker(dialog, app, timeout_ms=3000):
    worker = dialog._vpn_worker
    assert worker is not None, "no se lanzó ningún _VpnWorker"
    assert worker.wait(timeout_ms), "el _VpnWorker no terminó a tiempo"
    app.processEvents()


def _make_dialog(monkeypatch, app, *, profiles=None, is_installed=True):
    monkeypatch.setattr(vpn_client, "is_openvpn_installed", lambda: is_installed)
    monkeypatch.setattr(vpn_profiles, "list_profiles", lambda *a, **k: profiles or [])
    dialog = VpnDialog()
    return dialog


_PROFILE = {"name": "Japon (VPNGate)", "tunnel": "japon_vpng", "conf_path": "japon_vpng.ovpn"}


def test_refresh_vpn_status_runs_status_off_the_ui_thread(monkeypatch, app):
    """El _refresh_vpn_status() inicial (disparado por _reload_vpn_combo
    en __init__) no debe ejecutar vpn_client.status() en el hilo
    principal."""
    caller_threads = []

    def _fake_status(tunnel):
        caller_threads.append(threading.current_thread())
        return True

    monkeypatch.setattr(vpn_client, "status", _fake_status)
    dialog = _make_dialog(monkeypatch, app, profiles=[_PROFILE])

    _wait_worker(dialog, app)

    assert caller_threads, "status() no se llegó a llamar"
    assert caller_threads[0] is not threading.main_thread()
    assert dialog.vpn_status_label.text() == "Conectado"
    assert dialog.vpn_toggle_btn.text() == "Desconectar"


def test_refresh_vpn_status_does_not_stack_a_second_worker_while_one_runs(monkeypatch, app):
    release = threading.Event()

    def _slow_status(tunnel):
        release.wait(timeout=2)
        return False

    monkeypatch.setattr(vpn_client, "status", _slow_status)
    dialog = _make_dialog(monkeypatch, app, profiles=[_PROFILE])

    first_worker = dialog._vpn_worker
    assert first_worker is not None and first_worker.isRunning()

    # Un segundo tick del QTimer mientras el primero sigue en marcha no
    # debe lanzar un segundo hilo hablando con openvpn-gui.exe a la vez.
    dialog._refresh_vpn_status()
    assert dialog._vpn_worker is first_worker

    release.set()
    _wait_worker(dialog, app)


def test_toggle_disables_button_immediately_and_reenables_after_connect(monkeypatch, app):
    monkeypatch.setattr(vpn_client, "status", lambda tunnel: False)
    connect_calls = []

    def _fake_connect(conf_path, tunnel):
        connect_calls.append((str(conf_path), tunnel))

    monkeypatch.setattr(vpn_client, "connect", _fake_connect)
    dialog = _make_dialog(monkeypatch, app, profiles=[_PROFILE])
    _wait_worker(dialog, app)  # deja terminar el refresh inicial

    dialog._on_vpn_toggle()
    assert dialog.vpn_toggle_btn.isEnabled() is False  # ya, antes de que el worker termine

    _wait_worker(dialog, app)  # termina el toggle...
    _wait_worker(dialog, app)  # ...que a su vez dispara otro _refresh_vpn_status

    assert connect_calls == [("japon_vpng.ovpn", "japon_vpng")]
    assert dialog.vpn_toggle_btn.isEnabled() is True


def test_toggle_shows_a_warning_and_reenables_button_on_vpn_client_error(monkeypatch, app):
    monkeypatch.setattr(vpn_client, "status", lambda tunnel: False)

    def _raise(*_a, **_k):
        raise vpn_client.VpnClientError("openvpn-gui.exe no respondió")

    monkeypatch.setattr(vpn_client, "connect", _raise)
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning",
        staticmethod(lambda *args, **kwargs: warnings.append(args[-1])),
    )
    dialog = _make_dialog(monkeypatch, app, profiles=[_PROFILE])
    _wait_worker(dialog, app)

    dialog._on_vpn_toggle()
    _wait_worker(dialog, app)

    assert warnings == ["openvpn-gui.exe no respondió"]
    assert dialog.vpn_toggle_btn.isEnabled() is True


def test_toggle_shows_a_generic_warning_and_reenables_button_on_unexpected_exception(monkeypatch, app):
    """_VpnWorker.run() debe atrapar cualquier excepción, no solo
    VpnClientError -- ver su propio comentario: subprocess.run() puede
    lanzar cosas como TimeoutExpired o UnicodeDecodeError que no son
    VpnClientError. Antes de este fix, esto dejaba el botón deshabilitado
    para siempre sin ningún aviso."""
    monkeypatch.setattr(vpn_client, "status", lambda tunnel: False)

    def _raise(*_a, **_k):
        raise TimeoutError("openvpn-gui.exe no respondió a tiempo")

    monkeypatch.setattr(vpn_client, "connect", _raise)
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning",
        staticmethod(lambda *args, **kwargs: warnings.append(args[-1])),
    )
    dialog = _make_dialog(monkeypatch, app, profiles=[_PROFILE])
    _wait_worker(dialog, app)

    dialog._on_vpn_toggle()
    _wait_worker(dialog, app)

    assert warnings == ["openvpn-gui.exe no respondió a tiempo"]
    assert dialog.vpn_toggle_btn.isEnabled() is True


def test_delete_disconnects_off_thread_before_removing_the_profile(monkeypatch, app):
    monkeypatch.setattr(vpn_client, "status", lambda tunnel: True)
    disconnect_calls = []
    monkeypatch.setattr(vpn_client, "disconnect", lambda tunnel: disconnect_calls.append(tunnel))
    monkeypatch.setattr(vpn_profiles, "get_profile", lambda name, *a, **k: dict(_PROFILE))
    delete_calls = []
    monkeypatch.setattr(vpn_profiles, "delete_profile", lambda name, *a, **k: delete_calls.append(name))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))

    dialog = _make_dialog(monkeypatch, app, profiles=[_PROFILE])
    _wait_worker(dialog, app)

    dialog._on_vpn_delete()
    _wait_worker(dialog, app)

    assert disconnect_calls == ["japon_vpng"]
    assert delete_calls == ["Japon (VPNGate)"]


def test_delete_skips_disconnect_when_the_tunnel_is_already_down(monkeypatch, app):
    monkeypatch.setattr(vpn_client, "status", lambda tunnel: False)

    def _boom(tunnel):
        raise AssertionError("no debería llamarse: el túnel ya está desconectado")

    monkeypatch.setattr(vpn_client, "disconnect", _boom)
    monkeypatch.setattr(vpn_profiles, "get_profile", lambda name, *a, **k: dict(_PROFILE))
    delete_calls = []
    monkeypatch.setattr(vpn_profiles, "delete_profile", lambda name, *a, **k: delete_calls.append(name))
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.Yes))

    dialog = _make_dialog(monkeypatch, app, profiles=[_PROFILE])
    _wait_worker(dialog, app)

    dialog._on_vpn_delete()
    _wait_worker(dialog, app)

    assert delete_calls == ["Japon (VPNGate)"]


def test_closing_the_dialog_waits_for_a_running_worker_instead_of_leaking_it(monkeypatch, app):
    """_wait_for_vpn_worker() (conectado a `finished`) debe bloquear
    hasta que el hilo en marcha termine de verdad, en vez de dejar un
    QThread vivo colgado de un QDialog que Qt está a punto de destruir."""
    release = threading.Event()

    def _slow_status(tunnel):
        release.wait(timeout=2)
        return False

    monkeypatch.setattr(vpn_client, "status", _slow_status)
    dialog = _make_dialog(monkeypatch, app, profiles=[_PROFILE])
    worker = dialog._vpn_worker
    assert worker is not None and worker.isRunning()

    release.set()
    dialog.reject()  # emite `finished` -> _wait_for_vpn_worker()

    assert worker.isFinished()
