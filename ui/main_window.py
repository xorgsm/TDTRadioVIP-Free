"""
Ventana principal de TDT & Radio VIP — interfaz moderna.
Coder By X@R
"""
import os
from pathlib import Path
from typing import Optional

from PySide6.QtCore import (
    QEasingCurve, QEvent, QPropertyAnimation, QSize, Qt, QTimer,
)
from PySide6.QtGui import QAction, QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QBoxLayout, QButtonGroup, QComboBox, QDialog, QFrame,
    QGraphicsDropShadowEffect, QGraphicsOpacityEffect, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QMainWindow, QMenu, QMenuBar, QMessageBox,
    QPushButton, QScrollArea, QSizeGrip, QSizePolicy, QSlider, QSplitter, QStackedWidget,
    QToolButton, QVBoxLayout, QWidget,
)

from ui import icons as app_icons
from core import config as cfg
from core.logger import log_file_path
from core import channels as tv_channels
from core import favorites as fav_store
from core import history as hist_store
from core import recorder as rec_module
from core import recording_schedule
from core import backup as backup_module
from core import updater
from player.vlc_player import VLCPlayer
from ui.dialogs import SettingsDialog
from ui.equalizer_dialog import EqualizerDialog
from ui.style import ACCENT_PRESETS, build_style
from ui.toast import show_toast
from ui.visual import set_variant
from ui import palette
from ui.channel_menu_controller import ChannelMenuController
from ui.catalog_load_controller import CatalogLoadController
from ui.home_controller import HomeController
from ui.channel_lists_controller import ChannelListsController
from ui.channel_model import ChannelListModel, ChannelListView
from ui.carousel import Carousel
from ui.command_palette import CommandPalette
from ui.epg_controller import EpgController
from ui.fetch_worker import (
    FetchWorker,
    process_events_during_shutdown,
    shutdown_workers,
)
from ui.groups_sidebar import GroupsSidebar
from ui.library_controller import LibraryController
from ui.library_sidebar import LibrarySidebar
from ui.onboarding import OnboardingDialog
from ui.mosaic_view import MosaicView
from ui.recurring_dialog import RecurringRecordingsDialog
from ui.scheduled_recordings_dialog import ScheduledRecordingsDialog
from ui.stats_dialog import StatsDialog
from ui.stream_diagnostics_dialog import StreamDiagnosticsDialog
from ui.tray_controller import TrayReminderController
from ui.update_check_controller import UpdateCheckController
from ui.media_keys import (
    HOTKEY_NEXT, HOTKEY_PLAY_PAUSE, HOTKEY_PREV, HOTKEY_STOP, SystemMediaKeys,
)
from ui.playback_controller import PlaybackController
from ui.queue_controller import QueueController
from ui.window_chrome import WindowChrome
from ui.taskbar_controls import (
    BTN_NEXT, BTN_PLAY, BTN_PREV, BTN_STOP, BTN_MUTE, TaskbarControls, set_native_window_icon,
)
from ui.radio_hero import RadioHeroWidget
from ui.widgets import ChannelDelegate, ChannelGridDelegate, LogoLoader

NAV_HOME, NAV_TV, NAV_RADIO, NAV_FAV, NAV_HIST = range(5)
# Ancho del riel lateral (ver _build_nav_rail). Se comparte con
# _build_title_bar para que el menu (Archivo/Configuracion/Ayuda) arranque
# alineado con el panel de contenido -- antes quedaba pegado al nombre de
# la app y no coincidia con el borde de "Inicio" ni con el resto de la
# ventana.
NAV_RAIL_WIDTH = 180
# Títulos cortos a propósito: "Televisión (TDT)" y "Radio online" se
# comían casi todo el ancho disponible en la barra superior (título +
# botón Guía + filtro de categoría + buscador en una sola fila), dejando
# el propio título cortado en ventanas no muy anchas. La aclaración "TDT"
# y "online" ya la da el icono/tooltip del riel, no hace falta repetirla aquí.
SECTION_TITLES = {
    NAV_HOME: "Inicio",
    NAV_TV: "Televisión",
    NAV_RADIO: "Radio",
    NAV_FAV: "Favoritos",
    NAV_HIST: "Historial",
}
# Mismo color por sección que ya usan los iconos del riel lateral, para
# poder pintar con él también el título de la barra superior (más
# acentos de color coherentes con lo que ya existía, no colores nuevos
# sueltos). Se define aquí, a nivel de módulo, para que tanto
# _build_nav_rail() como _on_nav_changed() lean del mismo sitio.
SECTION_COLORS = {
    NAV_HOME: ACCENT_PRESETS["Verde"],
    NAV_TV: palette.ACCENT_INFO,
    NAV_RADIO: palette.ACCENT_CATEGORY_ORANGE,
    NAV_FAV: palette.ACCENT,
    NAV_HIST: ACCENT_PRESETS["Violeta"],
}
SECTION_VARIANTS = {
    NAV_HOME: "success",
    NAV_TV: "tv",
    NAV_RADIO: "radio",
    NAV_FAV: "primary",
    NAV_HIST: "sleep",
}
DEFAULT_DOWNLOADS_DIRNAME = "TDT Radio VIP"


