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

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

from core.logger import get_logger

log = get_logger(__name__)

_CONNECT_TIMEOUT_MS = 200


class SingleInstanceGuard(QObject):
    """Cerrojo de instancia única identificado por `key` (nombre fijo por edición)."""

    activation_requested = Signal()

    def __init__(self, key: str, parent=None):
        super().__init__(parent)
        self._key = key
        self._server: QLocalServer | None = None
        self._probe: QLocalSocket | None = None

    def try_acquire(self) -> bool:
        """
        True si esta instancia consigue el cerrojo (es la única corriendo;
        debe seguir arrancando normal). False si ya había otra corriendo
        (se le avisó para que se active; esta debe cerrarse sin más, ver
        ui/application.py).
        """
        probe = QLocalSocket(self)
        probe.connectToServer(self._key)
        if probe.waitForConnected(_CONNECT_TIMEOUT_MS):
            probe.write(b"activate")
            probe.waitForBytesWritten(_CONNECT_TIMEOUT_MS)
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
            return False

        # Nombre "fantasma" de un cierre en seco anterior (crash, kill): un
        # segundo listen() sobre el mismo nombre sin este paso previo
        # fallaría con AddressInUseError aunque no haya ningún proceso real
        # detrás -- removeServer() ya comprueba que no haya un servidor de
        # verdad escuchando antes de dejar reusar el nombre.
        QLocalServer.removeServer(self._key)
        server = QLocalServer(self)
        server.newConnection.connect(self._on_new_connection)
        if not server.listen(self._key):
            # No se pudo escuchar por algo distinto de "ya hay una instancia"
            # (permisos, nombre no válido en este SO...) -- no tiene sentido
            # bloquear un arranque legítimo por un problema del cerrojo en
            # sí, así que se deja pasar como si fuera la única instancia.
            log.warning("No se pudo crear el cerrojo de instancia única (%s)", server.errorString())
            return True
        self._server = server
        return True

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
        self.activation_requested.emit()
