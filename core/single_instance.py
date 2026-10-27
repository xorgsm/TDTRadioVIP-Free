"""
Evita que el usuario abra sin querer una segunda instancia de la app (doble
clic accidental en el acceso directo, o lanzarla otra vez sin darse cuenta
de que ya estaba abierta) -- ver ui/application._create_application().

Un QLocalServer con nombre fijo por edición actúa de "cerrojo": la primera
instancia lo crea y se queda escuchando; cualquier instancia posterior que
intente conectar a ese mismo nombre lo consigue (hay alguien escuchando), se
lo toma como señal de "ya hay una corriendo", le avisa por ese mismo socket
para que traiga su ventana al frente, y se cierra sola sin llegar a mostrar
ventana. VIP y Free usan nombres distintos (ver ui/application.py) -- mismo
criterio que el AppUserModelID de core/bootstrap.py -- así que sí pueden
estar las dos abiertas a la vez, cada una es "su propia" instancia única.

No usa QSharedMemory (la alternativa más común para esto): en Windows un
cierre en seco del proceso (kill, corte de luz) puede dejar el segmento de
memoria compartida "fantasma" bloqueando instancias futuras hasta reiniciar
el sistema. QLocalServer no tiene ese problema -- su socket lo libera el
propio sistema operativo en cuanto el proceso muere, sin dejar nada atrás
que limpiar a mano.

Coder By X@R
"""
from __future__ import annotations

import sys
import time

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QAbstractSocket, QLocalServer, QLocalSocket

from core.logger import get_logger

log = get_logger(__name__)

_CONNECT_TIMEOUT_MS = 200
# La primera instancia puede tardar en atender el aviso (cargando una lista
# enorme): si la segunda se cierra antes, el aviso se pierde. Esta espera no
# se ve (la segunda instancia no tiene ventana) y acaba en cuanto llega el acuse.
_ACK_TIMEOUT_MS = 10000
# Con el mutex tomado por otra instancia que aún está arrancando, su servidor
# local puede no estar escuchando todavía: se reintenta el aviso este rato.
_NOTIFY_RETRY_S = 3.0
_NOTIFY_RETRY_STEP_S = 0.1
_ERROR_ALREADY_EXISTS = 183


