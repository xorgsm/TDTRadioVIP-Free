import time
import uuid

from PySide6.QtNetwork import QLocalSocket
from PySide6.QtWidgets import QApplication

from core.single_instance import SingleInstanceGuard


def _app():
    return QApplication.instance() or QApplication([])


def _pump_until(app, predicate, timeout_ms=2000, step_ms=10):
    waited = 0
    while not predicate() and waited < timeout_ms:
        app.processEvents()
        time.sleep(step_ms / 1000)
        waited += step_ms
    return predicate()


def test_first_instance_acquires_the_lock():
    _app()
    key = f"TDTRadioVIP-test-{uuid.uuid4().hex}"
    guard = SingleInstanceGuard(key)
    try:
        assert guard.try_acquire() is True
    finally:
        guard.deleteLater()


def test_second_instance_fails_to_acquire_and_notifies_the_first(monkeypatch):
    # Las dos instancias comparten hilo: la primera no puede acusar recibo
    # mientras la segunda espera, así que no se espera el plazo real.
    monkeypatch.setattr("core.single_instance._ACK_TIMEOUT_MS", 50)
    app = _app()
    key = f"TDTRadioVIP-test-{uuid.uuid4().hex}"
    first = SingleInstanceGuard(key)
    second = SingleInstanceGuard(key)
    activated = []
    first.activation_requested.connect(lambda: activated.append(True))
    try:
        assert first.try_acquire() is True
        assert second.try_acquire() is False
        assert _pump_until(app, lambda: len(activated) == 1)
    finally:
        first.deleteLater()
        second.deleteLater()


def test_different_keys_do_not_collide():
    _app()
    key_a = f"TDTRadioVIP-test-{uuid.uuid4().hex}"
    key_b = f"TDTRadioVIP-test-{uuid.uuid4().hex}"
    guard_a = SingleInstanceGuard(key_a)
    guard_b = SingleInstanceGuard(key_b)
    try:
        assert guard_a.try_acquire() is True
        assert guard_b.try_acquire() is True
    finally:
        guard_a.deleteLater()
        guard_b.deleteLater()


def test_second_process_that_exits_right_away_still_activates_the_first():
    """La segunda instancia real termina nada más avisar (ver
    ui/application.py): el aviso tiene que llegar aunque su proceso muera."""
    import subprocess
    import sys
    from pathlib import Path

    app = _app()
    key = f"TDTRadioVIP-test-{uuid.uuid4().hex}"
    first = SingleInstanceGuard(key)
    activated = []
    first.activation_requested.connect(lambda: activated.append(True))
    code = (
        "from PySide6.QtCore import QCoreApplication\n"
        "from core.single_instance import SingleInstanceGuard\n"
        "app = QCoreApplication([])\n"
        f"raise SystemExit(0 if SingleInstanceGuard({key!r}).try_acquire() is False else 1)\n"
    )
    try:
        assert first.try_acquire() is True
        second = subprocess.Popen(
            [sys.executable, "-c", code], cwd=Path(__file__).resolve().parent.parent
        )
        assert _pump_until(app, lambda: second.poll() is not None, timeout_ms=15000)
        assert second.returncode == 0
        assert _pump_until(app, lambda: len(activated) == 1)
    finally:
        first.deleteLater()


def test_activation_survives_a_first_instance_busy_for_a_few_seconds():
    """La ventana abierta puede tardar en atender eventos (cargando una lista
    enorme, por ejemplo): el aviso de la segunda instancia no debe perderse."""
    import subprocess
    import sys
    from pathlib import Path

    app = _app()
    key = f"TDTRadioVIP-test-{uuid.uuid4().hex}"
    first = SingleInstanceGuard(key)
    activated = []
    first.activation_requested.connect(lambda: activated.append(True))
    code = (
        "from PySide6.QtCore import QCoreApplication\n"
        "from core.single_instance import SingleInstanceGuard\n"
        "app = QCoreApplication([])\n"
        f"raise SystemExit(0 if SingleInstanceGuard({key!r}).try_acquire() is False else 1)\n"
    )
    try:
        assert first.try_acquire() is True
        second = subprocess.Popen(
            [sys.executable, "-c", code], cwd=Path(__file__).resolve().parent.parent
        )
        time.sleep(2.5)  # primera instancia ocupada: no procesa eventos
        assert _pump_until(app, lambda: second.poll() is not None, timeout_ms=15000)
        assert second.returncode == 0
        assert _pump_until(app, lambda: len(activated) == 1)
    finally:
        first.deleteLater()