class MainWindow(QMainWindow):
    def __init__(self, activated: bool = False, es_version_free: bool = False):
        super().__init__()
        self._is_closing = False
        self.activated = activated
        # Edición Free: main_free.py pasa activated=True y es_version_free=True
        # para abrir la reproducción de TV/radio directamente.
        self.es_version_free = es_version_free
        self.setObjectName("mainWindowRoot")
        self.setWindowTitle(f"TDT & Radio VIP {cfg.APP_VERSION} — Coder By X@R")
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        # El LibrarySidebar (Recientes/Playlists) arranca OCULTO a propósito
        # (ver _build_nav_rail/_toggle_library_sidebar): con él visible por
        # defecto la ventana necesitaba 210px de más, y en pantallas más
        # pequeñas la app se abría demasiado grande y con la barra de
        # controles y la barra superior apretadas. Quien lo quiera, lo
        # activa con el botón de biblioteca del riel — sigue disponible,
        # solo que no ocupa sitio si no se pide.
        # El lienzo de Pencil se ha planteado a 1280 px: arrancar algo más
        # cerca de esa proporción deja respirar el catálogo, la emisión y
        # la navegación textual, sin obligar a maximizar la ventana.
        self.resize(1280, 760)
        # 1000px de mínimo era más de lo que la propia interfaz necesita
        # (riel 76 + lista de canales 420 + panel de vídeo 300 + divisor
        # ≈ 800-820px reales): al ser mayor que la mitad del ancho de
        # muchas pantallas (p. ej. 1920px ÷ 2 = 960), Windows no dejaba
        # encajar la ventana en la mitad de la pantalla ni al arrastrarla
        # al borde izquierdo -- se quedaba "a medias" (bug reportado).
        # 900 sigue teniendo margen sobre el mínimo real de la interfaz.
        # Los tres paneles pueden coexistir en una ventana estrecha. Antes
        # sus mínimos sumaban casi todo el ancho de la pantalla y Qt acababa
        # recortando el panel central en vez de dejar al splitter repartirlo.
        self.setMinimumSize(860, 580)

        self.settings = cfg.load_settings()
        self.favorites = fav_store.load_favorites()
        self.history = hist_store.load_history()
        self.epg_guide = {}
        self.logo_loader = LogoLoader()

        self.tv_channels_data = []
        self.radio_stations_data = []
        # Grupos de TV marcados en GroupsSidebar (panel lateral de
        # categorías, ver ui/groups_sidebar.py). None = sin filtro ("Todos");
        # un set vacío no se usa -- deseleccionar todo cae a None (ver
        # GroupsSidebar._select_rows_or_all).
        self._tv_sidebar_groups = None

        self.current_type: Optional[str] = None
        self.current_name: Optional[str] = None
        self.current_url: Optional[str] = None
        self.current_logo: str = ""
        self._current_alternate_urls = []
        self.current_tvg_id: str = ""
        self._playback_failed = False
        self._playback_token = 0
        self._active_list = None
        self._active_row = -1
        self._auto_skip_count = 0
        self._fade_anim = None
        self._current_nav_id = NAV_HOME

        self.downloads_dir = self.settings.get("downloads_dir") or str(
            Path.home() / "Downloads" / DEFAULT_DOWNLOADS_DIRNAME
        )
        self.recordings_dir = self.settings.get("recordings_dir") or self.downloads_dir
        self.recorder = rec_module.Recorder(self.recordings_dir)
        self.recordings_dir = str(self.recorder.output_dir)
        # Grabación programada actualmente en curso (ScheduledRecording),
        # o None si self.recorder está libre o grabando algo manual. Sirve
        # para que _check_scheduled_recordings() sepa cuál cerrar cuando
        # llegue su hora de fin, y para que toggle_recording() (parada
        # manual, ver PlaybackController) también limpie la programación
        # si el usuario para a mano una grabación que en realidad venía de
        # la EPG.
        self._scheduled_recording_active: Optional[recording_schedule.ScheduledRecording] = None
        self._player_fullscreen = False
        self._was_maximized_before_fs = False
        self._pseudo_maximizado = False
        self._geometria_normal = None
        self._pip_mode = False
        self._geometria_antes_pip = None
        # Preferencia persistente (no de "esta reproducción"): se aplica
        # cada vez que se sintoniza un canal de TV -- ver
        # PlaybackController.play()/_apply_audio_only_state().
        self._audio_only_tv = self.settings.get("audio_only_tv", False)
        self._taskbar = TaskbarControls()
        self._background_diagnostics_started = False
        self._native_icon_applied = False

        # Creado ANTES de _build_ui(): la construcción de la interfaz conecta
        # varias señales (botones de reproducción, temporizador de apagado...)
        # directamente a métodos de este controlador.
        self.playback = PlaybackController(self)
        self.window_chrome = WindowChrome(self)
        self.lists = ChannelListsController(self)
        self.queue = QueueController(self)
        self.epg = EpgController(self)
        self.library = LibraryController(self)
        self.tray = TrayReminderController(self)
        self.catalog = CatalogLoadController(self)
        self.updates = UpdateCheckController(self)
        self.home = HomeController(self)
        self.channel_menu = ChannelMenuController(self)

        self._build_ui()
        self._registrar_atajos()

        # Teclas multimedia del teclado (play/pausa, siguiente, anterior,
        # detener) funcionando en segundo plano, no solo con la ventana en
        # foco. Se registran aquí porque no dependen del HWND (a diferencia
        # del icono nativo / botones de la barra de tareas en showEvent):
        # RegisterHotKey con hWnd=None no necesita que la ventana ya esté
        # creada a nivel de Win32.
        self._media_keys = SystemMediaKeys()
        self._media_keys.bind(HOTKEY_PLAY_PAUSE, self.playback.toggle_play)
        self._media_keys.bind(HOTKEY_STOP, self.playback.stop_playback)
        self._media_keys.bind(HOTKEY_NEXT, self.playback.play_next)
        self._media_keys.bind(HOTKEY_PREV, self.playback.play_prev)
        self._media_keys.start()

        self.catalog.load_tv_channels()
        self.catalog.load_radio_stations()
        self.lists.refresh_favorites_tab()
        self.lists.refresh_history_tab()
        if self.settings.get("epg_url"):
            self.epg.load()

        self.tray.setup()
        if self.settings.get("automatic_backups_enabled", True):
            QTimer.singleShot(1500, self._run_automatic_backup)
        if self.settings.get("automatic_update_check", True):
            QTimer.singleShot(5000, self._check_update_automatically)
        if self.settings.get("resume_last_stream", False):
            QTimer.singleShot(2200, self._resume_last_stream)

        if not self.player.disponible:
            # Antes esto reventaba en el arranque con un error críptico. Ahora
            # la app abre igual (descargas, listas, favoritos siguen usables)
            # y se explica qué falta.
            QTimer.singleShot(300, self._avisar_vlc_no_disponible)

        if not self.settings.get("onboarding_shown"):
            # Con un pequeño retraso, para que se vea primero la ventana
            # principal ya construida detrás en vez de un diálogo modal
            # tapándolo todo desde el primer frame.
            QTimer.singleShot(500, self._mostrar_bienvenida)

    def _mostrar_bienvenida(self):
        OnboardingDialog(self).exec()
        self.settings["onboarding_shown"] = True
        if not cfg.save_settings(self.settings):
            QMessageBox.warning(
                self,
                "No se pudieron guardar los ajustes",
                "No se pudieron guardar los ajustes. Inténtalo de nuevo.",
            )

    # _setup_tray_and_reminders / _check_epg_reminders / _check_scheduled_recordings /
    # _check_scheduled_recording_alive / _on_tray_message_clicked viven ahora en
    # ui.tray_controller.TrayReminderController (self.tray).

    def _avisar_vlc_no_disponible(self):
        QMessageBox.warning(
            self,
            "Motor de vídeo no disponible",
            f"{self.player.motivo_no_disponible()}\n\n"
            "La reproducción de TV y radio no funcionará. El resto de la "
            "aplicación (descargas, listas y favoritos) sigue disponible.",
        )
        self.statusBar().showMessage("VLC no disponible: la reproducción está desactivada.")

    # ---------- Construcción de la interfaz ----------

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("appSurface")
        raiz_v = QVBoxLayout(central)
        raiz_v.setContentsMargins(0, 0, 0, 0)
        raiz_v.setSpacing(0)

        self.title_bar = self._build_title_bar()
        raiz_v.addWidget(self.title_bar)

        cuerpo = QWidget()
        root = QHBoxLayout(cuerpo)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.nav_rail = self._build_nav_rail()
        root.addWidget(self.nav_rail)

        # Sidebar de biblioteca (Recientes + Playlists = carpetas de
        # favoritos), estilo Spotify: panel aditivo entre el riel de
        # iconos y el contenido principal, colapsable con el botón de
        # abajo del todo en el riel. No sustituye a las pestañas de
        # Favoritos/Historial -- es un atajo hacia ellas.
        self.library_sidebar = LibrarySidebar(self, self._open_favorites_folder)
        self.library_sidebar.setVisible(False)
        root.addWidget(self.library_sidebar)
        # Fondo vacío del sidebar (y el hueco bajo las entradas de
        # Recientes/Playlists) también arrastra la ventana, igual que la
        # barra de título -- ver WindowChrome.event_filter(). Con este
        # panel abierto ocupa buena parte de la altura de la ventana, y
        # antes la única zona de arrastre era la franja fina de arriba.
        self.library_sidebar.installEventFilter(self)
        self.library_sidebar.recent_list.viewport().installEventFilter(self)
        self.library_sidebar.playlists_list.viewport().installEventFilter(self)

        # Panel de grupos/categorías de TV (ver ui/groups_sidebar.py) --
        # mismo patrón que LibrarySidebar arriba, pero solo tiene sentido
        # durante la sección de Televisión: su visibilidad se controla en
        # _on_nav_changed(), no con un botón propio en el riel.
        self.groups_sidebar = GroupsSidebar(self._on_groups_sidebar_changed, self.channel_menu.delete_tv_groups)
        self.groups_sidebar.setVisible(False)
        root.addWidget(self.groups_sidebar)

        content = QVBoxLayout()
        content.setContentsMargins(16, 18, 12, 16)
        content.setSpacing(16)
        content.addLayout(self._build_top_bar())
        content.addWidget(self._build_content_stack(), stretch=1)

        # Se aplica después de crear las listas: el botón vive en la barra
        # superior, que se construye antes que el QStackedWidget.
        self.tv_view_toggle.setChecked(bool(self.settings.get("catalog_grid_view", False)))

        # setChecked(True) sobre el botón de Inicio (más arriba, en
        # _build_nav_rail) no dispara idClicked por sí solo — solo lo hace
        # un clic real del usuario. Sin esto, la portada se abriría vacía
        # hasta que el usuario cambiara de sección y volviera a Inicio.
        self._on_nav_changed(NAV_HOME)

        self.content_widget = QWidget()
        self.content_widget.setLayout(content)
        # Mínimo real: por debajo de esto, el título + filtro de categoría +
        # buscador de la barra superior no caben y se cortan (era el bug del
        # buscador cortado). El splitter no puede arrastrarse más allá.
        self.content_widget.setMinimumWidth(330)

        player_panel = self._build_player_panel()
        # La fila de controles ya no crece con el número de funciones: las
        # cinco acciones secundarias (pistas, pantalla completa, PiP,
        # temporizador, cola) que antes tenían un botón circular propio y
        # obligaban a un mínimo de 430px ahora viven en un único botón
        # "Más opciones" (ver _build_now_playing_bar). 300px sigue dejando
        # margen de sobra para el resto de la fila (favoritos, cast,
        # detener, play, grabar, silenciar, más) sin que se solape nada, y
        # permite que la ventana encaje en la mitad de pantallas normales
        # en vez del mínimo inflado de antes.
        # El reproductor necesita un ancho protegido: en la captura, al
        # arrastrar el divisor el catálogo se quedaba con casi todo el
        # espacio y el vídeo/"Ahora suena" quedaba reducido a una franja.
        player_panel.setMinimumWidth(300)

        # Antes el reparto entre la lista y el vídeo era un stretch fijo
        # (3:2) dentro del QHBoxLayout: no había forma de ajustarlo a mano.
        # Con un splitter, el usuario arrastra la línea divisoria él mismo,
        # y los anchos mínimos de arriba evitan que se coma ninguno de los
        # dos lados por accidente.
        self.main_splitter = QSplitter(Qt.Horizontal)
        self.main_splitter.setObjectName("mainSplitter")
        self.main_splitter.setChildrenCollapsible(False)
        self.main_splitter.addWidget(self.content_widget)
        self.main_splitter.addWidget(player_panel)
        self.main_splitter.setStretchFactor(0, 3)
        self.main_splitter.setStretchFactor(1, 2)
        self.main_splitter.setSizes([560, 500])
        root.addWidget(self.main_splitter, stretch=1)
        raiz_v.addWidget(cuerpo, stretch=1)

        self.setCentralWidget(central)
        # Los filtros de adaptación se activan solo cuando todos los widgets
        # que consulta eventFilter ya existen; durante la construcción Qt
        # también emite Resize y podría entrar antes de crear player_frame.
        self.now_playing_bar.installEventFilter(self)
        self._home_viewport.installEventFilter(self)
        self.statusBar().addPermanentWidget(QSizeGrip(self))
        self.statusBar().showMessage("Listo.")
        self.player.set_volume(self.volume_slider.value())

    def _build_nav_rail(self) -> QWidget:
        rail = QWidget()
        rail.setObjectName("navRail")
        # Pensado como una columna de catálogo legible, no un riel de
        # iconos crípticos. Los textos hacen que las áreas sean reconocibles
        # de un vistazo y siguen conservando los iconos como anclas visuales.
        rail.setFixedWidth(NAV_RAIL_WIDTH)
        layout = QVBoxLayout(rail)
        layout.setContentsMargins(12, 24, 12, 14)
        layout.setSpacing(5)

        # La marca y la versión ya no se repiten aquí -- viven una sola vez,
        # más grandes, en la barra de título (_build_title_bar, titleBrand/
        # titleVersion). EXPLORAR pasa a ser lo primero que se ve del riel.
        nav_caption = QLabel("EXPLORAR")
        nav_caption.setObjectName("navCaption")
        layout.addWidget(nav_caption)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)

        # Cada icono conserva el color de su sección como señal secundaria;
        # el estado activo usa una superficie común para no convertir toda
        # la navegación en un bloque de color distinto en cada pantalla.
        nav_icon_builders = {
            NAV_HOME: (app_icons.icon_home, SECTION_COLORS[NAV_HOME]),
            NAV_TV: (app_icons.icon_tv, SECTION_COLORS[NAV_TV]),
            NAV_RADIO: (app_icons.icon_radio, SECTION_COLORS[NAV_RADIO]),
            NAV_FAV: (app_icons.icon_favorite, SECTION_COLORS[NAV_FAV]),
            NAV_HIST: (app_icons.icon_history, SECTION_COLORS[NAV_HIST]),
        }
        nav_defs = [
            (NAV_HOME, "Inicio"),
            (NAV_TV, "Televisión"),
            (NAV_RADIO, "Radio"),
            (NAV_FAV, "Favoritos"),
            (NAV_HIST, "Historial"),
        ]
        for nav_id, tooltip in nav_defs:
            btn = QToolButton()
            btn.setObjectName("navButton")
            set_variant(btn, SECTION_VARIANTS[nav_id])
            btn.setToolTip(tooltip)
            btn.setText(tooltip)
            btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            builder, inactive_color = nav_icon_builders[nav_id]
            btn.setIconSize(QSize(22, 22))
            btn.setIcon(builder(inactive_color, size=24))
            btn.toggled.connect(
                lambda _checked, b=btn, f=builder, c=inactive_color: b.setIcon(
                    f(c, size=24)
                )
            )
            self.nav_group.addButton(btn, nav_id)
            layout.addWidget(btn)

        self.nav_group.button(NAV_HOME).setChecked(True)
        self.nav_group.idClicked.connect(self._on_nav_changed)

        layout.addStretch(1)

        self.library_toggle_btn = QToolButton()
        self.library_toggle_btn.setObjectName("navButton")
        self.library_toggle_btn.setToolTip("Mostrar/ocultar biblioteca")
        self.library_toggle_btn.setText("Biblioteca")
        self.library_toggle_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.library_toggle_btn.setCheckable(True)
        self.library_toggle_btn.setChecked(False)
        self.library_toggle_btn.setCursor(Qt.PointingHandCursor)
        self.library_toggle_btn.setIconSize(QSize(26, 26))
        self.library_toggle_btn.setIcon(app_icons.icon_library(palette.TEXT_MUTED))
        self.library_toggle_btn.toggled.connect(self._toggle_library_sidebar)
        layout.addWidget(self.library_toggle_btn)

        return rail

    def _toggle_library_sidebar(self, visible: bool):
        self.library_sidebar.setVisible(visible)
        self.library_toggle_btn.setIcon(
            app_icons.icon_library(palette.ACCENT if visible else palette.TEXT_MUTED)
        )

    def _open_favorites_folder(self, folder):
        """
        Salta a la pestaña de Favoritos y, si se indica una carpeta, la deja
        seleccionada en el filtro -- llamado desde el panel de biblioteca al
        pinchar una "playlist". folder=None significa "todos los favoritos,
        sin filtrar por carpeta".
        """
        self.nav_group.button(NAV_FAV).click()
        if folder:
            idx = self.group_filter.findText(folder)
            if idx >= 0:
                self.group_filter.setCurrentIndex(idx)
        else:
            self.group_filter.setCurrentIndex(0)

    def _on_groups_sidebar_changed(self, groups):
        """
        Callback de GroupsSidebar cuando cambia la selección de grupos.
        `groups` es un set de nombres de grupo, o None si no hay filtro
        (se eligió "(Todos)" o se deseleccionó todo).
        """
        self._tv_sidebar_groups = groups
        self.lists.filter_current_list()

    def _build_top_bar(self) -> QVBoxLayout:
        # Dos filas: la primera da contexto a la sección y la segunda se
        # dedica enteramente a explorar. Es la misma jerarquía que el
        # lateral de Pencil y evita que el buscador pierda anchura ante los
        # filtros en ventanas normales.
        bar = QVBoxLayout()
        bar.setSpacing(10)
        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        filters_row = QVBoxLayout()
        filters_row.setSpacing(8)
        filter_options_row = QHBoxLayout()
        filter_options_row.setSpacing(8)

        self.section_title = QLabel(SECTION_TITLES[NAV_HOME])
        self.section_title.setObjectName("sectionTitle")
        # Sin mínimo protegido, un QHBoxLayout bajo presión de espacio lo
        # encoge a él antes que a group_filter/search_box (que sí tienen
        # min/max explícitos) -- por eso "Televisión" salía cortado en
        # ventanas estrechas. 110px cubre el título más largo ("Televisión")
        # con el tamaño de fuente actual; si aun así falta sitio, se elide
        # con "…" en vez de recortarse sin avisar.
        self.section_title.setMinimumWidth(90)
        self.section_title.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        title_row.addWidget(self.section_title)

        self.catalog_count_label = QLabel()
        self.catalog_count_label.setObjectName("catalogCount")
        self.catalog_count_label.setMaximumWidth(110)
        self.catalog_count_label.hide()
        title_row.addWidget(self.catalog_count_label)
        title_row.addStretch(1)

        self.epg_btn = QPushButton("Guía")
        self.epg_btn.setToolTip("Ver parrilla de programación")
        self.epg_btn.clicked.connect(self.epg.open_dialog)
        title_row.addWidget(self.epg_btn)

        # Alternar lista/cuadrícula para los dos catálogos principales --
        # visibilidad controlada junto al resto en _on_nav_changed().
        self.tv_view_toggle = QToolButton()
        self.tv_view_toggle.setObjectName("catalogViewToggle")
        self.tv_view_toggle.setCheckable(True)
        self.tv_view_toggle.setCursor(Qt.PointingHandCursor)
        self.tv_view_toggle.setIconSize(QSize(18, 18))
        # Iconos dibujados a mano (ver ui/icons.py), no texto: el carácter
        # "⊞" que se usaba antes con setText() no está garantizado en Segoe
        # UI y salía en blanco -- solo se veía el fondo dorado/de acento del
        # estado :checked, sin ningún icono encima (reportado con captura).
        self.tv_view_toggle.setIcon(app_icons.icon_grid_view(palette.TEXT_DIM))
        self.tv_view_toggle.setToolTip("Ver catálogo en cuadrícula")
        self.tv_view_toggle.setFixedSize(30, 30)
        self.tv_view_toggle.toggled.connect(self._toggle_tv_grid_view)
        title_row.addWidget(self.tv_view_toggle)

        # Filtro por estado de salud del stream (TV y Radio). Filtra con los
        # resultados ya guardados del diagnóstico (core/stream_health_store),
        # sin tocar la red: elegir una opción es instantáneo. El userData de
        # cada opción es la clave que entiende matches_health_filter().
        self.health_filter = QComboBox()
        self.health_filter.setObjectName("groupFilter")
        for etiqueta, clave in (
            ("Estado: todos", "all"),
            ("Estables", "stable"),
            ("Con incidencias", "issues"),
            ("Diagnóstico antiguo", "stale"),
            ("Sin diagnosticar", "unchecked"),
        ):
            self.health_filter.addItem(etiqueta, clave)
        self.health_filter.setToolTip(
            "Filtrar por el último diagnóstico guardado "
            "(Archivo > Diagnosticar canales y emisoras…)"
        )
        self.health_filter.currentIndexChanged.connect(self.lists.filter_current_list)
        self.health_filter.setMinimumWidth(88)
        self.health_filter.setMaximumWidth(140)
        filter_options_row.addWidget(self.health_filter)

        self.group_filter = QComboBox()
        self.group_filter.setObjectName("groupFilter")
        self.group_filter.addItem("Todas las categorías")
        self.group_filter.currentTextChanged.connect(self.lists.filter_current_list)
        # Antes con setFixedWidth(200): a la anchura mínima de ventana que
        # permite la app (900px), el título + 200 + 240 del buscador no
        # cabían en la columna de contenido, y al ser anchos fijos Qt no
        # podía encogerlos — se salían del panel sin más, cortando la
        # esquina redondeada del buscador. Con mínimo/máximo, encogen antes
        # de desbordar.
        self.group_filter.setMinimumWidth(100)
        self.group_filter.setMaximumWidth(175)
        filter_options_row.addWidget(self.group_filter)

        self.catalog_sort = QComboBox()
        self.catalog_sort.setObjectName("groupFilter")
        self.catalog_sort.addItem("Orden original", "source")
        self.catalog_sort.addItem("Nombre A–Z", "name")
        self.catalog_sort.addItem("Favoritos primero", "favorites")
        self.catalog_sort.setToolTip("Ordenar el catálogo")
        self.catalog_sort.setMinimumWidth(98)
        self.catalog_sort.setMaximumWidth(140)
        self.catalog_sort.currentIndexChanged.connect(self._on_catalog_sort_changed)
        filter_options_row.addWidget(self.catalog_sort)

        self.search_box = QLineEdit()
        self.search_box.setObjectName("searchBox")
        self.search_box.setPlaceholderText("Buscar canal o emisora…")
        self.search_box.setMinimumWidth(100)
        self.search_box.setMaximumWidth(16777215)
        # Antirrebote: filtrar en cada tecla (aunque cada pasada ya vaya
        # protegida con setUpdatesEnabled, ver ChannelListsController.
        # filter_current_list) sigue siendo trabajo de más si el usuario
        # escribe varias letras seguidas rápido -- con esto se espera a
        # que pare de teclear 150ms antes de filtrar, sin cambiar nada
        # para quien escribe despacio (nunca se nota el retraso).
        self._search_debounce = QTimer(self)
        self._search_debounce.setSingleShot(True)
        self._search_debounce.setInterval(150)
        self._search_debounce.timeout.connect(self.lists.filter_current_list)
        self.search_box.textChanged.connect(lambda _texto: self._search_debounce.start())
        # En la captura, los cuatro controles en una sola fila se cortaban
        # al reducir el catálogo. La búsqueda va en su propia fila y los
        # filtros debajo; las tres opciones inferiores ya caben incluso en
        # el ancho mínimo del panel central.
        filters_row.addWidget(self.search_box)
        filters_row.addLayout(filter_options_row)

        bar.addLayout(title_row)
        bar.addLayout(filters_row)
        return bar

    def _on_catalog_sort_changed(self):
        current = self.stack.currentWidget() if hasattr(self, "stack") else None
        if current not in (getattr(self, "tv_list", None), getattr(self, "radio_list", None)):
            return
        kind = "tv" if current is self.tv_list else "radio"
        self.settings[f"catalog_sort_{kind}"] = self.catalog_sort.currentData() or "source"
        cfg.save_settings(self.settings)
        self.lists.sort_catalog(current)

    def _toggle_tv_grid_view(self, checked: bool):
        """
        Alterna TV y Radio entre filas y cuadrícula de tarjetas. Favoritos
        e historial conservan el modo lista porque contienen tipos mezclados
        y, en el caso de favoritos, admiten reordenación mediante arrastre.
        """
        for catalog in (self.tv_list, self.radio_list):
            if checked:
                catalog.setItemDelegate(self.grid_delegate)
                catalog.setViewMode(QListWidget.IconMode)
                catalog.setFlow(QListWidget.LeftToRight)
                catalog.setResizeMode(QListWidget.Adjust)
                catalog.setMovement(QListWidget.Static)
                catalog.setSpacing(4)
                catalog.setGridSize(QSize(
                    ChannelGridDelegate.CARD_SIZE,
                    ChannelGridDelegate.CARD_SIZE,
                ))
            else:
                catalog.setItemDelegate(self.delegate)
                catalog.setViewMode(QListWidget.ListMode)
                catalog.setFlow(QListWidget.TopToBottom)
                catalog.setMovement(QListWidget.Static)
                catalog.setSpacing(0)
                catalog.setGridSize(QSize())

        if checked:
            # BG_ROOT (oscuro) cuando está marcado, porque :checked pone de
            # fondo el color de acento claro -- mismo criterio que ya usan
            # los botones del riel de navegación (ver nav_icon_builders).
            self.tv_view_toggle.setIcon(app_icons.icon_list_view(palette.BG_ROOT))
            self.tv_view_toggle.setToolTip("Ver catálogo en lista")
        else:
            self.tv_view_toggle.setIcon(app_icons.icon_grid_view(palette.TEXT_DIM))
            self.tv_view_toggle.setToolTip("Ver catálogo en cuadrícula")

        self.settings["catalog_grid_view"] = bool(checked)
        cfg.save_settings(self.settings)
        self.tv_list.viewport().update()
        self.radio_list.viewport().update()

    def _build_content_stack(self) -> QStackedWidget:
        self.stack = QStackedWidget()
        self.delegate = ChannelDelegate()
        self.grid_delegate = ChannelGridDelegate()
        self.grid_delegate.CARD_SIZE = int(self.settings.get("catalog_card_size", 168))

        self.tv_model = ChannelListModel(self)
        self.radio_model = ChannelListModel(self)
        self.tv_list = self._make_list(model=self.tv_model)
        self.radio_list = self._make_list(model=self.radio_model)
        self.fav_list = self._make_list(reorderable=True)
        self.hist_list = self._make_list()
        self.home_page = self._build_home_page()

        for page in (self.home_page, self.tv_list, self.radio_list, self.fav_list,
                     self.hist_list):
            self.stack.addWidget(page)

        return self.stack

    def _build_home_page(self) -> QWidget:
        """
        Portada de bienvenida: accesos rápidos a TV/Radio, y un vistazo a lo
        último visto y a los favoritos, sin tener que entrar en cada sección.
        Reutiliza _make_list() (misma tarjeta, mismo clic-para-reproducir,
        mismo menú contextual que el resto de la app) en vez de inventar un
        sistema de tarjetas nuevo sin poder probarlo antes de dártelo.
        """
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setObjectName("homeScroll")

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(2, 4, 20, 18)
        layout.setSpacing(18)
        self._home_layout = layout

        hero = QFrame()
        hero.setObjectName("homeHero")
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(22, 18, 22, 18)
        hero_layout.setSpacing(10)

        greeting = QLabel("Tu televisión y radio")
        greeting.setObjectName("homeGreeting")
        greeting.setWordWrap(True)
        greeting.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        hero_layout.addWidget(greeting)

        subtitle = QLabel("Elige TV, radio o retoma lo que estabas escuchando.")
        subtitle.setObjectName("dialogSubtitle")
        subtitle.setWordWrap(True)
        subtitle.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        hero_layout.addWidget(subtitle)

        self.home_now_card = QFrame()
        self.home_now_card.setObjectName("dialogPanel")
        self.home_now_card.setProperty("uiSurface", "homeSectionCard")
        now_layout = QBoxLayout(QBoxLayout.LeftToRight, self.home_now_card)
        now_layout.setContentsMargins(14, 10, 14, 10)
        now_layout.setSpacing(10)
        self._home_now_layout = now_layout
        now_text = QVBoxLayout()
        self.home_now_title = QLabel("Nada en reproducción")
        self.home_now_title.setObjectName("nowTitle")
        self.home_now_title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.home_now_subtitle = QLabel("Busca cualquier canal o emisora con Ctrl+K")
        self.home_now_subtitle.setObjectName("nowSubtitle")
        self.home_now_subtitle.setWordWrap(True)
        self.home_now_subtitle.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        now_text.addWidget(self.home_now_title)
        now_text.addWidget(self.home_now_subtitle)
        now_layout.addLayout(now_text, 1)
        self.home_resume_btn = QPushButton("Buscar")
        set_variant(self.home_resume_btn, "primary")
        self.home_resume_btn.clicked.connect(self.home.home_resume_or_search)
        now_layout.addWidget(self.home_resume_btn)
        self.home_float_btn = QPushButton("Ventana flotante")
        self.home_float_btn.clicked.connect(self.window_chrome.toggle_pip_mode)
        self.home_float_btn.setVisible(False)
        now_layout.addWidget(self.home_float_btn)
        hero_layout.addWidget(self.home_now_card)

        quick_row = QBoxLayout(QBoxLayout.LeftToRight)
        quick_row.setSpacing(10)
        self._home_quick_layout = quick_row

        tv_btn = QPushButton(" Ver TV en directo")
        tv_btn.setObjectName("homeQuickButton")
        set_variant(tv_btn, "tv")
        # Icono oscuro a juego con el "color" que ya usa
        # QPushButton#homeQuickButton[uiVariant="tv"] en ui/style.py para el
        # texto sobre el fondo palette.ACCENT_INFO -- un literal aparte aquí
        # se habría podido desincronizar si ese tono cambia más adelante.
        tv_btn.setIcon(app_icons.icon_tv(palette.BG_ROOT))
        tv_btn.setIconSize(QSize(20, 20))
        tv_btn.setCursor(Qt.PointingHandCursor)
        tv_btn.clicked.connect(lambda: self.nav_group.button(NAV_TV).click())
        quick_row.addWidget(tv_btn)

        radio_btn = QPushButton(" Escuchar Radio")
        radio_btn.setObjectName("homeQuickButtonAlt")
        set_variant(radio_btn, "radio")
        radio_btn.setIcon(app_icons.icon_radio(palette.TEXT_PRIMARY))
        radio_btn.setIconSize(QSize(20, 20))
        radio_btn.setCursor(Qt.PointingHandCursor)
        radio_btn.clicked.connect(lambda: self.nav_group.button(NAV_RADIO).click())
        quick_row.addWidget(radio_btn)
        quick_row.addStretch(1)
        hero_layout.addLayout(quick_row)
        layout.addWidget(hero)

        health_panel = QFrame()
        health_panel.setObjectName("dialogPanel")
        health_panel.setProperty("uiSurface", "homeSectionCard")
        health_layout = QBoxLayout(QBoxLayout.LeftToRight, health_panel)
        health_layout.setContentsMargins(16, 13, 16, 13)
        health_layout.setSpacing(12)
        self._home_health_layout = health_layout
        health_text = QVBoxLayout()
        health_text.setSpacing(3)
        health_heading = QLabel("ESTADO DE LAS EMISIONES")
        health_heading.setObjectName("dialogSectionLabel")
        health_text.addWidget(health_heading)
        self.home_health_summary = QLabel()
        self.home_health_summary.setObjectName("homeHealthSummary")
        self.home_health_summary.setWordWrap(True)
        self.home_health_summary.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        health_text.addWidget(self.home_health_summary)
        health_layout.addLayout(health_text, 1)
        health_btn = QPushButton("Ver diagnóstico")
        set_variant(health_btn, "secondary")
        health_btn.clicked.connect(self._open_stream_diagnostics)
        health_layout.addWidget(health_btn)

        # ---- Ahora en antena (qué está echando cada canal, vía EPG) ----
        panel_antena = QFrame()
        panel_antena.setObjectName("dialogPanel")
        panel_antena.setProperty("uiSurface", "homeSectionCard")
        pa_layout = QVBoxLayout(panel_antena)
        pa_layout.setContentsMargins(16, 14, 16, 14)
        pa_layout.setSpacing(8)
        lbl_antena = QLabel("AHORA EN ANTENA")
        lbl_antena.setObjectName("dialogSectionLabel")
        pa_layout.addWidget(lbl_antena)
        self.home_on_air_carousel = Carousel(
            on_activate=self.home.activate_home_entry,
            logo_loader=self.logo_loader,
            empty_text="Configura una guía de programación (EPG) en Configuración para ver esto.",
        )
        pa_layout.addWidget(self.home_on_air_carousel)
        self.panel_antena = panel_antena

        # ---- Recientes (carrusel horizontal, estilo Spotify) ----
        panel_recientes = QFrame()
        panel_recientes.setObjectName("dialogPanel")
        panel_recientes.setProperty("uiSurface", "homeSectionCard")
        pr_layout = QVBoxLayout(panel_recientes)
        pr_layout.setContentsMargins(16, 14, 16, 14)
        pr_layout.setSpacing(8)
        lbl_recientes = QLabel("RECIENTES")
        lbl_recientes.setObjectName("dialogSectionLabel")
        pr_layout.addWidget(lbl_recientes)
        self.home_recent_carousel = Carousel(
            on_activate=self.home.activate_home_entry,
            logo_loader=self.logo_loader,
            empty_text="Todavía no has visto ni escuchado nada.",
        )
        pr_layout.addWidget(self.home_recent_carousel)
        layout.addWidget(panel_recientes)

        # ---- Recomendado para ti (carrusel horizontal) ----
        panel_recomendado = QFrame()
        panel_recomendado.setObjectName("dialogPanel")
        panel_recomendado.setProperty("uiSurface", "homeSectionCard")
        pv_layout = QVBoxLayout(panel_recomendado)
        pv_layout.setContentsMargins(16, 14, 16, 14)
        pv_layout.setSpacing(8)
        lbl_recomendado = QLabel("RECOMENDADO PARA TI")
        lbl_recomendado.setObjectName("dialogSectionLabel")
        pv_layout.addWidget(lbl_recomendado)
        self.home_recommended_carousel = Carousel(
            on_activate=self.home.activate_home_entry,
            logo_loader=self.logo_loader,
            empty_text="Actualiza los canales de TV para ver sugerencias aquí.",
        )
        pv_layout.addWidget(self.home_recommended_carousel)

        # ---- Favoritos ----
        panel_favs = QFrame()
        panel_favs.setObjectName("dialogPanel")
        panel_favs.setProperty("uiSurface", "homeSectionCard")
        pf_layout = QVBoxLayout(panel_favs)
        pf_layout.setContentsMargins(16, 14, 16, 14)
        pf_layout.setSpacing(8)
        lbl_favs = QLabel("TUS FAVORITOS")
        lbl_favs.setObjectName("dialogSectionLabel")
        pf_layout.addWidget(lbl_favs)
        self.home_fav_list = self._make_list()
        self.home_fav_list.setFixedHeight(5 * ChannelDelegate.ROW_HEIGHT + 12)
        self.home_fav_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        pf_layout.addWidget(self.home_fav_list)
        self.home_fav_empty = QLabel("Todavía no tienes ningún favorito marcado.")
        self.home_fav_empty.setStyleSheet(f"color: {palette.TEXT_DIM}; font-size: 8pt;")
        pf_layout.addWidget(self.home_fav_empty)

        # "Recomendado para ti" y "Tus favoritos" van uno junto al otro
        # (2:1, como en la referencia de Stitch) en vez de apilados a lo
        # largo de toda la portada -- ambos son paneles cortos y quedaba
        # mucho hueco vacío a los lados si ocupaban el ancho completo.
        secondary_row = QBoxLayout(QBoxLayout.LeftToRight)
        secondary_row.setSpacing(16)
        self._home_secondary_layout = secondary_row
        secondary_row.addWidget(panel_recomendado, 2)
        secondary_row.addWidget(panel_favs, 1)
        layout.addLayout(secondary_row)

        layout.addWidget(panel_antena)
        layout.addWidget(health_panel)
        layout.addStretch(1)
        scroll.setWidget(content)
        self._home_viewport = scroll.viewport()
        return scroll

    # _update_home_compact / _home_resume_or_search / _refresh_home_now_playing /
    # _refresh_home_page / _refresh_home_health / _activate_home_entry /
    # _compute_recommendations viven ahora en
    # ui.home_controller.HomeController (self.home).

    # ---------- Ecualizador ----------

    def _apply_saved_equalizer(self):
        """
        Aplica el ecualizador guardado (ver ui/equalizer_dialog.py) nada
        más crear el reproductor, para que ya esté activo desde el primer
        canal/emisora de la sesión y no solo después de abrir el diálogo.
        Si el nº de bandas guardado no coincide con el que da esta libVLC
        (p. ej. tras cambiar de máquina o de versión de VLC), se ignora en
        vez de aplicar una configuración a medias.
        """
        if not self.settings.get("equalizer_enabled", False):
            return
        bandas = self.settings.get("equalizer_bands") or []
        if len(bandas) != self.player.equalizer_band_count():
            return
        self.player.set_equalizer(self.settings.get("equalizer_preamp", 0.0), bandas)

    def _open_equalizer_dialog(self):
        EqualizerDialog(self).exec()

    def _make_list(self, reorderable: bool = False, model=None) -> QListWidget:
        lst = ChannelListView() if model is not None else QListWidget()
        lst.setObjectName("channelList")
        lst.setItemDelegate(self.delegate)
        if model is not None:
            lst.setModel(model)
        lst.setUniformItemSizes(True)
        lst.setMouseTracking(True)
        lst.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        if isinstance(lst, ChannelListView):
            lst.clicked.connect(lambda index, w=lst: self.playback.on_item_activated(w.item(index.row()), w))
        else:
            lst.itemClicked.connect(lambda item, w=lst: self.playback.on_item_activated(item, w))
        lst.setContextMenuPolicy(Qt.CustomContextMenu)
        lst.customContextMenuRequested.connect(lambda pos, w=lst: self.channel_menu.show_context_menu(pos, w))
        lst.verticalScrollBar().valueChanged.connect(
            lambda _value, w=lst: self.lists.load_visible_logos(w)
        )
        lst.horizontalScrollBar().valueChanged.connect(
            lambda _value, w=lst: self.lists.load_visible_logos(w)
        )
        if reorderable:
            # Solo Favoritos se puede reordenar a mano arrastrando filas --
            # el resto de listas reflejan un orden que viene de fuera (la
            # lista M3U, la API de radio, o la fecha del historial) y
            # reordenarlas a mano no se guardaría en ningún sitio.
            lst.setDragDropMode(QListWidget.InternalMove)
            lst.setDefaultDropAction(Qt.MoveAction)
            lst.model().rowsMoved.connect(lambda *_: self.lists.persist_favorites_order())
        return lst

    def _build_player_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("playerPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 6, 16, 14)
        layout.setSpacing(10)

        # Cabecera propia del área de emisión. En el diseño de Pencil, la
        # reproducción se entiende como un espacio independiente de la lista
        # de canales: este rótulo conserva esa jerarquía también al alternar
        # entre TV, radio o el ecualizador.
        #
        # Va en un QWidget (no un QHBoxLayout suelto) para poder
        # ocultarla/mostrarla de una vez en pantalla completa -- ver
        # WindowChrome.show_fullscreen_overlay(). live_badge conserva su
        # propia visibilidad (set_live_badge_visible()) anidada dentro: al
        # ocultar el contenedor solo se tapa, no se pierde ese estado.
        self.player_header_bar = QWidget()
        player_header = QHBoxLayout(self.player_header_bar)
        player_header.setContentsMargins(8, 2, 8, 4)
        self.player_context_label = QLabel("AHORA SUENA")
        self.player_context_label.setObjectName("playerContextLabel")
        player_header.addWidget(self.player_context_label)
        player_header.addStretch(1)

        # El punto rojo se mantiene separado del dorado de marca: comunica
        # que el contenido es una emisión viva, no una alerta de error.
        self.live_badge = QLabel(
            '<span style="color:#ef5350;">●</span>&nbsp;&nbsp;EN DIRECTO'
        )
        self.live_badge.setObjectName("liveBadge")
        set_variant(self.live_badge, "danger")
        self.live_badge.hide()
        player_header.addWidget(self.live_badge)
        layout.addWidget(self.player_header_bar)

        self.player_frame = QFrame()
        self.player_frame.setObjectName("playerFrame")
        self.player_frame.installEventFilter(self)
        frame_layout = QVBoxLayout(self.player_frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)

        self.player_stack = QStackedWidget()
        # QStackedWidget siempre ajusta a su widget hijo actual al tamaño
        # completo DEL PROPIO STACK — pero eso no significa que el stack en
        # sí crezca dentro de frame_layout. Sin esta línea, player_stack se
        # quedaba con la política Preferred por defecto de Qt y su sizeHint
        # (dominado por EqualizerWidget.setMinimumHeight(200)); el vídeo
        # salía correctamente escalado... al tamaño pequeño que Qt le daba
        # al stack, con el fondo de playerFrame visible alrededor.
        self.player_stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.player = VLCPlayer()
        self.player.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.player.error_occurred.connect(self.playback.on_player_error)
        self.player.end_reached.connect(self.playback.on_player_end_reached)
        self._apply_saved_equalizer()
        # "equalizer" es el nombre histórico de este atributo (antes un
        # EqualizerWidget a pelo); ahora es la vista "Ahora Suena" completa
        # -- logo de emisora + título en directo cuando el stream lo manda
        # (ICY) -- que sigue llevando su propio EqualizerWidget dentro como
        # tira animada. start()/stop()/set_intensity() tienen la misma firma
        # que antes a propósito, así que playback_controller.py no cambia.
        self.equalizer = RadioHeroWidget(self.logo_loader)
        self.player.meta_changed.connect(self.equalizer.set_now_playing)
        self.player_stack.addWidget(self.player)
        self.player_stack.addWidget(self.equalizer)
        frame_layout.addWidget(self.player_stack, stretch=1)

        layout.addWidget(self.player_frame, stretch=1)
        self.now_playing_bar = self._build_now_playing_bar()
        layout.addWidget(self.now_playing_bar)

        # Auto-ocultar cabecera/controles en pantalla completa (ajuste
        # "fullscreen_autohide_ui") -- ver WindowChrome.enter_player_fullscreen
        # / show_fullscreen_overlay / check_fullscreen_mouse_activity. El
        # vídeo se pinta en una ventana nativa de libVLC embebida, así que
        # sus eventos de ratón no llegan a Qt: en vez de un eventFilter se
        # sondea la posición global del cursor con un QTimer periódico.
        self._fs_last_cursor_pos = None
        self._fs_mouse_poll_timer = QTimer(self)
        self._fs_mouse_poll_timer.setInterval(180)
        self._fs_mouse_poll_timer.timeout.connect(
            self.window_chrome.check_fullscreen_mouse_activity
        )
        self._fs_overlay_hide_timer = QTimer(self)
        self._fs_overlay_hide_timer.setSingleShot(True)
        self._fs_overlay_hide_timer.setInterval(2500)
        self._fs_overlay_hide_timer.timeout.connect(
            self.window_chrome.hide_fullscreen_overlay
        )

        return panel

    def set_live_badge_visible(self, visible: bool) -> None:
        """Sincroniza el indicador visual con la emisión actual."""
        self.live_badge.setVisible(bool(visible))
        if visible:
            self.live_badge.raise_()

    @staticmethod
    def _make_separator() -> QFrame:
        """
        Línea vertical fina entre grupos de botones de control. Antes todos
        los botones iban en una sola fila sin ninguna separación visual más
        que el spacing del layout — con el halo del play y poco espacio
        entre botones, la fila entera se veía como un bloque pegado en vez
        de controles agrupados por función (favorito/cast, reproducción,
        grabar/volumen, vista).
        """
        sep = QFrame()
        sep.setObjectName("ctrlSeparator")
        sep.setFixedWidth(1)
        sep.setFixedHeight(22)
        return sep

    @staticmethod
    def _make_glow(color: QColor, blur: float = 22, alpha: int = 160, y_offset: float = 0) -> QGraphicsDropShadowEffect:
        """
        Halo de color alrededor de un botón, vía QGraphicsDropShadowEffect
        (esto sí aplica a QWidgets normales, a diferencia de los delegados
        de lista, que no soportan QGraphicsEffect y necesitan pintarlo a mano).
        """
        effect = QGraphicsDropShadowEffect()
        glow_color = QColor(color)
        glow_color.setAlpha(alpha)
        effect.setColor(glow_color)
        effect.setBlurRadius(blur)
        effect.setOffset(0, y_offset)
        return effect

    def _build_now_playing_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("nowPlayingBar")
        bar.setFixedHeight(142)
        outer = QVBoxLayout(bar)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(12)
        self._now_bar_layout = outer

        info_row = QHBoxLayout()
        self.now_logo = QLabel()
        self.now_logo.setFixedSize(50, 50)
        self.now_logo.setStyleSheet(f"background-color: {palette.BG_PANEL_ALT}; border-radius: 12px;")
        self.now_logo.setAlignment(Qt.AlignCenter)
        info_row.addWidget(self.now_logo)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        self.now_title = QLabel("Nada en reproducción")
        self.now_title.setObjectName("nowTitle")
        self.now_title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self.now_subtitle = QLabel("Elige un canal o una emisora")
        self.now_subtitle.setObjectName("nowSubtitle")
        self.now_subtitle.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        text_col.addWidget(self.now_title)
        text_col.addWidget(self.now_subtitle)
        info_row.addLayout(text_col, stretch=1)

        # El volumen vivía en la fila de botones de abajo, donde con muchos
        # botones + separadores no queda sitio de sobra: con ventana
        # estrecha el slider (que necesita un ancho mínimo para no
        # convertirse en un punto suelto irreconocible) se comía a sus
        # vecinos. Aquí arriba, junto al nombre del canal, sí hay margen.
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setObjectName("volumeSlider")
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(self.settings.get("volume", 80))
        self.volume_slider.setFixedWidth(108)
        self.volume_slider.valueChanged.connect(self.playback.on_volume_changed)
        info_row.addWidget(self.volume_slider)

        outer.addLayout(info_row)

        controls = QHBoxLayout()
        controls.setSpacing(6)

        # Reorganizado en tres zonas (izquierda / centro / derecha), estilo
        # Spotify: antes todos los botones iban en una sola fila corrida de
        # izquierda a derecha sin agrupar por función. Con addStretch a cada
        # lado del grupo central, el transporte de reproducción (parar /
        # play / reintentar) queda siempre centrado en la barra pase lo que
        # pase con favoritos/cast a la izquierda o grabar/volumen/vista a la
        # derecha -- la misma jerarquía visual que un reproductor "grande".
        left_group = QHBoxLayout()
        left_group.setSpacing(6)
        center_group = QHBoxLayout()
        center_group.setSpacing(3)
        right_group = QHBoxLayout()
        right_group.setSpacing(5)

        self.fav_btn = QPushButton()
        self.fav_btn.setObjectName("ctrlButton")
        self.fav_btn.setIconSize(QSize(15, 15))
        self.fav_btn.setIcon(app_icons.icon_favorite(palette.ACCENT, size=18))
        self.fav_btn.setToolTip("Añadir a favoritos")
        self.fav_btn.setAccessibleName("Añadir a favoritos")
        self.fav_btn.setCheckable(True)
        self.fav_btn.clicked.connect(self.playback.toggle_favorite_current)
        left_group.addWidget(self.fav_btn)

        self.stop_btn = QPushButton()
        self.stop_btn.setObjectName("ctrlButton")
        self.stop_btn.setIcon(app_icons.icon_stop(palette.TEXT_PRIMARY, size=18))
        self.stop_btn.setIconSize(QSize(15, 15))
        self.stop_btn.setToolTip("Detener")
        self.stop_btn.setAccessibleName("Detener reproducción")
        self.stop_btn.clicked.connect(self.playback.stop_playback)
        center_group.addWidget(self.stop_btn)

        # Avance r\u00E1pido / retroceso de 30 s. Solo tienen efecto real en
        # contenido posicionable (VOD, series, ficheros locales) -- un
        # canal de TV o emisora de radio en directo puro no admite
        # set_time(), as\u00ED que empiezan desactivados y PlaybackController
        # los activa/desactiva seg\u00FAn VLCPlayer.is_seekable() confirme lo
        # que se est\u00E1 reproduciendo (ver _confirm_playback_ok).
        self.seek_back_btn = QPushButton()
        self.seek_back_btn.setObjectName("ctrlButton")
        self.seek_back_btn.setIcon(app_icons.icon_seek(palette.TEXT_PRIMARY, size=18, forward=False))
        self.seek_back_btn.setIconSize(QSize(15, 15))
        self.seek_back_btn.setToolTip("Retroceder 30 s")
        self.seek_back_btn.setAccessibleName("Retroceder 30 segundos")
        self.seek_back_btn.setEnabled(False)
        self.seek_back_btn.clicked.connect(lambda: self.playback.seek(-30_000))
        center_group.addWidget(self.seek_back_btn)

        center_group.addSpacing(4)
        self.play_btn = QPushButton()
        self.play_btn.setObjectName("playCircle")
        self.play_btn.setIcon(app_icons.icon_play(palette.BG_ROOT, size=22))
        self.play_btn.setIconSize(QSize(19, 19))
        self.play_btn.setToolTip("Reproducir")
        self.play_btn.setAccessibleName("Reproducir")
        set_variant(self.play_btn, "primary")
        self.play_btn.clicked.connect(self.playback.toggle_play)
        center_group.addWidget(self.play_btn)
        center_group.addSpacing(4)

        self.seek_fwd_btn = QPushButton()
        self.seek_fwd_btn.setObjectName("ctrlButton")
        self.seek_fwd_btn.setIcon(app_icons.icon_seek(palette.TEXT_PRIMARY, size=18))
        self.seek_fwd_btn.setIconSize(QSize(15, 15))
        self.seek_fwd_btn.setToolTip("Avanzar 30 s")
        self.seek_fwd_btn.setAccessibleName("Avanzar 30 segundos")
        self.seek_fwd_btn.setEnabled(False)
        self.seek_fwd_btn.clicked.connect(lambda: self.playback.seek(30_000))
        center_group.addWidget(self.seek_fwd_btn)

        self.retry_btn = QPushButton()
        self.retry_btn.setObjectName("ctrlButton")
        self.retry_btn.setIcon(app_icons.icon_retry(palette.TEXT_PRIMARY, size=18))
        self.retry_btn.setIconSize(QSize(15, 15))
        self.retry_btn.setToolTip("Reintentar conexión")
        self.retry_btn.setAccessibleName("Reintentar conexión")
        self.retry_btn.clicked.connect(self.playback.retry_playback)
        self.retry_btn.setVisible(False)
        center_group.addWidget(self.retry_btn)

        self.record_btn = QPushButton()
        self.record_btn.setObjectName("recordButton")
        self.record_btn.setIcon(app_icons.icon_record(palette.DANGER, size=18))
        self.record_btn.setIconSize(QSize(15, 15))
        self.record_btn.setToolTip("Iniciar grabación")
        self.record_btn.setAccessibleName("Iniciar grabación")
        set_variant(self.record_btn, "danger")
        self.record_btn.setCheckable(True)
        self.record_btn.clicked.connect(self.playback.toggle_recording)
        right_group.addWidget(self.record_btn)

        self.mute_btn = QPushButton()
        self.mute_btn.setObjectName("muteButton")
        set_variant(self.mute_btn, "info")
        self.mute_btn.setIconSize(QSize(15, 15))
        self.mute_btn.setIcon(app_icons.icon_speaker(palette.ACCENT_INFO, muted=False))
        self.mute_btn.setCheckable(True)
        self.mute_btn.setToolTip("Silenciar")
        self.mute_btn.setAccessibleName("Silenciar")
        self.mute_btn.clicked.connect(self.playback.toggle_mute)
        right_group.addWidget(self.mute_btn)

        self.now_controls_separator = self._make_separator()
        right_group.addWidget(self.now_controls_separator)

        # Pistas/pantalla completa/PiP/temporizador/cola: antes cada uno
        # tenia su propio boton circular en esta fila. Con 8 botones +
        # separador no cabian en ventanas estrechas y quedaban solapados o
        # cortados (reportado con captura). Se siguen creando igual -- el
        # resto del codigo (iconos, tooltips, estado checked/toggled) sigue
        # dependiendo de estos widgets como "guardianes de estado" -- pero
        # ya NO se anaden a right_group: se agrupan bajo un unico boton
        # "Mas opciones" siempre visible, asi la fila no crece con el
        # numero de funciones, solo con las acciones realmente frecuentes.
        self.tracks_btn = QPushButton("CC")
        self.tracks_btn.setObjectName("ctrlButton")
        self.tracks_btn.setToolTip("Pistas de audio y subt\u00EDtulos")
        self.tracks_btn.clicked.connect(self._open_tracks_menu)

        self.fullscreen_btn = QPushButton()
        self.fullscreen_btn.setObjectName("ctrlButton")
        self.fullscreen_btn.setIcon(app_icons.icon_fullscreen(palette.TEXT_PRIMARY, size=18))
        self.fullscreen_btn.setIconSize(QSize(15, 15))
        self.fullscreen_btn.setToolTip("Pantalla completa (F11)")
        self.fullscreen_btn.setAccessibleName("Pantalla completa")
        self.fullscreen_btn.clicked.connect(self.window_chrome.toggle_player_fullscreen)

        self.pip_btn = QPushButton()
        self.pip_btn.setObjectName("ctrlButton")
        self.pip_btn.setIconSize(QSize(15, 15))
        self.pip_btn.setIcon(app_icons.icon_pip(palette.TEXT_PRIMARY))
        self.pip_btn.setToolTip("Ventana flotante")
        self.pip_btn.setAccessibleName("Abrir ventana flotante")
        self.pip_btn.clicked.connect(self.window_chrome.toggle_pip_mode)

        self.sleep_btn = QPushButton()
        self.sleep_btn.setObjectName("sleepButton")
        set_variant(self.sleep_btn, "sleep")
        self.sleep_btn.setIconSize(QSize(15, 15))
        self.sleep_btn.setIcon(app_icons.icon_moon(palette.ACCENT_SLEEP))
        self.sleep_btn.setCheckable(True)
        self.sleep_btn.setToolTip("Temporizador de apagado")
        self.sleep_btn.setAccessibleName("Temporizador de apagado")
        self.sleep_btn.clicked.connect(self.playback.on_sleep_btn_clicked)
        self.sleep_btn.toggled.connect(
            # palette.BG_ROOT es el "color" que usa
            # #sleepButton[uiVariant="sleep"]:checked en ui/style.py sobre
            # el fondo palette.ACCENT_SLEEP.
            lambda checked: self.sleep_btn.setIcon(app_icons.icon_moon(palette.BG_ROOT if checked else palette.ACCENT_SLEEP))
        )

        self.queue_btn = QPushButton()
        self.queue_btn.setObjectName("ctrlButton")
        self.queue_btn.setIconSize(QSize(15, 15))
        self.queue_btn.setIcon(app_icons.icon_queue(palette.TEXT_PRIMARY))
        self.queue_btn.setToolTip("Cola de reproducción (vacía)")
        self.queue_btn.setAccessibleName("Cola de reproducción")
        self.queue_btn.clicked.connect(self.queue.toggle_panel)

        self.more_btn = QPushButton()
        self.more_btn.setObjectName("ctrlButton")
        self.more_btn.setIconSize(QSize(15, 15))
        self.more_btn.setIcon(app_icons.icon_more(palette.TEXT_PRIMARY))
        self.more_btn.setToolTip("Más opciones (pistas, pantalla completa, PiP, temporizador, cola)")
        self.more_btn.setAccessibleName("Más opciones de reproducción")
        self.more_btn.clicked.connect(self._open_more_controls_menu)
        right_group.addWidget(self.more_btn)

        self._sleep_timer = QTimer(self)
        self._sleep_timer.setSingleShot(True)
        self._sleep_timer.timeout.connect(self.playback.on_sleep_timeout)
        self._sleep_countdown = QTimer(self)
        self._sleep_countdown.setInterval(60000)   # cada minuto
        self._sleep_countdown.timeout.connect(self.playback.update_sleep_tooltip)
        self._sleep_minutes_left = 0

        controls.addLayout(left_group)
        controls.addStretch(1)
        controls.addLayout(center_group)
        controls.addStretch(1)
        controls.addLayout(right_group)

        outer.addLayout(controls)
        return bar

    def _update_now_playing_compact(self, width: int) -> None:
        """Adapta la barra de reproducción sin solapar controles."""
        compact = width < 390
        margin = 14 if compact else 16
        self._now_bar_layout.setContentsMargins(margin, 16, margin, 16)
        self.now_logo.setVisible(not compact)
        self.volume_slider.setFixedWidth(56 if compact else 108)
        # En directo no aportan nada; en contenido posicionable reaparecen
        # al ensanchar el panel, evitando sacrificar controles esenciales.
        self.seek_back_btn.setVisible(not compact)
        self.seek_fwd_btn.setVisible(not compact)
        self.now_controls_separator.setVisible(not compact)

    def _open_more_controls_menu(self):
        """
        Menú "Más opciones" de la barra de reproducción: agrupa las
        acciones secundarias (pistas, pantalla completa, PiP, temporizador
        de apagado, cola) que antes tenían un botón circular propio en la
        fila de controles y dejaban de caber -- se solapaban o se veían
        cortados -- en ventanas estrechas. tracks_btn/fullscreen_btn/
        pip_btn/sleep_btn/queue_btn se siguen creando y actualizando en
        _build_now_playing_bar() exactamente igual que antes (iconos,
        tooltips, estado checked/toggled); solo dejaron de añadirse a la
        fila visible, así que aquí se reutilizan como fuente de su propio
        texto/estado en vez de duplicar esa lógica.
        """
        menu = QMenu(self)
        acento = self.settings.get("accent_color", palette.ACCENT)
        menu.setStyleSheet(
            f"QMenu {{ background-color: {palette.BG_PANEL}; color: {palette.TEXT_PRIMARY}; "
            f"border: 1px solid {palette.BORDER}; }}"
            f"QMenu::item:selected {{ background-color: {acento}; color: {palette.BG_ROOT}; }}"
        )

        menu.addAction("Pistas de audio y subtítulos…", self._open_tracks_menu)

        texto_fullscreen = (
            "Salir de pantalla completa" if self._player_fullscreen
            else "Pantalla completa (F11)"
        )
        menu.addAction(texto_fullscreen, self.window_chrome.toggle_player_fullscreen)

        texto_pip = "Salir de ventana flotante" if self._pip_mode else "Ventana flotante"
        menu.addAction(texto_pip, self.window_chrome.toggle_pip_mode)

        menu.addSeparator()

        if self._sleep_timer.isActive():
            texto_sleep = f"Cancelar temporizador ({self._sleep_minutes_left} min restantes)"
        else:
            texto_sleep = "Temporizador de apagado…"
        # on_sleep_btn_clicked ya decide internamente si abre el selector
        # de minutos o cancela el temporizador activo -- no hace falta
        # duplicar esa rama aquí, solo el texto que se muestra.
        menu.addAction(texto_sleep, self.playback.on_sleep_btn_clicked)

        menu.addAction(self.queue_btn.toolTip(), self.queue.toggle_panel)

        menu.addSeparator()
        texto_audio_only = (
            "Desactivar modo solo audio (TV)" if self._audio_only_tv
            else "Modo solo audio (TV)…"
        )
        menu.addAction(texto_audio_only, self.playback.toggle_audio_only_tv)
        menu.addAction("Ecualizador…", self._open_equalizer_dialog)

        menu.addAction("Información técnica…", self._show_stream_technical_info)
        menu.exec(self.more_btn.mapToGlobal(self.more_btn.rect().bottomLeft()))

    def _show_stream_technical_info(self):
        if not self.current_url:
            QMessageBox.information(self, "Información técnica", "No hay ninguna emisión activa.")
            return
        info = self.player.technical_info()
        labels = {
            "resolution": "Resolución", "volume": "Volumen",
            "audio_tracks": "Pistas de audio", "subtitle_tracks": "Pistas de subtítulos",
            "state": "Estado VLC", "input_bitrate": "Bitrate de entrada",
            "demux_bitrate": "Bitrate demux",
        }
        lines = [f"Canal: {self.current_name}", f"URL: {self.current_url}"]
        for key, label in labels.items():
            if key in info:
                value = info[key]
                if key.endswith("bitrate"):
                    value = f"{value:.2f} Mb/s"
                lines.append(f"{label}: {value}")
        QMessageBox.information(self, "Información técnica del stream", "\n".join(lines))

    def _open_tracks_menu(self):
        """
        Menú de pistas de audio y subtítulos del stream actual (solo TV:
        las emisoras de radio no traen subtítulos y casi nunca más de una
        pista de audio). Se construye cada vez que se abre, no una vez al
        arrancar, porque las pistas disponibles dependen del canal que
        esté sonando en ese momento.
        """
        if self.current_type != "tv" or not self.player.disponible:
            QMessageBox.information(
                self, "Sin pistas disponibles",
                "Las pistas de audio y subtítulos solo están disponibles "
                "mientras se reproduce un canal de TV."
            )
            return

        menu = QMenu(self)
        acento = self.settings.get("accent_color", palette.ACCENT)
        menu.setStyleSheet(
            f"QMenu {{ background-color: {palette.BG_PANEL}; color: {palette.TEXT_PRIMARY}; "
            f"border: 1px solid {palette.BORDER}; }}"
            f"QMenu::item:selected {{ background-color: {acento}; color: {palette.BG_ROOT}; }}"
        )

        audio_menu = menu.addMenu("Pista de audio")
        pistas_audio = self.player.audio_tracks()
        if not pistas_audio:
            audio_menu.addAction("(Solo una pista disponible)").setEnabled(False)
        else:
            actual = self.player.current_audio_track()
            for track_id, nombre in pistas_audio:
                accion = audio_menu.addAction(nombre)
                accion.setCheckable(True)
                accion.setChecked(track_id == actual)
                accion.triggered.connect(lambda _c=False, tid=track_id: self.player.set_audio_track(tid))

        subs_menu = menu.addMenu("Subtítulos")
        pistas_subs = self.player.subtitle_tracks()
        if not pistas_subs:
            subs_menu.addAction("(Este stream no trae subtítulos)").setEnabled(False)
        else:
            actual_sub = self.player.current_subtitle_track()
            for track_id, nombre in pistas_subs:
                accion = subs_menu.addAction(nombre)
                accion.setCheckable(True)
                accion.setChecked(track_id == actual_sub)
                accion.triggered.connect(lambda _c=False, tid=track_id: self.player.set_subtitle_track(tid))

        # Se ancla a more_btn (no a tracks_btn): tracks_btn ya no vive en
        # ningún layout visible -- ver el comentario en _build_now_playing_bar
        # -- así que su propia posición en pantalla no sería fiable.
        menu.exec(self.more_btn.mapToGlobal(self.more_btn.rect().bottomLeft()))

    def _build_title_bar(self) -> QWidget:
        """
        Barra de título propia. Antes esto se montaba con los 'corner widgets'
        de QMenuBar, un mecanismo cuyo dibujado depende del estilo nativo y
        que en algunos equipos no llegaba a mostrarse. Aquí la disposición es
        explícita, así que se ve igual en cualquier máquina.
        """
        barra = QWidget()
        barra.setObjectName("titleBar")
        barra.setFixedHeight(58)

        fila = QHBoxLayout(barra)
        fila.setContentsMargins(18, 0, 8, 0)
        fila.setSpacing(12)

        # Marca + versión, apiladas: antes la versión no vivía aquí (esta
        # barra se veía apretada contra "Archivo" en ventanas no muy
        # anchas con la marca en una sola línea) y en su lugar se repetía
        # en el riel de navegación (brandLabel/versionLabel). Con la barra
        # ya más alta para dos líneas, la marca+versión viven una sola vez,
        # más grandes, y el riel ya no las repite (ver _build_nav_rail).
        marca = QLabel("TDT & Radio VIP")
        marca.setObjectName("titleBrand")
        marca.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        version_label = QLabel(f"Versión {cfg.APP_VERSION}")
        version_label.setObjectName("titleVersion")
        version_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        # La marca vive en una columna de ancho fijo, igual que el riel
        # lateral de debajo (NAV_RAIL_WIDTH): asi el menu que viene a
        # continuacion arranca siempre en el mismo punto que el panel de
        # contenido (donde esta "Inicio"), sin depender de cuanto mida el
        # texto de la marca.
        marca_col = QWidget()
        marca_col.setFixedWidth(NAV_RAIL_WIDTH - fila.contentsMargins().left())
        marca_col_layout = QVBoxLayout(marca_col)
        marca_col_layout.setContentsMargins(0, 0, 0, 0)
        marca_col_layout.setSpacing(0)
        marca_col_layout.addStretch(1)
        marca_col_layout.addWidget(marca)
        marca_col_layout.addWidget(version_label)
        marca_col_layout.addStretch(1)
        fila.addWidget(marca_col)

        fila.addWidget(self._build_menu())

        # Zona vacía: es la que permite arrastrar la ventana.
        fila.addStretch(1)

        min_btn = QToolButton()
        min_btn.setObjectName("winCtrlButton")
        min_btn.setText("\u2013")
        min_btn.setCursor(Qt.PointingHandCursor)
        min_btn.setToolTip("Minimizar")
        min_btn.clicked.connect(self.showMinimized)
        fila.addWidget(min_btn)

        self._maximize_btn = QToolButton()
        self._maximize_btn.setObjectName("winCtrlButton")
        self._maximize_btn.setText("\u25A1")
        self._maximize_btn.setCursor(Qt.PointingHandCursor)
        self._maximize_btn.setToolTip("Maximizar")
        self._maximize_btn.clicked.connect(self.window_chrome.toggle_maximize)
        fila.addWidget(self._maximize_btn)

        close_btn = QToolButton()
        close_btn.setObjectName("winCloseButton")
        close_btn.setText("\u00D7")
        close_btn.setCursor(Qt.PointingHandCursor)
        close_btn.setToolTip("Cerrar")
        close_btn.clicked.connect(self.close)
        fila.addWidget(close_btn)

        barra.installEventFilter(self)
        return barra

    def _build_menu(self) -> QMenuBar:
        menu = QMenuBar()
        menu.setObjectName("appMenuBar")
        menu.setNativeMenuBar(False)
        self.menu_bar = menu

        file_menu = menu.addMenu("Archivo")
        global_search_action = QAction("Búsqueda global…", self)
        global_search_action.setShortcut(QKeySequence("Ctrl+K"))
        global_search_action.triggered.connect(self._open_command_palette)
        file_menu.addAction(global_search_action)
        file_menu.addSeparator()

        refresh_tv_action = QAction("Actualizar canales TV", self)
        refresh_tv_action.triggered.connect(lambda: self.catalog.load_tv_channels(force=True))
        file_menu.addAction(refresh_tv_action)

        refresh_radio_action = QAction("Actualizar emisoras de radio", self)
        refresh_radio_action.triggered.connect(lambda: self.catalog.load_radio_stations(force=True))
        file_menu.addAction(refresh_radio_action)

        diagnostics_action = QAction("Diagnosticar canales y emisoras…", self)
        diagnostics_action.triggered.connect(self._open_stream_diagnostics)
        file_menu.addAction(diagnostics_action)

        file_menu.addSeparator()
        add_entry_action = QAction("Añadir canal o emisora…", self)
        add_entry_action.triggered.connect(self.library.open_add_entry_dialog)
        file_menu.addAction(add_entry_action)

        import_action = QAction("Importar lista M3U…", self)
        import_action.triggered.connect(self.library.open_import_playlist_dialog)
        file_menu.addAction(import_action)

        add_public_tv_list_action = QAction("Añadir lista pública de TV…", self)
        add_public_tv_list_action.triggered.connect(self.library.open_add_public_tv_list_dialog)
        file_menu.addAction(add_public_tv_list_action)

        editor_m3u_action = QAction("Editor M3U…", self)
        editor_m3u_action.triggered.connect(self.library.open_m3u_editor)
        file_menu.addAction(editor_m3u_action)

        import_tv_action = QAction("Importar lista de TV...", self)
        import_tv_action.triggered.connect(lambda: self.library.open_import_playlist_dialog("tv"))
        file_menu.addAction(import_tv_action)

        import_radio_action = QAction("Importar lista de radio...", self)
        import_radio_action.triggered.connect(lambda: self.library.open_import_playlist_dialog("radio"))
        file_menu.addAction(import_radio_action)

        export_playlist_action = QAction("Exportar lista M3U…", self)
        export_playlist_action.triggered.connect(self.library.export_current_playlist)
        file_menu.addAction(export_playlist_action)

        export_tv_action = QAction("Exportar lista de TV...", self)
        export_tv_action.triggered.connect(lambda: self.library.export_current_playlist("tv"))
        file_menu.addAction(export_tv_action)

        export_radio_action = QAction("Exportar lista de radio...", self)
        export_radio_action.triggered.connect(lambda: self.library.export_current_playlist("radio"))
        file_menu.addAction(export_radio_action)

        manage_action = QAction("Gestionar canales personalizados…", self)
        manage_action.triggered.connect(lambda: self.library.open_manage_channels_dialog())
        file_menu.addAction(manage_action)

        file_menu.addSeparator()
        recordings_action = QAction("Biblioteca de grabaciones…", self)
        recordings_action.triggered.connect(self.library.open_recordings_library)
        file_menu.addAction(recordings_action)

        recurring_action = QAction("Grabaciones recurrentes…", self)
        recurring_action.triggered.connect(self._open_recurring_dialog)
        file_menu.addAction(recurring_action)

        scheduled_action = QAction("Centro de grabaciones programadas…", self)
        scheduled_action.triggered.connect(self._open_scheduled_recordings_dialog)
        file_menu.addAction(scheduled_action)

        mosaic_action = QAction("Multivista (mosaico)…", self)
        mosaic_action.triggered.connect(self._open_mosaic_view)
        file_menu.addAction(mosaic_action)

        file_menu.addSeparator()
        export_backup_action = QAction("Exportar copia de seguridad…", self)
        export_backup_action.triggered.connect(self.library.export_backup)
        file_menu.addAction(export_backup_action)

        import_backup_action = QAction("Importar copia de seguridad…", self)
        import_backup_action.triggered.connect(self.library.import_backup)
        file_menu.addAction(import_backup_action)

        file_menu.addSeparator()
        exit_action = QAction("Salir", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        settings_menu = menu.addMenu("Configuración")
        settings_action = QAction("Preferencias…", self)
        settings_action.triggered.connect(self._open_settings)
        settings_menu.addAction(settings_action)

        help_menu = menu.addMenu("Ayuda")
        about_action = QAction("Acerca de", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

        stats_action = QAction("Estadísticas de uso…", self)
        stats_action.triggered.connect(self._open_stats_dialog)
        help_menu.addAction(stats_action)

        update_action = QAction("Buscar actualizaciones", self)
        update_action.triggered.connect(self.updates.check_for_update)
        help_menu.addAction(update_action)

        logs_action = QAction("Abrir carpeta de logs", self)
        logs_action.triggered.connect(self._abrir_carpeta_logs)
        help_menu.addAction(logs_action)

        return menu

    def _open_stream_diagnostics(self):
        dialog = StreamDiagnosticsDialog(self.tv_channels_data, self.radio_stations_data, self)
        dialog.exec()
        self.home.refresh_home_health()
        if dialog.catalog_changed and not self._is_closing:
            self.catalog.load_tv_channels()
            self.catalog.load_radio_stations()

    def _open_command_palette(self):
        """
        Búsqueda global (Ctrl+K / menú Archivo). Las "acciones rápidas" se
        arman aquí, no dentro de CommandPalette, para que ese módulo no
        tenga que importar NAV_HOME/NAV_TV/etc. de este archivo (crearía un
        import circular, ya que este archivo importa CommandPalette).
        """
        acciones = [
            ("Preferencias…", self._open_settings),
            ("Ir a Inicio", lambda: self.nav_group.button(NAV_HOME).click()),
            ("Ir a Televisión", lambda: self.nav_group.button(NAV_TV).click()),
            ("Ir a Radio", lambda: self.nav_group.button(NAV_RADIO).click()),
            ("Ir a Favoritos", lambda: self.nav_group.button(NAV_FAV).click()),
            ("Ir a Historial", lambda: self.nav_group.button(NAV_HIST).click()),
            ("Añadir canal o emisora…", self.library.open_add_entry_dialog),
            ("Importar lista M3U…", self.library.open_import_playlist_dialog),
            ("Añadir lista pública de TV…", self.library.open_add_public_tv_list_dialog),
            ("Gestionar canales personalizados…", lambda: self.library.open_manage_channels_dialog()),
        ]

        dialog = CommandPalette(self, acciones)
        dialog.show_centered()

    def eventFilter(self, obj, event):
        """
        Delega en WindowChrome (arrastre de ventana, maximizar/restaurar,
        doble clic para pantalla completa). WindowChrome devuelve None
        cuando el evento no le interesa -- Qt exige entonces caer al
        comportamiento por defecto de QMainWindow, no un True/False propio.
        """
        if obj is getattr(self, "now_playing_bar", None) and event.type() == QEvent.Resize:
            self._update_now_playing_compact(event.size().width())
        if obj is getattr(self, "_home_viewport", None) and event.type() == QEvent.Resize:
            self.home.update_home_compact(event.size().width())
        result = self.window_chrome.event_filter(obj, event)
        if result is None:
            return super().eventFilter(obj, event)
        return result

    # Maximizar/restaurar, pantalla completa y modo PiP (antes _toggle_maximize
    # / _maximizar / _restaurar_tamano / _toggle_player_fullscreen /
    # _salir_fullscreen_si_activo / _toggle_pip_mode / _enter_pip_mode /
    # _exit_pip_mode / _enter_player_fullscreen / _exit_player_fullscreen)
    # viven ahora en ui.window_chrome.WindowChrome (self.window_chrome).

    # ---------- Temporizador de apagado ----------

    # El temporizador de apagado (antes _on_sleep_btn_clicked / _iniciar_sleep /
    # _cancelar_sleep / _update_sleep_tooltip / _on_sleep_timeout) vive ahora en
    # ui.playback_controller.PlaybackController -- ver self.playback mas arriba.

    def _registrar_atajos(self):
        """
        Atajos a nivel de ventana. Con keyPressEvent no bastaba: si el foco
        estaba en el campo de URL o en la lista de canales, el widget hijo se
        quedaba la pulsación y F11/Esc no llegaban nunca a la ventana.
        """
        atajo_fs = QShortcut(QKeySequence(Qt.Key_F11), self)
        atajo_fs.setContext(Qt.WindowShortcut)
        atajo_fs.activated.connect(self.window_chrome.toggle_player_fullscreen)

        atajo_salir = QShortcut(QKeySequence(Qt.Key_Escape), self)
        atajo_salir.setContext(Qt.WindowShortcut)
        atajo_salir.activated.connect(self.window_chrome.salir_fullscreen_si_activo)


    # ---------- Navegación ----------

    def showEvent(self, event):
        super().showEvent(event)
        # La ventana ya tiene HWND en este punto.
        if not self._native_icon_applied:
            self._native_icon_applied = True
            icon_path = cfg.get_icon_path()
            if icon_path:
                set_native_window_icon(int(self.winId()), icon_path)

        if not self._taskbar._ready:
            hwnd = int(self.winId())
            if self._taskbar.setup(hwnd):
                self._taskbar.bind(BTN_PREV, self.playback.play_prev)
                self._taskbar.bind(BTN_PLAY, self.playback.toggle_play)
                self._taskbar.bind(BTN_STOP, self.playback.stop_playback)
                self._taskbar.bind(BTN_MUTE, self.playback.toggle_mute)
                self._taskbar.bind(BTN_NEXT, self.playback.play_next)

    # _play_prev / _play_next viven ahora en PlaybackController (self.playback).

    def nativeEvent(self, eventType, message):
        """
        Enruta los mensajes nativos de Windows hacia TaskbarControls, para
        que los clics en los botones de la miniatura de la barra de tareas
        (prev/play/stop/mute/next al pasar el ratón por el icono) lleguen a
        algún sitio. Sin este método, TaskbarControls.on_windows_message()
        no lo llamaba nadie -- estaba escrito pero nunca conectado.
        """
        if eventType in (b"windows_generic_MSG", "windows_generic_MSG"):
            try:
                if self._taskbar.on_native_message(int(message)):
                    return True, 0
            except Exception:
                pass
        return super().nativeEvent(eventType, message)

    def _on_nav_changed(self, nav_id: int):
        previous_nav = self._current_nav_id
        if previous_nav in (NAV_TV, NAV_RADIO):
            kind = "tv" if previous_nav == NAV_TV else "radio"
            filters = dict(self.settings.get("catalog_filters") or {})
            # El filtro de categoría de TV ahora lo lleva GroupsSidebar (panel
            # lateral), no el desplegable group_filter -- se guarda como una
            # lista de nombres de grupo (antes era un único string de
            # group_filter.currentText(), de ahí el nombre de la clave).
            if previous_nav == NAV_TV and self._tv_sidebar_groups:
                group_state = sorted(self._tv_sidebar_groups)
            else:
                group_state = []
            filters[kind] = {
                "search": self.search_box.text(),
                "group": group_state,
                "health": self.health_filter.currentData() or "all",
            }
            self.settings["catalog_filters"] = filters
            cfg.save_settings(self.settings)

        self._current_nav_id = nav_id
        self.stack.setCurrentIndex(nav_id)
        self.section_title.setText(SECTION_TITLES[nav_id])
        self.section_title.setStyleSheet("")
        set_variant(self.section_title, SECTION_VARIANTS[nav_id])
        self.catalog.update_catalog_count()
        self.epg_btn.setVisible(nav_id == NAV_TV)
        self.tv_view_toggle.setVisible(nav_id in (NAV_TV, NAV_RADIO))
        # group_filter ya no se usa para TV -- lo sustituye groups_sidebar
        # (panel lateral con contador por grupo). Sigue siendo el filtro de
        # carpeta en Favoritos.
        self.group_filter.setVisible(nav_id == NAV_FAV)
        self.groups_sidebar.setVisible(nav_id == NAV_TV)
        self.catalog_sort.setVisible(nav_id in (NAV_TV, NAV_RADIO))
        self.health_filter.setVisible(nav_id in (NAV_TV, NAV_RADIO))
        if nav_id == NAV_TV:
            self.lists.refresh_group_filter()
            sort_key = self.settings.get("catalog_sort_tv", "source")
            self.catalog_sort.blockSignals(True)
            self.catalog_sort.setCurrentIndex(max(0, self.catalog_sort.findData(sort_key)))
            self.catalog_sort.blockSignals(False)
        elif nav_id == NAV_FAV:
            self.lists.refresh_folder_filter()
        elif nav_id == NAV_RADIO:
            sort_key = self.settings.get("catalog_sort_radio", "source")
            self.catalog_sort.blockSignals(True)
            self.catalog_sort.setCurrentIndex(max(0, self.catalog_sort.findData(sort_key)))
            self.catalog_sort.blockSignals(False)
        elif nav_id == NAV_HOME:
            self.home.refresh_home_page()
        self.search_box.setVisible(nav_id != NAV_HOME)
        if nav_id in (NAV_TV, NAV_RADIO):
            kind = "tv" if nav_id == NAV_TV else "radio"
            state = (self.settings.get("catalog_filters") or {}).get(kind, {})
            self.search_box.blockSignals(True)
            self.search_box.setText(state.get("search", ""))
            self.search_box.blockSignals(False)
            health_index = self.health_filter.findData(state.get("health", "all"))
            self.health_filter.blockSignals(True)
            self.health_filter.setCurrentIndex(max(0, health_index))
            self.health_filter.blockSignals(False)
            if nav_id == NAV_TV and state.get("group"):
                # state["group"] es una lista de nombres de grupo (ver el
                # guardado más arriba); refresh_group_filter() ya pobló
                # groups_sidebar justo antes, así que aquí solo hace falta
                # restaurar qué filas quedan seleccionadas.
                self._tv_sidebar_groups = set(state["group"])
                self.groups_sidebar.select_groups(self._tv_sidebar_groups)
        else:
            self.search_box.clear()
        if nav_id != NAV_HOME:
            self.lists.filter_current_list()
        if nav_id == NAV_TV:
            self.lists.load_visible_logos(self.tv_list)
        elif nav_id == NAV_RADIO:
            self.lists.load_visible_logos(self.radio_list)
        elif nav_id == NAV_FAV:
            self.lists.load_visible_logos(self.fav_list)
        self._animate_page(self.stack.currentWidget())

    # _update_catalog_count vive ahora en
    # ui.catalog_load_controller.CatalogLoadController (self.catalog).

    def _animate_page(self, widget: QWidget):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(220)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.finished.connect(lambda: widget.setGraphicsEffect(None))
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        self._fade_anim = anim

    # _load_tv_channels / _on_tv_channels_loaded / _load_radio_stations /
    # _on_radio_stations_loaded / _maybe_start_background_diagnostics /
    # _on_background_diagnostics_completed viven ahora en
    # ui.catalog_load_controller.CatalogLoadController (self.catalog).

    # _open_epg_dialog / _tune_to_tvg_id / _load_epg / _on_epg_loaded viven
    # ahora en ui.epg_controller.EpgController (self.epg).

    def _open_recurring_dialog(self):
        RecurringRecordingsDialog(self, self.tv_channels_data).exec()

    def _open_scheduled_recordings_dialog(self):
        ScheduledRecordingsDialog(self).exec()

    def _open_mosaic_view(self):
        if not self.tv_channels_data:
            QMessageBox.information(
                self, "Multivista", "Espera a que carguen los canales de TV."
            )
            return

        # La multivista abre hasta 4 instancias de VLC en paralelo (ver
        # ui/mosaic_view.py) -- sumadas a la del reproductor principal, son
        # 5 streams compitiendo a la vez por el dispositivo de audio, que en
        # Windows es lo que dejaba mudo al canal principal al cerrar la
        # multivista (seguía "reproduciendo" pero sin sonido, y hacía falta
        # reiniciar la app). Se para del todo mientras el diálogo está
        # abierto -- no se ve de todas formas, tapa la ventana entera -- y
        # se retoma desde cero (media_player limpio, ver VLCPlayer.play) al
        # cerrarlo.
        reanudar = None
        if self.current_url:
            reanudar = (
                self.current_type, self.current_name, self.current_url,
                self.current_tvg_id, self.current_logo,
            )
            self.player.stop()
            self.equalizer.stop()

        MosaicView(self, self.tv_channels_data).exec()

        if reanudar is not None:
            self.playback.play(*reanudar)

    def _open_stats_dialog(self):
        StatsDialog(self).exec()

    def _run_automatic_backup(self):
        if self._is_closing:
            return
        previous = getattr(self, "_backup_worker", None)
        if previous is not None and previous.isRunning():
            return
        try:
            worker = FetchWorker(
                backup_module.run_automatic_backup,
                cfg.get_app_data_dir() / "backups",
                interval_days=int(self.settings.get("automatic_backup_interval_days", 1)),
                retention=int(self.settings.get("automatic_backup_retention", 7)),
                app_data_dir=cfg.get_app_data_dir(),
                profile_data_dir=cfg.get_profile_data_dir(),
            )
        except (OSError, ValueError):
            self.statusBar().showMessage("No se pudo crear la copia automática.", 5000)
            return
        worker.done.connect(self._on_automatic_backup_done)
        self._backup_worker = worker
        worker.start()

    def _on_automatic_backup_done(self, result):
        if self._is_closing:
            return
        if result is None:
            self.statusBar().showMessage("No se pudo crear la copia automática.", 5000)
        elif result:
            self.statusBar().showMessage("Copia de seguridad automática creada.", 4000)

    def _check_update_automatically(self):
        """
        Comprobación silenciosa al arrancar (como mucho una vez al día, ver
        core.updater.check_for_update_if_due) -- si hay una versión nueva,
        avisa con un toast no bloqueante; si no la hay, si la URL está
        vacía o si ya se comprobó hoy, no hace nada visible. Nunca
        descarga ni instala sola -- ver _on_automatic_update_check_done()
        para lo que pasa si el usuario pulsa "Ver".
        """
        if self._is_closing:
            return
        url = self.settings.get("update_check_url", "")
        if not url:
            return
        worker = FetchWorker(
            updater.check_for_update_if_due,
            url,
            cfg.get_app_data_dir() / "updates",
            cfg.APP_VERSION,
        )
        worker.done.connect(self._on_automatic_update_check_done)
        self._auto_update_check_worker = worker
        worker.start()

    def _on_automatic_update_check_done(self, resultado):
        if self._is_closing or not resultado:
            return
        version = resultado.get("version", "?")
        show_toast(
            self, f"Hay una actualización disponible: {version}",
            undo_text="Ver",
            on_undo=lambda: self.updates.on_update_check_done(resultado),
            timeout_ms=12000,
        )

    def _resume_last_stream(self):
        if self._is_closing or self.current_url or not self.history:
            return
        entry = self.history[0]
        if entry.get("url") and entry.get("type") in ("tv", "radio"):
            self.playback.play(
                entry["type"], entry.get("name", "Última emisión"), entry["url"],
                entry.get("tvg_id", ""), entry.get("logo", ""),
            )

    # check_for_update / on_update_check_done / _on_update_download_done
    # viven ahora en ui.update_check_controller.UpdateCheckController
    # (self.updates).

    # ---------- Añadir canal/emisora manual e importar listas M3U ----------
    #
    # _open_add_entry_dialog / _edit_custom_entry / _delete_custom_entry /
    # _open_import_playlist_dialog / _fetch_playlist_text / _on_playlist_fetched /
    # _exportar_backup / _importar_backup viven ahora en
    # ui.library_controller.LibraryController (self.library).

    # ---------- Poblar listas ----------

    # _request_logo / _populate_tv_list / _populate_radio_list /
    # _refresh_favorites_tab / _refresh_history_tab / _mark_playing_everywhere /
    # _mark_favorites_everywhere / _filter_current_list viven ahora en
    # ChannelListsController (self.lists).

    # ---------- Reproducción ----------

    # _on_item_activated / _activate_item / _auto_skip_next viven ahora en
    # PlaybackController (self.playback).

    # _show_context_menu / _hide_public_tv_channel / _delete_tv_groups /
    # _mover_a_carpeta / _toggle_favorite_for viven ahora en
    # ui.channel_menu_controller.ChannelMenuController (self.channel_menu).

    # _play / _update_now_logo / _toggle_play / _on_player_error /
    # _on_player_end_reached / _retry_playback / _stop_playback /
    # _on_volume_changed / _toggle_mute / _toggle_favorite_current /
    # _toggle_recording / _update_epg_display viven ahora en
    # PlaybackController (self.playback).

    # ---------- Configuración ----------

    def _open_settings(self):
        old_tv_url = self.settings.get("tv_playlist_url") or tv_channels.playlist_url_for(
            self.settings.get("tv_country_code", "ES")
        )
        old_radio_country = self.settings.get("radio_country_code", "ES")
        old_accent = self.settings.get("accent_color", palette.ACCENT)
        old_theme = self.settings.get("theme_mode", "dark")
        old_card_size = int(self.settings.get("catalog_card_size", 168))
        old_profile = self.settings.get("active_profile", "Default")
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() == QDialog.Accepted:
            new_settings = dialog.get_settings()
            if not cfg.save_settings(new_settings):
                QMessageBox.warning(
                    self,
                    "No se pudieron guardar los ajustes",
                    "No se pudieron guardar los ajustes. Inténtalo de nuevo.",
                )
                return
            self.settings = new_settings

            new_profile = self.settings.get("active_profile", "Default")
            if new_profile != old_profile:
                QMessageBox.information(
                    self, "Perfil cambiado",
                    f"Perfil activo: {new_profile}.\n\n"
                    "Cierra y vuelve a abrir la aplicación para que se aplique del todo."
                )
            self.recordings_dir = self.settings.get("recordings_dir") or self.downloads_dir
            if not self.recorder.is_recording:
                self.recorder = rec_module.Recorder(self.recordings_dir)
                self.recordings_dir = str(self.recorder.output_dir)
            if self.settings.get("epg_url"):
                self.epg.load()

            new_accent = self.settings.get("accent_color", palette.ACCENT)
            new_theme = self.settings.get("theme_mode", "dark")
            if new_accent != old_accent or new_theme != old_theme:
                app = QApplication.instance()
                if app is not None:
                    app.setStyleSheet(build_style(new_accent, new_theme))

            new_card_size = int(self.settings.get("catalog_card_size", 168))
            if new_card_size != old_card_size:
                self.grid_delegate.CARD_SIZE = new_card_size
                if self.tv_view_toggle.isChecked():
                    grid_size = QSize(new_card_size, new_card_size)
                    self.tv_list.setGridSize(grid_size)
                    self.radio_list.setGridSize(grid_size)

            new_tv_url = self.settings.get("tv_playlist_url") or tv_channels.playlist_url_for(
                self.settings.get("tv_country_code", "ES")
            )
            if new_tv_url != old_tv_url:
                self.catalog.load_tv_channels()
            if self.settings.get("radio_country_code", "ES") != old_radio_country:
                self.catalog.load_radio_stations()

    def _abrir_carpeta_logs(self):
        carpeta = log_file_path().parent
        carpeta.mkdir(parents=True, exist_ok=True)
        os.startfile(carpeta)

    def _show_about(self):
        if self.es_version_free:
            registro_html = (
                f"<p style='font-size:13pt; font-weight:700; color:{palette.ACCENT_INFO};'>"
                "Versión FREE — TV y Radio incluidos, sin Descargas ni Chromecast</p>"
            )
        elif self.activated:
            registro_html = (
                f"<p style='font-size:13pt; font-weight:700; color:{palette.SUCCESS};'>"
                "Aplicación registrada</p>"
            )
        else:
            registro_html = (
                f"<p style='font-size:13pt; font-weight:700; color:{palette.DANGER};'>"
                "Versión no activada</p>"
            )
        QMessageBox.about(
            self, "Acerca de",
            f"<b>TDT & Radio VIP</b> — versión {cfg.APP_VERSION}<br>"
            "Coder By X@R<br><br>"
            f"{registro_html}"
            "Reproductor de canales de TDT y radio online gratuitos.<br>"
            "Fuentes: iptv-org (TV) y Radio-Browser (radio).<br><br>"
            "La disponibilidad y calidad de los streams depende de terceros ajenos a esta aplicación.<br><br>"
            "<table width='100%' cellpadding='12' cellspacing='0' bgcolor='#1b2a41' "
            "style='border:1px solid #c9a227; border-radius:10px;'>"
            "<tr><td>"
            "<b style='color:#c9a227; font-size:12pt;'>TDTChannels</b><br>"
            "Proporciona listas oficiales y legales de television terrestre en Espana "
            "en formato M3U y M3U8.<br>"
            f"<a href='https://www.tdtchannels.com/lists/tv.m3u8' style='color:{palette.ACCENT_INFO};'>"
            "https://www.tdtchannels.com/lists/tv.m3u8</a>"
            "</td></tr></table><br>"
            "<hr>"
            f"<b style='color:{palette.ACCENT};'>&#10084; Un Abrazo grande a mi hijo Hugo Moreno &#161;ERES UN CAMPE&#211;N! &#10084;</b><br>"
            f"<b style='color:{palette.ACCENT};'>&#10084; Besitos a Evelyn Llamas &#10084;</b><br>"
            "Saludos a mi amigo Paco Blanco.<br>"
            "Viva La Guardia Civil — SANCHEZ CABRON:<br>"
            "<b>¡España Campeona del Mundo! "
            "<img src='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAB4AAAAUCAIAAAAVyRqTAAAALUlEQVR4nGNcJSrNQBvARCNzR43GBIwf99PK6KEZIKNGjxo9YEYzjhaqw8FoABs0A4rK4LUlAAAAAElFTkSuQmCC' width='24' height='16'> "
            "&#127942; &#128170; ¡OLÉ, LA UCO!</b><br><br>"
            "Ceuta y Melilla Españolas siempre! Ole Mi Juanito Gordito Y Aitor Super CARS! Edu The Punicher . "
            "<img src='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAB4AAAAUCAIAAAAVyRqTAAAALUlEQVR4nGNcJSrNQBvARCNzR43GBIwf99PK6KEZIKNGjxo9YEYzjhaqw8FoABs0A4rK4LUlAAAAAElFTkSuQmCC' width='24' height='16'>"
        )

    def closeEvent(self, event):
        if self._is_closing:
            event.ignore()
            return
        self._is_closing = True
        FetchWorker.begin_shutdown()
        reminder_timer = getattr(self, "_reminder_timer", None)
        if reminder_timer is not None:
            reminder_timer.stop()
        self._tray_icon.hide()
        self._media_keys.stop()
        if self.recorder.is_recording:
            # on_wait bombea eventos sin entrada de usuario: sin esto, cerrar la app
            # con una grabación en curso bloqueaba el hilo de la interfaz
            # mientras ffmpeg terminaba de cerrar el archivo -- Windows
            # llegaba a marcar la ventana como "no responde" antes de que
            # terminara. Ver core.recorder.Recorder.stop().
            self.recorder.stop(on_wait=process_events_during_shutdown)
            if self._scheduled_recording_active is not None:
                rec = self._scheduled_recording_active
                recording_schedule.mark_done(rec.tvg_id, rec.title, rec.start)
                self._scheduled_recording_active = None
        self.player.stop()
        self.equalizer.stop()
        self._taskbar.cleanup()
        shutdown_workers(FetchWorker.active_workers())
        self.player.release()
        event.accept()
