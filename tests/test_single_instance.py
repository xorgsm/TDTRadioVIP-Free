import time
import uuid

import pytest
from PySide6.QtNetwork import QLocalSocket
from PySide6.QtWidgets import QApplication

from core.single_instance import SingleInstanceGuard


def _app():
    return QApplication.instance() or QApplication([])


def _dispose(*guards):
    # deleteLater() no cierra el handle del mutex (es un entero de ctypes).
    for guard in guards:
        guard.release()
        guard.deleteLater()


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
        _dispose(guard)


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
        _dispose(first, second)


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
        _dispose(guard_a, guard_b)


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
        _dispose(first)


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
        _dispose(first)


def _first_probe_misses(monkeypatch, guard):
    """El primer sondeo de `guard` "no ve" a la otra instancia; los demás sí."""
    real_notify = guard._notify_running_instance
    llamadas = []

    def sondeo():
        llamadas.append(1)
        return False if len(llamadas) == 1 else real_notify()

    monkeypatch.setattr(guard, "_notify_running_instance", sondeo)
    return llamadas


def test_second_instance_that_loses_the_listen_race_still_defers(monkeypatch):
    """Arranque simultáneo sin mutex (Unix): el sondeo inicial no ve a nadie,
    pero otro proceso gana el listen(); el segundo debe reintentar el sondeo
    y cerrarse, sin borrar el nombre del servidor vivo."""
    import sys

    if sys.platform == "win32":
        pytest.skip("en Windows listen() no falla con el nombre en uso: decide el mutex")
    monkeypatch.setattr("core.single_instance._ACK_TIMEOUT_MS", 50)
    app = _app()
    key = f"TDTRadioVIP-test-{uuid.uuid4().hex}"
    first = SingleInstanceGuard(key)
    second = SingleInstanceGuard(key)
    activations = []
    first.activation_requested.connect(lambda: activations.append(1))
    try:
        assert first.try_acquire() is True
        llamadas = _first_probe_misses(monkeypatch, second)
        assert second.try_acquire() is False
        assert len(llamadas) == 2
        assert _pump_until(app, lambda: activations)
    finally:
        _dispose(first, second)


def test_mutex_taken_but_not_listening_yet_retries_the_notice(monkeypatch):
    """Doble clic rápido en Windows: el mutex ya es de la primera, pero su
    servidor aún no contesta; la segunda reintenta el aviso hasta que llega."""
    import sys

    if sys.platform != "win32":
        pytest.skip("el mutex solo existe en Windows")
    monkeypatch.setattr("core.single_instance._ACK_TIMEOUT_MS", 50)
    app = _app()
    key = f"TDTRadioVIP-test-{uuid.uuid4().hex}"
    first = SingleInstanceGuard(key)
    second = SingleInstanceGuard(key)
    activations = []
    first.activation_requested.connect(lambda: activations.append(1))
    try:
        assert first.try_acquire() is True
        llamadas = _first_probe_misses(monkeypatch, second)
        assert second.try_acquire() is False
        assert len(llamadas) == 2
        assert _pump_until(app, lambda: activations)
    finally:
        _dispose(first, second)


def test_owner_that_dies_while_the_second_retries_does_not_block_startup(monkeypatch):
    """La primera muere mientras la segunda reintenta el aviso: solo el handle
    de la segunda mantiene vivo el mutex, así que debe soltarlo y arrancar."""
    import sys

    if sys.platform != "win32":
        pytest.skip("el mutex solo existe en Windows")
    monkeypatch.setattr("core.single_instance._NOTIFY_RETRY_S", 0.2)
    _app()
    key = f"TDTRadioVIP-test-{uuid.uuid4().hex}"
    owner = SingleInstanceGuard(key)
    second = SingleInstanceGuard(key)
    try:
        assert owner._take_process_mutex() is True  # aún sin servidor

        def sondeo():
            owner._close_mutex()  # el propietario muere sin llegar a escuchar
            return False

        monkeypatch.setattr(second, "_notify_running_instance", sondeo)
        assert second.try_acquire() is True
    finally:
        _dispose(owner, second)


def test_owner_alive_but_not_answering_still_rejects_the_second(monkeypatch):
    import sys

    if sys.platform != "win32":
        pytest.skip("el mutex solo existe en Windows")
    monkeypatch.setattr("core.single_instance._NOTIFY_RETRY_S", 0.2)
    _app()
    key = f"TDTRadioVIP-test-{uuid.uuid4().hex}"
    owner = SingleInstanceGuard(key)
    second = SingleInstanceGuard(key)
    try:
        assert owner._take_process_mutex() is True  # vivo, pero sin servidor
        assert second.try_acquire() is False
    finally:
        _dispose(owner, second)