def test_second_instance_that_loses_the_listen_race_still_defers(monkeypatch):
    """Arranque simultáneo: el sondeo inicial no ve a nadie, pero otro proceso
    gana el listen(); el segundo debe reintentar el sondeo y cerrarse."""
    from PySide6.QtNetwork import QLocalServer

    app = _app()
    key = f"TDTRadioVIP-test-{uuid.uuid4().hex}"
    first = SingleInstanceGuard(key)
    second = SingleInstanceGuard(key)
    activations = []
    first.activation_requested.connect(lambda: activations.append(1))
    try:
        assert first.try_acquire() is True
        real_notify = second._notify_running_instance
        llamadas = []

        def sondeo():
            llamadas.append(1)
            # el primer sondeo "no ve" a la primera instancia
            return False if len(llamadas) == 1 else real_notify()

        monkeypatch.setattr(second, "_notify_running_instance", sondeo)
        # removeServer no puede quitar el nombre de un servidor vivo, así que
        # listen() falla con AddressInUse, como en la carrera real.
        assert second.try_acquire() is False
        assert len(llamadas) == 2
        assert _pump_until(app, lambda: activations)
    finally:
        first.deleteLater()
        second.deleteLater()


def test_activation_before_binding_is_replayed_on_bind():
    """Una segunda instancia que llega durante el splash (antes de que exista
    la ventana) no se pierde: se entrega al conectar el receptor."""
    app = _app()
    key = f"TDTRadioVIP-test-{uuid.uuid4().hex}"
    first = SingleInstanceGuard(key)
    second = SingleInstanceGuard(key)
    try:
        assert first.try_acquire() is True
        assert second.try_acquire() is False
        assert _pump_until(app, lambda: first._pending_activation)

        recibidos = []
        first.bind_activation(lambda: recibidos.append(1))
        assert recibidos == [1]
    finally:
        first.deleteLater()
        second.deleteLater()


def test_release_frees_the_lock_so_the_key_can_be_acquired_again(monkeypatch):
    monkeypatch.setattr("core.single_instance._NOTIFY_RETRY_S", 0.2)
    _app()
    key = f"TDTRadioVIP-test-{uuid.uuid4().hex}"
    first = SingleInstanceGuard(key)
    second = SingleInstanceGuard(key)
    try:
        assert first.try_acquire() is True
        first.release()
        first.release()  # idempotente
        assert second.try_acquire() is True
    finally:
        first.deleteLater()
        second.deleteLater()


def test_failed_probe_does_not_keep_a_socket_child():
    _app()
    guard = SingleInstanceGuard(f"TDTRadioVIP-test-{uuid.uuid4().hex}")
    try:
        assert guard._notify_running_instance() is False
        assert guard.findChildren(QLocalSocket) == []
    finally:
        guard.deleteLater()


def test_mutex_creation_failure_is_logged_and_does_not_block_startup(monkeypatch, caplog):
    import sys

    if sys.platform != "win32":
        return
    _app()

    class _FakeKernel32:
        def __init__(self):
            self.CreateMutexW = lambda *a: 0

    monkeypatch.setattr("ctypes.WinDLL", lambda *a, **k: _FakeKernel32())
    guard = SingleInstanceGuard(f"TDTRadioVIP-test-{uuid.uuid4().hex}")
    try:
        with caplog.at_level("WARNING"):
            assert guard.try_acquire() is True
        assert any("mutex" in r.getMessage().lower() for r in caplog.records)
    finally:
        guard.deleteLater()
