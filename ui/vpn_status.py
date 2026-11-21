"""Estado real de la VPN para la tarjeta «VPN activa» del raíl (edición con
licencia activada).

core.vpn_client.status() bloquea (lee el log del túnel y lanza un PowerShell
para comprobar que el proceso sigue vivo), así que se consulta en un
FetchWorker: una vez al arrancar y luego cada VPN_STATUS_POLL_MS. Un fallo de
la consulta apaga la tarjeta: un indicador de privacidad no debe decir
«activa» sin haberlo comprobado.

core.vpn_client/core.vpn_profiles no existen en la edición Free: se importan
solo dentro de query_vpn_status(), nunca a nivel de módulo.
"""
from typing import Callable, Optional, Tuple

from PySide6.QtCore import QObject, QTimer, Slot

from ui.fetch_worker import FetchWorker

VPN_STATUS_POLL_MS = 20000


def query_vpn_status() -> Tuple[bool, str]:
    """(conectado, nombre del perfil) del primer perfil con túnel activo, o
    (False, "") si no hay ninguno. Bloquea: llamar fuera del hilo de la UI."""
    from core import vpn_client, vpn_profiles

    for entry in vpn_profiles.list_profiles():
        if vpn_client.status(entry["tunnel"]):
            return True, entry["name"]
    return False, ""


class VpnStatusPoller(QObject):
    """Consulta periódica y sin solaparse; el resultado llega a
    win.nav_rail.set_vpn_status en el hilo de la UI."""

    def __init__(
        self, win, query: Optional[Callable[[], Tuple[bool, str]]] = None,
        interval_ms: int = VPN_STATUS_POLL_MS, parent=None,
    ):
        super().__init__(parent)
        self.win = win
        self._query = query or query_vpn_status
        self._worker: Optional[FetchWorker] = None
        # request_refresh() llegó con una consulta en marcha: se repite al
        # acabar, porque esa consulta pudo empezar antes del cambio.
        self._refresh_pending = False
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self.refresh)

    def start(self) -> None:
        """Comprobación inmediata y luego cada intervalo."""
        self.refresh()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def is_active(self) -> bool:
        return self._timer.isActive()

    @Slot()
    def request_refresh(self) -> None:
        """Consulta cuanto antes, sin esperar al siguiente tick: la pide el
        diálogo de VPN cuando ve un cambio. Nunca dos consultas a la vez."""
        if self._worker is not None and self._worker.isRunning():
            self._refresh_pending = True
            return
        self.refresh()

    @Slot()
    def refresh(self) -> None:
        if getattr(self.win, "_is_closing", False):
            return
        if self._worker is not None and self._worker.isRunning():
            return  # la consulta anterior aún no ha vuelto
        worker = FetchWorker(self._query)
        worker.done.connect(self._on_done)
        self._worker = worker
        worker.start()

    @Slot(object)
    def _on_done(self, result) -> None:
        if getattr(self.win, "_is_closing", False):
            return
        connected, label = False, ""
        if isinstance(result, tuple) and len(result) == 2 and result[0]:
            connected, label = True, str(result[1])
        self.win.nav_rail.set_vpn_status(connected, label)
        if self._refresh_pending:
            self._refresh_pending = False
            self.refresh()