def test_ghost_name_is_removed_only_when_nobody_answers(monkeypatch):
    """listen() falla con el nombre en uso y nadie contesta al sondeo: es un
    nombre fantasma, se borra y se vuelve a escuchar."""
    from PySide6.QtNetwork import QAbstractSocket, QLocalServer

    import core.single_instance as si

    removed = []
    listens = []

    class _FakeServer(QLocalServer):
        def listen(self, name):
            listens.append(name)
            return len(listens) > 1

        def serverError(self):
            return QAbstractSocket.SocketError.AddressInUseError

    monkeypatch.setattr(si, "QLocalServer", _FakeServer)
    monkeypatch.setattr(_FakeServer, "removeServer", staticmethod(removed.append))
    _app()
    key = f"TDTRadioVIP-test-{uuid.uuid4().hex}"
    guard = SingleInstanceGuard(key)
    monkeypatch.setattr(guard, "_take_process_mutex", lambda: None)
    try:
        assert guard.try_acquire() is True
        assert removed == [key]
        assert len(listens) == 2
    finally:
        _dispose(guard)


def test_activation_before_binding_is_replayed_on_bind(monkeypatch):
    """Una segunda instancia que llega durante el splash (antes de que exista
    la ventana) no se pierde: se entrega al conectar el receptor."""
    monkeypatch.setattr("core.single_instance._ACK_TIMEOUT_MS", 50)
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
        _dispose(first, second)


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
        _dispose(first, second)


def test_failed_probe_does_not_keep_a_socket_alive(monkeypatch):
    import core.single_instance as si

    created = []

    class _Probe(QLocalSocket):
        def __init__(self, *args):
            super().__init__(*args)
            self.disposed = False
            created.append(self)

        def deleteLater(self):
            self.disposed = True
            super().deleteLater()

    monkeypatch.setattr(si, "QLocalSocket", _Probe)
    _app()
    guard = SingleInstanceGuard(f"TDTRadioVIP-test-{uuid.uuid4().hex}")
    try:
        assert guard._notify_running_instance() is False
        assert len(created) == 1 and created[0].disposed
        assert guard._probe is None
    finally:
        _dispose(guard)


def test_release_also_closes_the_notice_socket(monkeypatch):
    monkeypatch.setattr("core.single_instance._ACK_TIMEOUT_MS", 50)
    _app()
    key = f"TDTRadioVIP-test-{uuid.uuid4().hex}"
    first = SingleInstanceGuard(key)
    second = SingleInstanceGuard(key)
    try:
        assert first.try_acquire() is True
        assert second.try_acquire() is False
        assert second._probe is not None
        second.release()
        assert second._probe is None
    finally:
        _dispose(first, second)


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
        _dispose(guard)


_CHILD = """
import sys, time
from PySide6.QtWidgets import QApplication
from core.single_instance import SingleInstanceGuard

app = QApplication([])
guard = SingleInstanceGuard(sys.argv[1])
if not guard.try_acquire():
    print("denied", flush=True)
    sys.exit(0)
got = []
guard.bind_activation(lambda: got.append(1))
print("ready", flush=True)
deadline = time.monotonic() + 20
while time.monotonic() < deadline and not got:
    app.processEvents()
    time.sleep(0.01)
print("activated" if got else "timeout", flush=True)
guard.release()
"""


def _spawn_child(key):
    import os
    import subprocess
    import sys

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    return subprocess.Popen(
        [sys.executable, "-c", _CHILD, key],
        cwd=root, env=env, stdout=subprocess.PIPE, text=True,
    )


def _readline(child, timeout_s=30):
    """readline() del hijo con plazo: si se cuelga al arrancar Qt, el test
    falla en vez de dejar pytest colgado para siempre."""
    import threading

    line = []
    reader = threading.Thread(target=lambda: line.append(child.stdout.readline()), daemon=True)
    reader.start()
    reader.join(timeout_s)
    if not line:
        pytest.fail(f"el proceso hijo no respondió en {timeout_s} s")
    return line[0].strip()


def _kill_tree(child):
    # El python.exe de un venv de Windows es un lanzador que crea el proceso
    # real como hijo: child.kill() solo mataría el lanzador.
    import subprocess
    import sys

    if sys.platform == "win32":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(child.pid)],
            capture_output=True, check=False, timeout=30,
        )
    else:
        child.kill()
    child.wait(timeout=30)


def test_two_real_processes_only_one_acquires_and_the_other_is_notified():
    _app()
    key = f"TDTRadioVIP-test-{uuid.uuid4().hex}"
    child = _spawn_child(key)
    guard = SingleInstanceGuard(key)
    try:
        assert _readline(child) == "ready"
        assert guard.try_acquire() is False
        assert _readline(child) == "activated"
    finally:
        _kill_tree(child)
        _dispose(guard)


def test_lock_is_free_again_after_the_owning_process_dies():
    _app()
    key = f"TDTRadioVIP-test-{uuid.uuid4().hex}"
    child = _spawn_child(key)
    guard = SingleInstanceGuard(key)
    try:
        assert _readline(child) == "ready"
        _kill_tree(child)  # cierre en seco: sin release() ni aboutToQuit
        assert guard.try_acquire() is True
    finally:
        _kill_tree(child)  # ya muerto si todo fue bien; si no, que no quede vivo
        _dispose(guard)