class SingleInstanceGuard(QObject):
    """Cerrojo de instancia única identificado por `key` (nombre fijo por edición)."""

    activation_requested = Signal()

    def __init__(self, key: str, parent=None):
        super().__init__(parent)
        self._key = key
        self._server: QLocalServer | None = None
        self._probe: QLocalSocket | None = None
        self._bound = False
        self._pending_activation = False
        self._mutex = None

    def bind_activation(self, callback) -> None:
        """
        Conecta `callback` a activation_requested y le entrega el aviso que
        llegó antes de poder conectarlo (una segunda instancia durante el
        splash, cuando todavía no existe la ventana).
        """
        self._bound = True
        self.activation_requested.connect(callback)
        if self._pending_activation:
            self._pending_activation = False
            callback()

    def try_acquire(self) -> bool:
        """
        True si esta instancia consigue el cerrojo (es la única corriendo;
        debe seguir arrancando normal). False si ya había otra corriendo
        (se le avisó para que se active; esta debe cerrarse sin más, ver
        ui/application.py).
        """
        if self._take_process_mutex() is False:
            # Otra instancia tiene el cerrojo, aunque todavía no esté
            # escuchando (doble clic rápido): se le avisa en cuanto pueda.
            if self._notify_with_retry():
                return False
            # Nadie atendió en todo el plazo: puede que quien creó el mutex
            # muriera mientras tanto y solo lo mantenga vivo el handle de esta
            # instancia. Se suelta y se vuelve a pedir; si sigue existiendo,
            # la otra instancia está viva pero no atiende.
            self._close_mutex()
            if self._take_process_mutex() is False:
                log.warning("La instancia abierta no atendió el aviso de activación")
                return False

        if self._notify_running_instance():
            return False

        server = QLocalServer(self)
        server.newConnection.connect(self._on_new_connection)
        if not server.listen(self._key):
            in_use = server.serverError() == QAbstractSocket.SocketError.AddressInUseError
            # Dos arranques simultáneos (doble clic rápido): los dos fallaron
            # el sondeo y el otro ganó el listen(). Se vuelve a sondear antes
            # de dar el cerrojo por inalcanzable.
            if in_use and self._notify_running_instance():
                return False
            # Nadie contesta: es un nombre "fantasma" de un cierre en seco
            # anterior (en Unix el socket queda como fichero). removeServer()
            # lo borra SIN comprobar si hay alguien escuchando, así que solo
            # se llama ahora, tras confirmar que no hay nadie detrás.
            if in_use:
                QLocalServer.removeServer(self._key)
                if server.listen(self._key):
                    self._server = server
                    return True
            # No se pudo escuchar por algo distinto de "ya hay una instancia"
            # (permisos, nombre no válido en este SO...) -- no tiene sentido
            # bloquear un arranque legítimo por un problema del cerrojo en
            # sí, así que se deja pasar como si fuera la única instancia.
            log.warning("No se pudo crear el cerrojo de instancia única (%s)", server.errorString())
            return True
        self._server = server
        return True

    def _take_process_mutex(self) -> bool | None:
        """
        En Windows, QLocalServer.listen() sobre un nombre en uso NO falla (las
        dos instancias de un doble clic rápido acabarían "escuchando"), así
        que el cerrojo atómico es un mutex con nombre, que el sistema libera
        al morir el proceso. False si ya lo tenía otro proceso, True si lo
        toma esta instancia, None si no hay mutex en esta plataforma.
        """
        if sys.platform != "win32":
            return None
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
        handle = kernel32.CreateMutexW(None, False, "Local\\" + self._key)
        if not handle:
            # Sin mutex solo queda el sondeo del servidor local, que en
            # Windows no basta para un doble clic rápido: se deja constancia.
            log.warning("No se pudo crear el mutex de instancia única (error %s)", ctypes.get_last_error())
            return None
        self._mutex = handle
        return ctypes.get_last_error() != _ERROR_ALREADY_EXISTS

    def _notify_with_retry(self) -> bool:
        """Reintenta el aviso durante _NOTIFY_RETRY_S; True si se entregó."""
        deadline = time.monotonic() + _NOTIFY_RETRY_S
        while not self._notify_running_instance():
            if time.monotonic() >= deadline:
                return False
            time.sleep(_NOTIFY_RETRY_STEP_S)
        return True

    def _close_mutex(self) -> None:
        if self._mutex is None:
            return
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle(self._mutex)
        self._mutex = None

    def release(self) -> None:
        """
        Libera el mutex, el servidor local y el socket del aviso; se puede
        llamar varias veces. La instancia que se cierra tras avisar no lo
        llama (ver ui/application.py): cerrar su socket justo después de
        escribir haría perder el aviso (ver _notify_running_instance).
        """
        self._close_mutex()
        if self._server is not None:
            self._server.close()
            self._server = None
        if self._probe is not None:
            self._probe.abort()
            self._probe = None

    def _notify_running_instance(self) -> bool:
        """True si había otra instancia escuchando y se le avisó."""
        probe = QLocalSocket()
        probe.connectToServer(self._key)
        if probe.waitForConnected(_CONNECT_TIMEOUT_MS):
            probe.write(b"activate")
            probe.waitForBytesWritten(_CONNECT_TIMEOUT_MS)
            # Esta instancia se cierra enseguida (ver ui/application.py): se
            # espera el acuse de la primera para que el aviso no se pierda si
            # el proceso termina antes de que ella lo haya leído.
            if not probe.waitForReadyRead(_ACK_TIMEOUT_MS):
                log.warning("La instancia abierta no confirmó el aviso de activación")
            # A propósito NO se cierra el socket aquí (ni disconnectFromServer()
            # ni dejar que el GC se lo lleve al salir de la función, que tiene
            # el mismo efecto): en Windows, una tubería con nombre que se
            # cierra nada más escribir se descarta entera -- el otro extremo
            # nunca llega a ver ni la conexión ni los bytes, aunque
            # waitForBytesWritten() ya haya devuelto True (confirmado
            # reproduciendo el problema a mano). Se guarda en `self` para que
            # siga vivo el resto del ciclo de vida de esta instancia -- que
            # de todos modos va a cerrarse sola enseguida (ver
            # ui/application.py), momento en el que el sistema operativo
            # libera el socket sin que haga falta cerrarlo a mano.
            self._probe = probe
            return True
        probe.deleteLater()
        return False

    def _on_new_connection(self):
        if self._server is None:
            return
        socket = self._server.nextPendingConnection()
        if socket is None:
            return
        socket.readyRead.connect(lambda: self._consume(socket))
        socket.disconnected.connect(socket.deleteLater)

    def _consume(self, socket: QLocalSocket) -> None:
        socket.readAll()
        # Acuse para la segunda instancia, que lo espera antes de cerrarse.
        socket.write(b"ok")
        socket.flush()
        if not self._bound:
            self._pending_activation = True
        self.activation_requested.emit()
