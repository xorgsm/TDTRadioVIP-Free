"""
Selector de servidores VPN gratuitos de VPNGate (ver core/vpngate.py).

Se abre desde la sección VPN de Ajustes como alternativa a importar un
.ovpn a mano: descarga la lista pública de servidores, deja elegir uno
por país/velocidad, y el resultado (un dict de core.vpngate.fetch_servers)
lo importa el llamador con core.vpn_profiles.import_profile_from_text() --
este diálogo no toca vpn_profiles ni hace red aparte de list_servers().
"""
from typing import Callable, List, Optional

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout,
)

from ui.dialogs._common import _header
from ui.visual import set_surface


def _format_entry(server: dict) -> str:
    pais = server.get("country_long") or server.get("country_short") or "?"
    ping = server.get("ping") or 0
    speed_mbps = (server.get("speed") or 0) / 1_000_000
    return f"{pais}  —  {ping} ms  —  {speed_mbps:.1f} Mbps  —  {server.get('hostname', '')}"


class _FetchWorker(QThread):
    """Descarga la lista de servidores VPNGate en un hilo aparte.

    fetch_servers() es una petición HTTP (hasta 10s de timeout, ver
    core/vpngate.py) contra un tercero que puede no responder -- llamarla
    tal cual desde __init__ (como antes) bloqueaba toda la ventana
    mientras se esperaba, sin que ni siquiera llegara a verse el diálogo
    abierto. Mismo patrón que ui.dialogs.vpn_dialog._VpnWorker, ya usado
    para connect()/disconnect()/status() desde 8.6.5."""

    succeeded = Signal(list)
    failed = Signal(str)

    def __init__(self, fetch_servers: Callable[[], List[dict]], parent=None):
        super().__init__(parent)
        self._fetch_servers = fetch_servers

    def run(self) -> None:
        from core.vpngate import VpnGateError

        try:
            servers = self._fetch_servers()
        except VpnGateError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc) or "Error inesperado al descargar la lista de servidores.")
        else:
            self.succeeded.emit(servers)


class VpnGatePickerDialog(QDialog):
    """Lista de servidores VPNGate ya ordenada por puntuación (mejor
    primero, según el propio VPNGate). `fetch_servers` es inyectable
    para poder probar el diálogo sin red real."""

    def __init__(self, parent=None, fetch_servers: Optional[Callable[[], List[dict]]] = None):
        super().__init__(parent)
        from core import vpngate as _vpngate

        self._fetch_servers = fetch_servers or _vpngate.fetch_servers
        self._servers: List[dict] = []
        self.selected_server: Optional[dict] = None
        self._fetch_worker: Optional[_FetchWorker] = None
        self.finished.connect(self._wait_for_fetch_worker)

        set_surface(self, "dialog")
        self.setWindowTitle("Servidores gratuitos (VPNGate)")
        self.setMinimumSize(480, 420)

        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(20, 18, 20, 18)
        root.addLayout(_header(
            "Servidores gratuitos (VPNGate)",
            "Servidores VPN públicos y gratuitos mantenidos por voluntarios "
            "(proyecto VPNGate, Universidad de Tsukuba). No hace falta cuenta "
            "ni suscripción -- elige uno y se guardará como un perfil VPN más.",
        ))

        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Filtrar por país…")
        self.filter_input.textChanged.connect(self._apply_filter)
        root.addWidget(self.filter_input)

        self.list_widget = QListWidget()
        self.list_widget.itemSelectionChanged.connect(self._update_ok_enabled)
        self.list_widget.itemDoubleClicked.connect(lambda _item: self._try_accept())
        root.addWidget(self.list_widget, stretch=1)

        self.status_label = QLabel("Descargando lista de servidores…")
        self.status_label.setObjectName("dialogSubtitle")
        self.status_label.setWordWrap(True)
        root.addWidget(self.status_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setObjectName("primaryButton")
        buttons.button(QDialogButtonBox.Ok).setText("Usar este servidor")
        buttons.button(QDialogButtonBox.Ok).setEnabled(False)
        buttons.accepted.connect(self._try_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self._ok_button = buttons.button(QDialogButtonBox.Ok)

        self._load_servers()

    def _load_servers(self) -> None:
        worker = _FetchWorker(self._fetch_servers, self)
        self._fetch_worker = worker
        worker.succeeded.connect(self._on_fetch_succeeded)
        worker.failed.connect(self._on_fetch_failed)
        worker.finished.connect(self._on_fetch_worker_finished)
        worker.start()

    def _on_fetch_worker_finished(self) -> None:
        self._fetch_worker = None

    def _on_fetch_succeeded(self, servers: List[dict]) -> None:
        self._servers = servers
        if not self._servers:
            self.status_label.setText("VPNGate no tiene servidores disponibles ahora mismo.")
            return
        self.status_label.setText(f"{len(self._servers)} servidores disponibles.")
        self._apply_filter()

    def _on_fetch_failed(self, message: str) -> None:
        self.status_label.setText(f"No se pudo cargar la lista: {message}")

    def _wait_for_fetch_worker(self) -> None:
        """Igual que ui.dialogs.vpn_dialog.VpnDialog._wait_for_vpn_worker:
        si el diálogo se cierra con la descarga todavía en marcha, hay
        que esperar a que el QThread termine antes de dejar que Qt
        destruya este QDialog."""
        if self._fetch_worker is not None:
            self._fetch_worker.wait()

    def _apply_filter(self) -> None:
        needle = self.filter_input.text().strip().casefold()
        self.list_widget.clear()
        for server in self._servers:
            pais = (server.get("country_long") or "").casefold()
            if needle and needle not in pais:
                continue
            item = QListWidgetItem(_format_entry(server))
            item.setData(Qt.UserRole, server)
            self.list_widget.addItem(item)
        self._update_ok_enabled()

    def _update_ok_enabled(self) -> None:
        self._ok_button.setEnabled(self.list_widget.currentItem() is not None)

    def _try_accept(self) -> None:
        item = self.list_widget.currentItem()
        if item is None:
            return
        self.selected_server = item.data(Qt.UserRole)
        self.accept()
