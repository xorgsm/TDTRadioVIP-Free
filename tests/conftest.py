import pytest


@pytest.fixture
def trusted_update_key(monkeypatch):
    """Instala la clave publica de prueba como clave de actualizaciones."""
    import _signing
    from core import update_signature

    monkeypatch.setattr(
        update_signature, "UPDATE_PUBLIC_KEY_N_B64", _signing.public_modulus_b64()
    )


@pytest.fixture(autouse=True)
def _offline_dns(monkeypatch):
    """Los tests no deben depender de DNS real: todo host resuelve a una
    IP pública de documentación salvo que el test fije otra cosa."""
    import ipaddress

    from core import net_safety

    monkeypatch.setattr(
        net_safety, "_resolve", lambda host: [ipaddress.ip_address("93.184.216.34")]
    )


@pytest.fixture(autouse=True)
def _mockable_pinned_get(request, monkeypatch):
    """El pinning de DNS abre su propia Session y se saltaría los tests que
    parchean `requests.get`: aquí delega en `requests.get` (resuelto al llamar)
    salvo en test_dns_pinning, que ejercita la conexión fijada de verdad."""
    if request.module.__name__.endswith("test_dns_pinning"):
        return
    import requests

    from core import http_limits

    monkeypatch.setattr(
        http_limits, "_pinned_get",
        lambda resolver: lambda url, **kwargs: requests.get(url, **kwargs),
    )


# MainWindow real (offscreen) sin red, bandeja, teclas multimedia ni ajustes
# del usuario: la usan tests/test_main_window_widget_contract.py y
# tests/test_main_window_min_size.py.
@pytest.fixture
def make_window(monkeypatch, tmp_path):
    from PySide6.QtWidgets import QApplication

    from core import config as cfg
    from core import favorites as fav_store
    from core import history as hist_store
    from ui import main_window as mw
    from ui.app_lifecycle import AppLifecycle
    from ui.media_keys import SystemMediaKeys
    from ui.tray_controller import TrayReminderController

    app = QApplication.instance() or QApplication([])
    settings = dict(cfg.DEFAULT_SETTINGS)
    settings["downloads_dir"] = str(tmp_path / "descargas")
    settings["recordings_dir"] = str(tmp_path / "grabaciones")
    monkeypatch.setattr(cfg, "load_settings", lambda: dict(settings))
    monkeypatch.setattr(cfg, "save_settings", lambda _s: True)
    monkeypatch.setattr(fav_store, "load_favorites", lambda: [])
    monkeypatch.setattr(hist_store, "load_history", lambda: [])
    monkeypatch.setattr(TrayReminderController, "setup", lambda self: None)
    monkeypatch.setattr(AppLifecycle, "schedule_startup_tasks", lambda self: None)
    monkeypatch.setattr(SystemMediaKeys, "start", lambda self: None)
    monkeypatch.setattr(mw.MainWindow, "_start_initial_loads", lambda self: None)
    windows = []

    def _make(width=1320, height=860, **kwargs):
        # Edición Free por defecto (como main_free.py): este archivo también
        # se publica en el repo Free, donde core.caster y compañía no existen.
        # Los casos que de verdad necesitan la edición con licencia lo piden
        # explícitamente y se saltan allí con pytest.importorskip.
        kwargs.setdefault("activated", True)
        kwargs.setdefault("es_version_free", True)
        win = mw.MainWindow(**kwargs)
        win.resize(width, height)
        win.show()
        app.processEvents()
        windows.append(win)
        return win

    yield _make
    from PySide6.QtCore import QEvent

    for win in windows:
        win.hide()
        win.deleteLater()
    # Sin bucle de eventos, processEvents() no ejecuta los deleteLater: las
    # ventanas seguían vivas hasta el cierre del intérprete, y allí sus
    # eventFilter recibían eventos con layouts ya destruidos (cierre del
    # proceso con 0xC0000409 de vez en cuando). Se destruyen aquí.
    app.sendPostedEvents(None, QEvent.DeferredDelete)
    app.processEvents()
