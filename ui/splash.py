"""
Banner de arranque de TDT & Radio VIP.

Muestra el aviso freeware, el hardware ID del PC (para que el usuario
te lo mande y tú generes el código) y un campo de activación.
En modo freeware solo están disponibles TV y radio.
En modo activado todas las funciones están desbloqueadas.
"""
from urllib.parse import quote

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QVBoxLayout,
)

from core.license import generate_hardware_id, is_activated, save_activation
from core.config import (
    APP_VERSION, SUPPORT_EMAIL, get_current_profile, list_profiles,
    load_settings, save_settings, set_current_profile,
)
from ui import palette
from ui.visual import set_surface, set_variant, set_visual_state


class _HWWorker(QThread):
    """Obtiene el hardware ID en segundo plano (las llamadas a WMIC tardan)."""
    done = Signal(str)

    def run(self):
        self.done.emit(generate_hardware_id())


class SplashDialog(QDialog):
    """
    Diálogo de bienvenida / activación.

    Resultado:
      self.activated  -> bool: True si el usuario tiene licencia válida
    """

    def __init__(self, parent=None, show_profile_selector: bool = True):
        super().__init__(parent)
        set_surface(self, "dialog")
        self.setWindowTitle("TDT & Radio VIP  —  Bienvenido")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setMinimumWidth(780)
        self.setMinimumHeight(650)

        self.activated = False
        self._hw_id = ""
        # Al reabrir el diálogo desde Configuración > Activar VIP… la sesión
        # ya está en marcha con los datos de un perfil cargados: cambiarlo
        # aquí no tendría efecto real, así que el selector solo se ofrece
        # en el splash de arranque.
        self._show_profile_selector = show_profile_selector
        self._build_ui()

        # Lanzar la obtención del hardware ID en segundo plano.
        self._worker = _HWWorker(self)
        self._worker.done.connect(self._on_hw_ready)
        self._worker.start()

    # ── UI ──────────────────────────────────────────────────────────────────

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(34, 26, 34, 24)
        lay.setSpacing(12)

        # Cabecera
        titulo = QLabel("TDT & Radio VIP")
        titulo.setObjectName("titulo")
        titulo.setAlignment(Qt.AlignCenter)
        lay.addWidget(titulo)

        version = QLabel(f"Versión {APP_VERSION}  ·  Coder By X@R")
        version.setObjectName("version")
        version.setAlignment(Qt.AlignCenter)
        lay.addWidget(version)

        intro = QLabel(
            "Disfruta de televisión y radio desde el primer momento. "
            "Activa VIP para grabar, convertir, editar, descargar y enviar contenido a tu TV."
        )
        intro.setObjectName("dialogSubtitle")
        intro.setAlignment(Qt.AlignCenter)
        intro.setWordWrap(True)
        lay.addWidget(intro)

        def feature_card(title, badge, features, featured=False):
            card = QFrame()
            card.setObjectName("licenseVipCard" if featured else "licenseFreeCard")
            border = palette.ACCENT if featured else palette.BORDER
            background = palette.BG_PANEL_ALT if featured else palette.BG_PANEL
            # Ojo con las llaves: solo los f-strings convierten "{{" en "{".
            # El fragmento central iba antes en un string normal con "}}"
            # literal, lo que rompía el parseo del QSS entero ("Could not
            # parse stylesheet") y dejaba las tarjetas sin fondo ni borde.
            card.setStyleSheet(
                f"QFrame#{card.objectName()} {{ background: {background}; border: 1px solid {border}; "
                "border-radius: 14px; } "
                f"QFrame#{card.objectName()} QLabel {{ border: none; background: transparent; }}"
            )
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(18, 15, 18, 15)
            card_layout.setSpacing(6)
            header = QHBoxLayout()
            name = QLabel(title)
            name.setStyleSheet(f"font-size: 13pt; font-weight: 700; color: {palette.TEXT_PRIMARY};")
            header.addWidget(name)
            header.addStretch(1)
            tag = QLabel(badge)
            tag.setStyleSheet(
                f"color: {palette.BG_ROOT if featured else palette.TEXT_MUTED}; "
                f"background: {palette.ACCENT if featured else palette.BG_ROOT}; "
                "border-radius: 8px; padding: 3px 8px; font-weight: 600;"
            )
            header.addWidget(tag)
            card_layout.addLayout(header)
            for feature in features:
                label = QLabel(f"✓  {feature}")
                label.setStyleSheet(
                    f"color: {palette.ACCENT_LIGHTER if featured else palette.TEXT_MUTED}; font-size: 8.5pt;"
                )
                card_layout.addWidget(label)
            card_layout.addStretch(1)
            return card

        plans = QHBoxLayout()
        plans.setSpacing(14)
        self.free_card = feature_card("Modo gratuito", "FREEWARE", [
            "TV y radio online", "Favoritos, historial y EPG", "Perfiles y listas propias",
            "Mini reproductor y búsqueda universal", "Editor de listas M3U",
        ])
        self.vip_card = feature_card("TDT & Radio VIP", "LICENCIA", [
            "Descargas de vídeo y audio", "Conversor de audio a MP3",
            "Editor MP3, recorte y etiquetas", "Soulseek y torrents integrados",
            "Grabaciones y programación", "Chromecast, Google Cast y DLNA",
        ], featured=True)
        plans.addWidget(self.free_card, 1)
        plans.addWidget(self.vip_card, 1)
        lay.addLayout(plans)

        # Hardware ID
        activation_title = QLabel("ACTIVAR FUNCIONES VIP")
        activation_title.setObjectName("dialogSectionLabel")
        activation_title.setAlignment(Qt.AlignCenter)
        lay.addWidget(activation_title)
        # El texto pasa a enlace mailto en _on_hw_ready, cuando ya se puede
        # incluir el ID en el propio correo.
        self.hw_label = QLabel(
            f"Envía este ID a <b style='color:{palette.ACCENT_LIGHTER};'>{SUPPORT_EMAIL}</b> "
            "para recibir una licencia válida para este equipo."
        )
        self.hw_label.setObjectName("hw_label")
        self.hw_label.setAlignment(Qt.AlignCenter)
        self.hw_label.setWordWrap(True)
        self.hw_label.setOpenExternalLinks(True)
        lay.addWidget(self.hw_label)

        self.hw_display = QLabel("Calculando…")
        self.hw_display.setObjectName("hw_id")
        self.hw_display.setAlignment(Qt.AlignCenter)
        self.hw_display.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.hw_display.setCursor(Qt.IBeamCursor)

        self.copy_btn = QPushButton("Copiar ID")
        set_variant(self.copy_btn, "secondary")
        self.copy_btn.setToolTip("Copiar el ID del equipo al portapapeles")
        self.copy_btn.setEnabled(False)  # Hasta tener el hardware ID
        self.copy_btn.clicked.connect(self._on_copiar_id)

        hw_row = QHBoxLayout()
        hw_row.setSpacing(10)
        hw_row.addStretch(1)
        hw_row.addWidget(self.hw_display)
        hw_row.addWidget(self.copy_btn)
        hw_row.addStretch(1)
        lay.addLayout(hw_row)

        # Campo de código
        self.codigo_input = QLineEdit()
        self.codigo_input.setObjectName("codigo_input")
        self.codigo_input.setPlaceholderText("Pega aquí la licencia V2 generada para este equipo")
        self.codigo_input.setAlignment(Qt.AlignCenter)
        # Las licencias V2 son firmas RSA-2048 en hexadecimal: "V2." +
        # 512 caracteres. El límite antiguo de 24 truncaba silenciosamente
        # todo lo pegado y hacía que cualquier licencia nueva pareciera inválida.
        self.codigo_input.setMaxLength(515)
        self.codigo_input.returnPressed.connect(self._on_activar)
        lay.addWidget(self.codigo_input)

        self.activar_btn = QPushButton("Activar")
        self.activar_btn.setObjectName("btn_activar")
        set_variant(self.activar_btn, "primary")
        self.activar_btn.setMinimumHeight(40)
        self.activar_btn.clicked.connect(self._on_activar)
        self.activar_btn.setEnabled(False)  # Deshabilitado hasta tener el hardware ID

        self.continuar_btn = QPushButton("Continuar en modo gratuito →")
        self.continuar_btn.setObjectName("btn_continuar")
        set_variant(self.continuar_btn, "secondary")
        self.continuar_btn.setMinimumHeight(40)
        self.continuar_btn.setToolTip(
            "Se recordará tu elección y la app entrará directa en los próximos "
            "arranques. Podrás activar VIP cuando quieras desde "
            "Configuración > Activar VIP…"
        )
        self.continuar_btn.clicked.connect(self._on_continuar)

        botones = QHBoxLayout()
        botones.setSpacing(12)
        botones.addWidget(self.activar_btn)
        botones.addWidget(self.continuar_btn)
        lay.addLayout(botones)

        # Selector de perfil: solo en el splash de arranque y solo si el
        # usuario ha creado perfiles además del predeterminado — con uno
        # solo, un desplegable de una única opción es ruido.
        self.profile_combo = None
        profiles = list_profiles() if self._show_profile_selector else []
        if len(profiles) > 1:
            self.profile_combo = QComboBox()
            self.profile_combo.addItems(profiles)
            self.profile_combo.setCurrentText(get_current_profile())
            self.profile_combo.setToolTip(
                "Perfil cuyas listas, favoritos e historial se cargarán al entrar"
            )
            profile_row = QHBoxLayout()
            profile_row.setSpacing(8)
            profile_row.addStretch(1)
            profile_label = QLabel("Entrar con el perfil:")
            profile_label.setObjectName("hw_label")
            profile_row.addWidget(profile_label)
            profile_row.addWidget(self.profile_combo)
            profile_row.addStretch(1)
            lay.addLayout(profile_row)

        self.estado_label = QLabel("")
        self.estado_label.setObjectName("splashStatus")
        self.estado_label.setAlignment(Qt.AlignCenter)
        set_visual_state(self.estado_label, "default")
        lay.addWidget(self.estado_label)

    # ── Slots ────────────────────────────────────────────────────────────────

    def _on_hw_ready(self, hw_id: str):
        self._hw_id = hw_id
        self.hw_display.setText(hw_id)
        self.activar_btn.setEnabled(True)
        self.copy_btn.setEnabled(True)

        # Con el ID ya calculado, el correo de soporte puede llevarlo puesto:
        # un clic abre el cliente de correo con asunto y cuerpo rellenos.
        subject = quote(f"Licencia TDT & Radio VIP {APP_VERSION}")
        body = quote(f"Hola,\n\nQuiero activar TDT & Radio VIP.\nID de mi equipo: {hw_id}\n")
        self.hw_label.setText(
            "Envía este ID a "
            f"<a style='color:{palette.ACCENT_LIGHTER}; font-weight:600;' "
            f"href='mailto:{SUPPORT_EMAIL}?subject={subject}&body={body}'>{SUPPORT_EMAIL}</a> "
            "para recibir una licencia válida para este equipo."
        )

        # Si ya estaba activado en este PC, saltarse el splash directamente.
        if is_activated():
            self.activated = True
            self.accept()

    def _on_copiar_id(self):
        if not self._hw_id:
            return
        QApplication.clipboard().setText(self._hw_id)
        set_visual_state(self.estado_label, "active")
        self.estado_label.setText("✔  ID copiado al portapapeles.")

    def _on_activar(self):
        codigo = self.codigo_input.text().strip()
        if not codigo:
            return
        if not self._hw_id:
            self.estado_label.setText("Espera a que se calcule el ID del equipo.")
            return

        if save_activation(codigo):
            self.activated = True
            set_visual_state(self.estado_label, "active")
            self.estado_label.setText("✔  Activación correcta. ¡Gracias!")
            self.activar_btn.setEnabled(False)
            self.continuar_btn.setText("Entrar →")
            self.continuar_btn.setObjectName("btn_activar")
            set_variant(self.continuar_btn, "primary")
        else:
            set_visual_state(self.estado_label, "error")
            self.estado_label.setText(
                "✖  Código no válido para este equipo. "
                "Comprueba que lo has introducido correctamente."
            )

    def _on_continuar(self):
        if self.profile_combo is not None:
            elegido = self.profile_combo.currentText()
            if elegido != get_current_profile():
                set_current_profile(elegido)
        if not self.activated:
            # Recordar la elección de modo gratuito para no volver a mostrar
            # el splash en cada arranque (ver ui/application.run_vip). Se
            # puede reabrir desde Configuración > Activar VIP….
            settings = load_settings()
            if not settings.get("splash_free_seen"):
                settings["splash_free_seen"] = True
                save_settings(settings)
        self.accept()
