"""
Diálogo de preferencias: canales, guía y grabaciones, mantenimiento
automático, apariencia (tema y color de acento), VPN y perfil de usuario.
"""
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFrame, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from core import config as cfg
from core import countries
from core import vpn_client, vpn_profiles
from ui import palette
from ui.dialogs.vpngate_picker import VpnGatePickerDialog
from ui.style import ACCENT_PRESETS, DEFAULT_ACCENT
from ui.visual import set_surface

from ui.dialogs._common import _header, _panel


class SettingsDialog(QDialog):
    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        set_surface(self, "dialog")
        self.setWindowTitle("Configuración")
        self.setMinimumWidth(480)
        self.resize(560, 640)
        self.settings = dict(settings)

        root = QVBoxLayout(self)
        root.setSpacing(14)
        root.setContentsMargins(20, 18, 20, 18)
        root.addLayout(_header(
            "Configuración",
            "Fuentes de contenido, grabación y aspecto de la aplicación.",
        ))

        # Todas las secciones van dentro de un scroll: con las 5 juntas
        # (Canales, Guía y grabaciones, Mantenimiento, Apariencia, Perfil)
        # el diálogo sin scroll se volvía más alto que la pantalla y no
        # dejaba encogerlo ni ver las últimas secciones.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 4, 0)
        content_layout.setSpacing(14)
        scroll.setWidget(content)
        root.addWidget(scroll, stretch=1)

        # ---- Canales ----
        panel_canales, form_canales = _panel("Canales")
        self.tv_country_combo = QComboBox()
        self._fill_country_combo(self.tv_country_combo, self.settings.get("tv_country_code", "ES"))
        form_canales.addRow("País de TV:", self.tv_country_combo)

        self.tv_url_input = QLineEdit(self.settings.get("tv_playlist_url", ""))
        self.tv_url_input.setPlaceholderText("(opcional) URL M3U propia — anula el país de arriba")
        form_canales.addRow("Lista TV personalizada:", self.tv_url_input)

        self.radio_country_combo = QComboBox()
        self._fill_country_combo(self.radio_country_combo, self.settings.get("radio_country_code", "ES"))
        form_canales.addRow("País de radio:", self.radio_country_combo)
        content_layout.addWidget(panel_canales)

        # ---- Guía y grabaciones ----
        panel_grab, form_grab = _panel("Guía y grabaciones")
        self.epg_input = QLineEdit(self.settings.get("epg_url", ""))
        self.epg_input.setPlaceholderText("URL de guía XMLTV (opcional)")
        form_grab.addRow("EPG (XMLTV):", self.epg_input)

        rec_row = QHBoxLayout()
        self.rec_dir_input = QLineEdit(self.settings.get("recordings_dir", ""))
        browse_btn = QPushButton("Examinar…")
        browse_btn.clicked.connect(self._browse_dir)
        rec_row.addWidget(self.rec_dir_input)
        rec_row.addWidget(browse_btn)
        form_grab.addRow("Carpeta de grabaciones:", rec_row)
        content_layout.addWidget(panel_grab)

        panel_maintenance, form_maintenance = _panel("Mantenimiento automático")
        self.auto_backup_check = QCheckBox("Crear copias de seguridad automáticamente")
        self.auto_backup_check.setChecked(
            bool(self.settings.get("automatic_backups_enabled", True))
        )
        form_maintenance.addRow("Copias:", self.auto_backup_check)
        self.backup_interval_combo = QComboBox()
        self.backup_interval_combo.addItem("Cada día", 1)
        self.backup_interval_combo.addItem("Cada semana", 7)
        interval_index = self.backup_interval_combo.findData(
            int(self.settings.get("automatic_backup_interval_days", 1))
        )
        self.backup_interval_combo.setCurrentIndex(max(0, interval_index))
        form_maintenance.addRow("Frecuencia:", self.backup_interval_combo)
        self.backup_retention_combo = QComboBox()
        for count in (3, 7, 14):
            self.backup_retention_combo.addItem(f"Conservar {count} copias", count)
        retention_index = self.backup_retention_combo.findData(
            int(self.settings.get("automatic_backup_retention", 7))
        )
        self.backup_retention_combo.setCurrentIndex(max(0, retention_index))
        form_maintenance.addRow("Retención:", self.backup_retention_combo)
        self.auto_diagnostics_check = QCheckBox("Revisar streams antiguos en segundo plano")
        self.auto_diagnostics_check.setChecked(
            bool(self.settings.get("automatic_stream_diagnostics", True))
        )
        form_maintenance.addRow("Diagnóstico:", self.auto_diagnostics_check)
        self.auto_update_check_check = QCheckBox("Buscar actualizaciones automáticamente al iniciar")
        self.auto_update_check_check.setChecked(
            bool(self.settings.get("automatic_update_check", True))
        )
        form_maintenance.addRow("Actualizaciones:", self.auto_update_check_check)
        content_layout.addWidget(panel_maintenance)

        # ---- Apariencia ----
        panel_apariencia, form_apariencia = _panel("Apariencia")
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Oscuro", "dark")
        self.theme_combo.addItem("Claro", "light")
        theme_index = self.theme_combo.findData(self.settings.get("theme_mode", "dark"))
        self.theme_combo.setCurrentIndex(max(0, theme_index))
        form_apariencia.addRow("Tema:", self.theme_combo)

        self.card_size_combo = QComboBox()
        self.card_size_combo.addItem("Compactas", 140)
        self.card_size_combo.addItem("Medianas", 168)
        self.card_size_combo.addItem("Grandes", 204)
        card_index = self.card_size_combo.findData(
            int(self.settings.get("catalog_card_size", 168))
        )
        self.card_size_combo.setCurrentIndex(max(0, card_index))
        form_apariencia.addRow("Tarjetas del catálogo:", self.card_size_combo)

        self.resume_last_check = QCheckBox("Reanudar el último canal o emisora al iniciar")
        self.resume_last_check.setChecked(bool(self.settings.get("resume_last_stream", False)))
        form_apariencia.addRow("Reproducción:", self.resume_last_check)

        self.fullscreen_autohide_check = QCheckBox(
            "Ocultar cabecera y controles en pantalla completa "
            "(aparecen al mover el ratón)"
        )
        self.fullscreen_autohide_check.setChecked(
            bool(self.settings.get("fullscreen_autohide_ui", True))
        )
        form_apariencia.addRow("Pantalla completa:", self.fullscreen_autohide_check)

        accent_row = QHBoxLayout()
        accent_row.setSpacing(8)
        self._accent_group = QButtonGroup(self)
        self._accent_buttons = {}
        accent_actual = (self.settings.get("accent_color") or DEFAULT_ACCENT).lower()
        # ¿El acento guardado es uno de los 6 predefinidos, o uno elegido a
        # mano la última vez? Si es "a mano", el botón de color libre debe
        # arrancar ya marcado y mostrando ese mismo tono, no en blanco.
        es_personalizado = accent_actual not in {c.lower() for c in ACCENT_PRESETS.values()}
        self._custom_color = accent_actual if es_personalizado else None
        self._custom_selected = es_personalizado

        for nombre, color in ACCENT_PRESETS.items():
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setFixedSize(28, 28)
            btn.setToolTip(nombre)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(
                f"QPushButton {{ background-color: {color}; border-radius: 14px; "
                f"border: 2px solid transparent; }}"
                f"QPushButton:checked {{ border: 2px solid white; }}"
            )
            if not es_personalizado and color.lower() == accent_actual:
                btn.setChecked(True)
            btn.clicked.connect(self._on_preset_accent_clicked)
            self._accent_group.addButton(btn)
            self._accent_buttons[btn] = color
            accent_row.addWidget(btn)

        # Botón de color libre: no forma parte de _accent_group (los
        # predefinidos son mutuamente excluyentes entre sí vía
        # QButtonGroup, pero este necesita su propio estado -- "elegido a
        # mano" o no -- que no encaja con ser "un botón más del grupo").
        self._custom_btn = QPushButton()
        self._custom_btn.setFixedSize(28, 28)
        self._custom_btn.setToolTip("Color personalizado…")
        self._custom_btn.setCursor(Qt.PointingHandCursor)
        self._custom_btn.clicked.connect(self._on_pick_custom_color)
        self._refresh_custom_btn_style()
        accent_row.addWidget(self._custom_btn)

        accent_row.addStretch(1)
        form_apariencia.addRow("Color de acento:", accent_row)
        content_layout.addWidget(panel_apariencia)

        # ---- VPN ----
        # Solo edición VIP con licencia activada de verdad. win.activated
        # también vale True en la build Free (ver ui.application.run_free,
        # que la arranca ya "activada" para desbloquear todo), así que
        # es_version_free hay que excluirlo aparte -- mismo criterio que
        # ya usa dialog_actions.py para "Ir a Descargas" en la paleta de
        # comandos.
        self._vpn_licensed = bool(getattr(parent, "activated", False)) and not bool(
            getattr(parent, "es_version_free", False)
        )
        if self._vpn_licensed:
            self._build_vpn_panel(content_layout)

        # ---- Perfil ----
        panel_perfil, form_perfil = _panel("Perfil")
        perfil_row = QHBoxLayout()
        self.perfil_combo = QComboBox()
        self._reload_perfil_combo(self.settings.get("active_profile", "Default"))
        nuevo_perfil_btn = QPushButton("+ Nuevo perfil…")
        nuevo_perfil_btn.clicked.connect(self._on_nuevo_perfil)
        duplicar_perfil_btn = QPushButton("Duplicar…")
        duplicar_perfil_btn.clicked.connect(self._on_duplicar_perfil)
        eliminar_perfil_btn = QPushButton("Eliminar")
        eliminar_perfil_btn.clicked.connect(self._on_eliminar_perfil)
        perfil_row.addWidget(self.perfil_combo, stretch=1)
        perfil_row.addWidget(nuevo_perfil_btn)
        perfil_row.addWidget(duplicar_perfil_btn)
        perfil_row.addWidget(eliminar_perfil_btn)
        form_perfil.addRow("Perfil activo:", perfil_row)
        perfil_aviso = QLabel(
            "Cada perfil tiene sus propios favoritos, historial, canales/emisoras "
            "añadidos a mano y grabaciones programadas. Cambiar de perfil pide "
            "reiniciar la aplicación para aplicarse del todo."
        )
        perfil_aviso.setWordWrap(True)
        perfil_aviso.setObjectName("dialogSubtitle")
        form_perfil.addRow(perfil_aviso)
        content_layout.addWidget(panel_perfil)

        content_layout.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setObjectName("primaryButton")
        buttons.button(QDialogButtonBox.Ok).setText("Guardar")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    @staticmethod
    def _fill_country_combo(combo: QComboBox, selected_code: str):
        for code, name in countries.COUNTRIES:
            combo.addItem(name, code)
        idx = combo.findData((selected_code or "ES").upper())
        combo.setCurrentIndex(idx if idx >= 0 else combo.findData("ES"))

    def _browse_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "Selecciona carpeta de grabaciones")
        if directory:
            self.rec_dir_input.setText(directory)

    # ---------- VPN ----------

    def _build_vpn_panel(self, content_layout: QVBoxLayout) -> None:
        """Sección VPN: conecta con la suscripción OpenVPN propia del
        usuario para acceder a listas públicas con restricción geográfica.
        La app no opera servidores VPN propios -- solo importa el .ovpn
        que ya trae el proveedor y pide a openvpn-gui.exe que conecte o
        desconecte ese perfil por nombre (ver core/vpn_client.py y
        core/vpn_profiles.py)."""
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
            content_layout.addWidget(panel_vpn)
            return

        self.vpn_profile_combo = QComboBox()
        form_vpn.addRow("Perfil:", self.vpn_profile_combo)

        self.vpn_status_label = QLabel()
        form_vpn.addRow("Estado:", self.vpn_status_label)

        vpn_row = QHBoxLayout()
        importar_btn = QPushButton("Importar perfil (.ovpn)…")
        importar_btn.clicked.connect(self._on_vpn_import)
        gratis_btn = QPushButton("Servidor gratuito (VPNGate)…")
        gratis_btn.clicked.connect(self._on_vpn_gate_pick)
        eliminar_btn = QPushButton("Eliminar")
        eliminar_btn.clicked.connect(self._on_vpn_delete)
        self.vpn_toggle_btn = QPushButton("Conectar")
        self.vpn_toggle_btn.clicked.connect(self._on_vpn_toggle)
        vpn_row.addWidget(importar_btn)
        vpn_row.addWidget(gratis_btn)
        vpn_row.addWidget(eliminar_btn)
        vpn_row.addWidget(self.vpn_toggle_btn)
        form_vpn.addRow(vpn_row)

        aviso = QLabel(
            "Importa el .ovpn de tu propia suscripción VPN, o elige un "
            "servidor gratuito de VPNGate sin necesitar ninguna cuenta. No "
            "hace falta permiso de administrador para conectar ni "
            "desconectar -- solo la primera vez, si tu usuario de Windows "
            "todavía no pertenece al grupo «OpenVPN Administrators», el "
            "propio instalador de OpenVPN puede añadirlo. El estado puede "
            "tardar unos segundos en reflejar el cambio."
        )
        aviso.setWordWrap(True)
        aviso.setObjectName("dialogSubtitle")
        form_vpn.addRow(aviso)

        content_layout.addWidget(panel_vpn)
        self._reload_vpn_combo()

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

    def _refresh_vpn_status(self) -> None:
        tunnel = self._current_vpn_tunnel()
        if not tunnel:
            self.vpn_status_label.setText("Sin perfiles guardados")
            self.vpn_toggle_btn.setEnabled(False)
            return
        self.vpn_toggle_btn.setEnabled(True)
        connected = vpn_client.status(tunnel)
        self.vpn_status_label.setText("Conectado" if connected else "Desconectado")
        self.vpn_toggle_btn.setText("Desconectar" if connected else "Conectar")

    def _on_vpn_import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Importar perfil VPN", "", "OpenVPN (*.ovpn)"
        )
        if not path:
            return
        nombre, ok = QInputDialog.getText(
            self, "Importar perfil VPN", "Nombre para este perfil (p. ej. el país):"
        )
        nombre = (nombre or "").strip()
        if not ok or not nombre:
            return
        try:
            vpn_profiles.import_profile(nombre, Path(path))
        except vpn_profiles.VpnProfileError as exc:
            QMessageBox.warning(self, "Importar perfil VPN", str(exc))
            return
        self._reload_vpn_combo(select_name=nombre)

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

    def _on_vpn_delete(self):
        nombre = self.vpn_profile_combo.currentText()
        if not nombre:
            return
        if QMessageBox.question(
            self, "Eliminar perfil VPN", f"¿Eliminar el perfil «{nombre}»?"
        ) != QMessageBox.Yes:
            return
        entry = vpn_profiles.get_profile(nombre)
        if entry and vpn_client.status(entry["tunnel"]):
            try:
                vpn_client.disconnect(entry["tunnel"])
            except vpn_client.VpnClientError as exc:
                QMessageBox.warning(
                    self, "Eliminar perfil VPN",
                    f"No se pudo desconectar el túnel antes de borrarlo: {exc}",
                )
                return
        vpn_profiles.delete_profile(nombre)
        self._reload_vpn_combo()

    def _on_vpn_toggle(self):
        tunnel = self._current_vpn_tunnel()
        if not tunnel:
            return
        entry = vpn_profiles.get_profile(self.vpn_profile_combo.currentText())
        connected = vpn_client.status(tunnel)
        self.vpn_toggle_btn.setEnabled(False)
        try:
            if connected:
                vpn_client.disconnect(tunnel)
            elif entry:
                vpn_client.connect(Path(entry["conf_path"]), tunnel)
        except vpn_client.VpnClientError as exc:
            QMessageBox.warning(self, "VPN", str(exc))
        finally:
            self.vpn_toggle_btn.setEnabled(True)
            self._refresh_vpn_status()

    # ---------- Color de acento ----------

    def _on_preset_accent_clicked(self):
        # Elegir un predefinido desmarca el color libre -- los dos son
        # alternativas, no se combinan.
        self._custom_selected = False
        self._refresh_custom_btn_style()

    def _on_pick_custom_color(self):
        inicial = QColor(self._custom_color or self.settings.get("accent_color") or DEFAULT_ACCENT)
        color = QColorDialog.getColor(inicial, self, "Elige un color de acento")
        if not color.isValid():
            return  # el usuario canceló el diálogo: no se toca nada
        self._custom_color = color.name()
        self._custom_selected = True
        # Elegir un color libre desmarca cualquier predefinido -- mismo
        # criterio que al revés en _on_preset_accent_clicked().
        checked = self._accent_group.checkedButton()
        if checked is not None:
            self._accent_group.setExclusive(False)
            checked.setChecked(False)
            self._accent_group.setExclusive(True)
        self._refresh_custom_btn_style()

    def _refresh_custom_btn_style(self):
        """
        Sin color elegido todavía: círculo neutro con un "+". Con uno
        elegido: círculo relleno de ese color, marcado con borde blanco
        solo si es la opción activa ahora mismo (el usuario puede haber
        vuelto a un predefinido después de probar uno personalizado, sin
        perder por eso el último color libre que había elegido).
        """
        if self._custom_color:
            fondo, texto = self._custom_color, ""
        else:
            fondo, texto = palette.BG_PANEL_ALT, "+"
        borde = "2px solid white" if self._custom_selected else "2px solid transparent"
        self._custom_btn.setText(texto)
        self._custom_btn.setStyleSheet(
            f"QPushButton {{ background-color: {fondo}; border-radius: 14px; "
            f"border: {borde}; color: white; font-weight: 700; }}"
        )

    def _reload_perfil_combo(self, seleccionar: str):
        self.perfil_combo.blockSignals(True)
        self.perfil_combo.clear()
        for nombre in cfg.list_profiles():
            self.perfil_combo.addItem(nombre, nombre)
        idx = self.perfil_combo.findData(seleccionar)
        self.perfil_combo.setCurrentIndex(idx if idx >= 0 else 0)
        self.perfil_combo.blockSignals(False)

    def _on_nuevo_perfil(self):
        nombre, ok = QInputDialog.getText(self, "Nuevo perfil", "Nombre del perfil nuevo:")
        nombre = (nombre or "").strip()
        if not ok or not nombre:
            return
        if nombre in cfg.list_profiles():
            QMessageBox.information(self, "Nuevo perfil", "Ya existe un perfil con ese nombre.")
            return
        try:
            cfg.create_profile(nombre)
        except ValueError:
            QMessageBox.warning(
                self, "Nuevo perfil",
                "Ese nombre no es válido (no puede contener \\ / : * ? \" < > | ni ser \".\" o \"..\").",
            )
            return
        self._reload_perfil_combo(nombre)

    def _on_duplicar_perfil(self):
        source = self.perfil_combo.currentData() or "Default"
        name, accepted = QInputDialog.getText(self, "Duplicar perfil", "Nombre de la copia:")
        if not accepted or not name.strip():
            return
        try:
            cfg.duplicate_profile(source, name)
        except ValueError as exc:
            QMessageBox.warning(self, "Duplicar perfil", str(exc))
            return
        self._reload_perfil_combo(name.strip())

    def _on_eliminar_perfil(self):
        name = self.perfil_combo.currentData() or "Default"
        if name == "Default":
            QMessageBox.information(self, "Eliminar perfil", "El perfil Default no se puede eliminar.")
            return
        if QMessageBox.question(
            self, "Eliminar perfil", f"¿Eliminar el perfil «{name}» y todos sus datos?"
        ) != QMessageBox.Yes:
            return
        cfg.delete_profile(name)
        self._reload_perfil_combo("Default")

    def get_settings(self) -> dict:
        self.settings["tv_country_code"] = self.tv_country_combo.currentData()
        self.settings["tv_playlist_url"] = self.tv_url_input.text().strip()
        self.settings["radio_country_code"] = self.radio_country_combo.currentData()
        self.settings["epg_url"] = self.epg_input.text().strip()
        self.settings["recordings_dir"] = self.rec_dir_input.text().strip() or self.settings.get("recordings_dir")
        self.settings["theme_mode"] = self.theme_combo.currentData() or "dark"
        self.settings["catalog_card_size"] = self.card_size_combo.currentData() or 168
        self.settings["resume_last_stream"] = self.resume_last_check.isChecked()
        self.settings["fullscreen_autohide_ui"] = self.fullscreen_autohide_check.isChecked()
        self.settings["automatic_backups_enabled"] = self.auto_backup_check.isChecked()
        self.settings["automatic_backup_interval_days"] = (
            self.backup_interval_combo.currentData() or 1
        )
        self.settings["automatic_backup_retention"] = (
            self.backup_retention_combo.currentData() or 7
        )
        self.settings["automatic_stream_diagnostics"] = (
            self.auto_diagnostics_check.isChecked()
        )
        self.settings["automatic_update_check"] = self.auto_update_check_check.isChecked()
        if self._custom_selected and self._custom_color:
            self.settings["accent_color"] = self._custom_color
        else:
            boton_marcado = self._accent_group.checkedButton()
            if boton_marcado is not None:
                self.settings["accent_color"] = self._accent_buttons[boton_marcado]
        self.settings["active_profile"] = self.perfil_combo.currentData() or "Default"
        return self.settings
