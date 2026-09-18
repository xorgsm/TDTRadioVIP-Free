"""
Diálogo VPN (edición VIP con licencia activada): conecta con servidores
gratuitos de VPNGate o con un .ovpn propio para acceder a listas públicas
de TV/radio con restricción geográfica.

Vivía como una sección más dentro de Ajustes (`ui/dialogs/settings.py`),
al final de un scroll de 5 secciones -- para llegar había que abrir
Ajustes y bajar hasta el final, lo que la dejaba prácticamente invisible
para quien no supiera de antemano que estaba ahí. Se extrae a su propio
diálogo, con entrada directa en el menú "Más ▾" (ver
ui.more_menu._build_settings_menu), para que sea un único clic en vez de
tres. La app no opera servidores VPN propios -- solo importa el .ovpn
elegido y pide a openvpn-gui.exe que conecte o desconecte ese perfil por
nombre (ver core/vpn_client.py y core/vpn_profiles.py).

El modelo bring-your-own (importar un .ovpn propio) se retiró en 8.5.0
para que VPNGate fuera la única fuente (100% gratis, sin depender de
terceros) y se reactiva en 8.6.0 junto a VPNGate -- no en su lugar --
porque en la práctica VPNGate suele estar dominado por servidores de
Japón/Corea y deja poca variedad de país; con esto quien encuentre un
.ovpn gratuito de otro proveedor (p.ej. ProtonVPN free, Windscribe free)
puede seguir usándolo como un perfil más.

Coder By X@R
"""
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import QThread, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QInputDialog, QLabel,
    QMessageBox, QPushButton, QVBoxLayout,
)

from core import vpn_client, vpn_profiles
from ui.dialogs._common import _header, _panel
from ui.dialogs.vpngate_picker import VpnGatePickerDialog
from ui.visual import set_surface, set_variant

# Cada cuánto se relee el estado de la VPN mientras el diálogo está
# abierto -- así se ve "Conectado" en verde sin tener que cerrar y
# reabrir el diálogo ni mirar la ventana propia de openvpn-gui.exe.
_VPN_STATUS_POLL_MS = 2000


class _VpnWorker(QThread):
    """Ejecuta una llamada a core.vpn_client (o cualquier callable sin
    argumentos) en un hilo aparte y notifica el resultado con una señal.

    connect()/disconnect()/status() hablan con openvpn-gui.exe y, en el
    caso de disconnect(), pueden quedarse esperando varios segundos
    (hasta _DISCONNECT_VERIFY_ATTEMPTS intentos de 1s verificando que el
    proceso murió, más el propio timeout de 10s de cada subprocess.run
    si openvpn-gui.exe no responde) -- y status() lanza un PowerShell
    (Get-CimInstance) en cada consulta. Todo eso llamado directamente
    desde un slot de Qt bloquea el hilo de la UI (el único que hay en
    una app Qt): el diálogo entero -- y con él, toda la ventana
    principal, que comparte el mismo bucle de eventos -- se queda
    congelado mientras dura. Confirmado leyendo el código: antes de
    este cambio, _refresh_vpn_status() (cada 2s mientras el diálogo
    está abierto) y _on_vpn_toggle()/_on_vpn_delete() llamaban a estas
    funciones tal cual, en el hilo de la UI."""

    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, func: Callable[[], object], parent=None):
        super().__init__(parent)
        self._func = func

    def run(self) -> None:
        try:
            result = self._func()
        except vpn_client.VpnClientError as exc:
            self.failed.emit(str(exc))
        else:
            self.succeeded.emit(result)


class VpnDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        set_surface(self, "dialog")
        self.setWindowTitle("VPN")
        self.setMinimumWidth(480)

        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(20, 18, 20, 18)
        root.addLayout(_header(
            "VPN",
            "Conecta con un servidor gratuito de VPNGate o importa un .ovpn "
            "propio para acceder a listas públicas de TV/radio con "
            "restricción geográfica.",
        ))

        panel_vpn, form_vpn = _panel("VPN")

        if not vpn_client.is_openvpn_installed():
            aviso = QLabel(
                "Para conectar necesitas el cliente oficial de OpenVPN "
                "instalado en este PC."
            )
            aviso.setWordWrap(True)
            aviso.setObjectName("dialogSubtitle")
            form_vpn.addRow(aviso)
            descargar_btn = QPushButton("Descargar OpenVPN…")
            descargar_btn.clicked.connect(
                lambda: QDesktopServices.openUrl(
                    QUrl("https://openvpn.net/community-downloads/")
                )
            )
            form_vpn.addRow(descargar_btn)
            root.addWidget(panel_vpn)
            root.addStretch(1)
            self._add_close_button(root)
            return

        # Un único worker "en curso" a la vez -- ver _VpnWorker. Si ya hay
        # uno corriendo (una consulta de estado o una acción de
        # conectar/desconectar/eliminar), el resto de operaciones lo
        # esperan en vez de lanzar un segundo hilo que hable con
        # openvpn-gui.exe en paralelo.
        self._vpn_worker: Optional[_VpnWorker] = None

        self.vpn_profile_combo = QComboBox()
        form_vpn.addRow("Perfil:", self.vpn_profile_combo)

        self.vpn_status_label = QLabel()
        form_vpn.addRow("Estado:", self.vpn_status_label)

        vpn_row = QHBoxLayout()
        gratis_btn = QPushButton("Servidor gratuito (VPNGate)…")
        gratis_btn.clicked.connect(self._on_vpn_gate_pick)
        importar_btn = QPushButton("Importar perfil (.ovpn)…")
        importar_btn.clicked.connect(self._on_vpn_import)
        eliminar_btn = QPushButton("Eliminar")
        eliminar_btn.clicked.connect(self._on_vpn_delete)
        self.vpn_toggle_btn = QPushButton("Conectar")
        self.vpn_toggle_btn.clicked.connect(self._on_vpn_toggle)
        vpn_row.addWidget(gratis_btn)
        vpn_row.addWidget(importar_btn)
        vpn_row.addWidget(eliminar_btn)
        vpn_row.addWidget(self.vpn_toggle_btn)
        form_vpn.addRow(vpn_row)

        aviso = QLabel(
            "Elige un servidor gratuito de VPNGate (dominado sobre todo "
            "por Japón/Corea, sin cuenta ni suscripción) o importa un "
            ".ovpn que ya tengas de otro proveedor gratuito para tener más "
            "países donde elegir. No hace falta permiso de administrador "
            "para conectar ni desconectar -- solo la primera vez que "
            "importes un perfil, si hace falta, la app te pedirá permiso "
            "de administrador (UAC) una única vez para configurar el "
            "acceso ella sola. El estado puede tardar unos segundos en "
            "reflejar el cambio."
        )
        aviso.setWordWrap(True)
        aviso.setObjectName("dialogSubtitle")
        form_vpn.addRow(aviso)

        root.addWidget(panel_vpn)
        root.addStretch(1)
        self._reload_vpn_combo()

        # Refresco en vivo: sin esto, el botón solo se actualiza al pulsarlo
        # -- para ver el cambio a "Conectado" en verde había que fiarse de
        # la ventana propia de openvpn-gui.exe en vez de esta app.
        self._vpn_status_timer = QTimer(self)
        self._vpn_status_timer.timeout.connect(self._refresh_vpn_status)
        self._vpn_status_timer.start(_VPN_STATUS_POLL_MS)
        self.finished.connect(self._vpn_status_timer.stop)
        self.finished.connect(self._wait_for_vpn_worker)

        self._add_close_button(root)

    def _add_close_button(self, root: QVBoxLayout) -> None:
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        root.addWidget(buttons)

    def _reload_vpn_combo(self, select_name: Optional[str] = None) -> None:
        self.vpn_profile_combo.blockSignals(True)
        self.vpn_profile_combo.clear()
        for entry in vpn_profiles.list_profiles():
            self.vpn_profile_combo.addItem(entry["name"], entry["tunnel"])
        if select_name is not None:
            idx = self.vpn_profile_combo.findText(select_name)
            if idx >= 0:
                self.vpn_profile_combo.setCurrentIndex(idx)
        self.vpn_profile_combo.blockSignals(False)
        self._refresh_vpn_status()

    def _current_vpn_tunnel(self) -> Optional[str]:
        return self.vpn_profile_combo.currentData()

    def _wait_for_vpn_worker(self) -> None:
        """Al cerrar el diálogo: si queda un _VpnWorker corriendo (p.ej.
        el disconnect() de 8.6.4 todavía verificando que el proceso
        murió), hay que esperarlo antes de dejar que Qt destruya este
        QDialog -- destruir un QObject con un QThread hijo todavía en
        marcha es un error de Qt (advertencia o crash, según
        plataforma), no un simple "se cancela solo"."""
        if self._vpn_worker is not None:
            self._vpn_worker.wait()

    def _run_vpn_worker(
        self, func: Callable[[], object],
        on_success: Callable[[object], None],
        on_error: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """Lanza `func` (una llamada a core.vpn_client) en un _VpnWorker.

        Devuelve False sin hacer nada si ya hay un worker en curso -- no
        se apilan hilos nuevos sobre uno que todavía está hablando con
        openvpn-gui.exe. `on_success`/`on_error` se ejecutan ya en el
        hilo de la UI (Qt convierte la señal entre hilos en una
        QueuedConnection automáticamente), así que ahí sí es seguro
        tocar widgets."""
        if self._vpn_worker is not None and self._vpn_worker.isRunning():
            return False
        worker = _VpnWorker(func, self)
        self._vpn_worker = worker

        def _cleanup():
            if self._vpn_worker is worker:
                self._vpn_worker = None

        worker.succeeded.connect(on_success)
        if on_error is not None:
            worker.failed.connect(on_error)
        worker.finished.connect(_cleanup)
        worker.start()
        return True

    def _refresh_vpn_status(self) -> None:
        tunnel = self._current_vpn_tunnel()
        if not tunnel:
            self.vpn_status_label.setText("Sin perfiles guardados")
            set_variant(self.vpn_status_label, "secondary")
            set_variant(self.vpn_toggle_btn, "secondary")
            self.vpn_toggle_btn.setEnabled(False)
            return
        self.vpn_toggle_btn.setEnabled(True)
        # status() puede lanzar un PowerShell (Get-CimInstance) para
        # comprobar si el túnel sigue vivo -- ver el docstring de
        # _VpnWorker. Si ya hay una consulta/acción en curso (p.ej. el
        # tick anterior del timer todavía no ha vuelto, o el usuario
        # acaba de pulsar Conectar/Desconectar), este tick se salta en
        # vez de acumular hilos.
        self._run_vpn_worker(
            lambda: vpn_client.status(tunnel),
            lambda connected: self._apply_vpn_status(tunnel, connected),
        )

    def _apply_vpn_status(self, tunnel: str, connected: bool) -> None:
        if self._current_vpn_tunnel() != tunnel:
            return  # el usuario cambió de perfil mientras la consulta corría
        self.vpn_status_label.setText("Conectado" if connected else "Desconectado")
        self.vpn_toggle_btn.setText("Desconectar" if connected else "Conectar")
        variant = "success" if connected else "secondary"
        set_variant(self.vpn_status_label, variant)
        set_variant(self.vpn_toggle_btn, variant)

    def _on_vpn_gate_pick(self):
        dialog = VpnGatePickerDialog(self)
        if dialog.exec() != QDialog.Accepted or dialog.selected_server is None:
            return
        server = dialog.selected_server
        pais = server.get("country_long") or server.get("country_short") or "VPNGate"
        nombre, ok = QInputDialog.getText(
            self, "Servidor gratuito (VPNGate)", "Nombre para este perfil:",
            text=f"{pais} (VPNGate)",
        )
        nombre = (nombre or "").strip()
        if not ok or not nombre:
            return
        try:
            vpn_profiles.import_profile_from_text(nombre, server["ovpn_text"])
        except vpn_profiles.VpnProfileError as exc:
            QMessageBox.warning(self, "Servidor gratuito (VPNGate)", str(exc))
            return
        self._reload_vpn_combo(select_name=nombre)

    def _on_vpn_import(self):
        """Importa un .ovpn propio (p.ej. de ProtonVPN free, Windscribe
        free, o cualquier otro proveedor gratuito) como perfil VPN más,
        junto a los de VPNGate -- ver el docstring del módulo."""
        ruta, _filtro = QFileDialog.getOpenFileName(
            self, "Importar perfil VPN", "", "Configuración OpenVPN (*.ovpn);;Todos los archivos (*)"
        )
        if not ruta:
            return
        sugerido = Path(ruta).stem
        nombre, ok = QInputDialog.getText(
            self, "Importar perfil (.ovpn)", "Nombre para este perfil:", text=sugerido,
        )
        nombre = (nombre or "").strip()
        if not ok or not nombre:
            return
        try:
            vpn_profiles.import_profile(nombre, Path(ruta))
        except vpn_profiles.VpnProfileError as exc:
            QMessageBox.warning(self, "Importar perfil (.ovpn)", str(exc))
            return
        self._reload_vpn_combo(select_name=nombre)

    def _on_vpn_delete(self):
        """Antes, comprobar el estado y desconectar (si hacía falta) se
        llamaba tal cual en el hilo de la UI -- disconnect() puede
        tardar varios segundos verificando que el proceso murió de
        verdad (ver core.vpn_client.disconnect y el docstring de
        _VpnWorker), así que confirmar "Eliminar" podía congelar toda
        la app durante ese rato antes de que se viera ningún cambio."""
        nombre = self.vpn_profile_combo.currentText()
        if not nombre:
            return
        if QMessageBox.question(
            self, "Eliminar perfil VPN", f"¿Eliminar el perfil «{nombre}»?"
        ) != QMessageBox.Yes:
            return
        entry = vpn_profiles.get_profile(nombre)

        def _disconnect_if_needed() -> None:
            if entry and vpn_client.status(entry["tunnel"]):
                vpn_client.disconnect(entry["tunnel"])

        def _finish_delete(_result: object) -> None:
            vpn_profiles.delete_profile(nombre)
            self._reload_vpn_combo()

        def _on_disconnect_error(message: str) -> None:
            QMessageBox.warning(
                self, "Eliminar perfil VPN",
                f"No se pudo desconectar el túnel antes de borrarlo: {message}",
            )

        started = self._run_vpn_worker(_disconnect_if_needed, _finish_delete, _on_disconnect_error)
        if not started:
            QMessageBox.information(
                self, "Eliminar perfil VPN",
                "Hay otra operación de VPN en curso; inténtalo de nuevo en unos segundos.",
            )

    def _on_vpn_toggle(self):
        tunnel = self._current_vpn_tunnel()
        if not tunnel:
            return
        entry = vpn_profiles.get_profile(self.vpn_profile_combo.currentText())

        def _toggle() -> bool:
            """Se recalcula connected DENTRO del worker (no se reutiliza
            el último status() ya pintado en la etiqueta) para decidir
            conectar/desconectar contra el estado real en el momento
            de ejecutar, no contra uno que pudo quedarse desactualizado
            mientras el usuario miraba el diálogo."""
            connected = vpn_client.status(tunnel)
            if connected:
                vpn_client.disconnect(tunnel)
            elif entry:
                vpn_client.connect(Path(entry["conf_path"]), tunnel)
            return connected

        def _on_done(_connected: object) -> None:
            self.vpn_toggle_btn.setEnabled(True)
            self._refresh_vpn_status()

        def _on_error(message: str) -> None:
            QMessageBox.warning(self, "VPN", message)
            _on_done(None)

        self.vpn_toggle_btn.setEnabled(False)
        started = self._run_vpn_worker(_toggle, _on_done, _on_error)
        if not started:
            self.vpn_toggle_btn.setEnabled(True)
