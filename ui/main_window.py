"""
Ventana principal de TDT & Radio VIP — interfaz moderna.
Coder By X@R
"""
import os
from functools import partial
from pathlib import Path
from typing import Optional

from PySide6.QtCore import (
    QEasingCurve, QEvent, QPropertyAnimation, QSize, Qt, QTimer,
)
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QDialog, QGraphicsOpacityEffect, QHBoxLayout, QListWidget, QMainWindow, QMessageBox,
    QSizeGrip, QSplitter, QStackedWidget,
    QVBoxLayout, QWidget,
)

from core import config as cfg
from core.logger import log_file_path
from core import channels as tv_channels
from core import favorites as fav_store
from core import history as hist_store
from core import recorder as rec_module
from core import recording_schedule
from core import backup as backup_module
from ui.dialogs import SettingsDialog
from ui.equalizer_dialog import EqualizerDialog
from ui.style import build_style
from ui.visual import set_variant
from ui import palette
from ui.channel_menu_controller import ChannelMenuController
from ui.catalog_load_controller import CatalogLoadController
from ui.home_controller import HomeController
from ui.catalog_toolbar import build_top_bar
from ui.home_page_builder import build_home_page
from ui.nav_rail import build_nav_rail, on_groups_sidebar_changed, open_favorites_folder
from ui.now_playing_bar_builder import update_now_playing_bar_compact
from ui.player_panel_builder import build_player_panel
from ui.title_bar import build_title_bar
from ui.channel_lists_controller import ChannelListsController
from ui.channel_model import ChannelListModel, ChannelListView
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
from ui.widgets import ChannelDelegate, ChannelGridDelegate, LogoLoader
# Reexportadas para no romper `from ui.main_window import NAV_TV` (usado
# como import tardío por ui.catalog_load_controller, ui.epg_controller y
# ui.window_chrome para evitar un ciclo). Las constantes viven en
# ui.nav_sections desde el refactor de main_window.py.
from ui.nav_sections import (
    NAV_DOWNLOAD, NAV_FAV, NAV_HIST, NAV_HOME, NAV_RADIO, NAV_TV,
    SECTION_TITLES, SECTION_VARIANTS,
)

DEFAULT_DOWNLOADS_DIRNAME = "TDT Radio VIP"


class MainWindow(QMainWindow):
    def __init__(self, activated: bool = False, es_version_free: bool = False):
        super().__init__()
        self._is_closing = False
        self.activated = activated
        # Distingue "activado de verdad con un código" de "versión Free,
        # desbloqueada por defecto" — main_free.py pasa activated=True para
        # abrir la reproducción de TV/radio sin pedir código, pero eso no es
        # lo mismo que un cliente que sí ha activado con su código real.
        # Descargas y Chromecast (ver más abajo: NAV_DOWNLOAD, cast_btn, y
        # la entrada "Ir a Descargas" de la paleta de comandos) exigen
        # además "not es_version_free" -- si no, activated=True en
        # main_free.py las desbloquearía igual que en un cliente con
        # licencia real, contradiciendo lo que anuncia el propio diálogo
        # "Acerca de" ("sin Descargas ni Chromecast").
        self.es_version_free = es_version_free
        self.setObjectName("mainWindowRoot")
        self.setWindowTitle(f"TDT & Radio VIP {cfg.APP_VERSION} — Coder By X@R")
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        # El LibrarySidebar (Recientes/Playlists) arranca OCULTO a propósito
        # (ver ui.nav_rail.build_nav_rail/toggle_library_sidebar): con él visible por
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
        # Cast (Chromecast/DLNA) no está incluido en la versión free (ver
        # _show_about). Los imports de core.caster/core.dlna_caster (y por
        # tanto de pychromecast/zeroconf) se hacen aquí dentro, no arriba del
        # módulo, para que TDTRadioVIP_Free.spec pueda excluir esos paquetes
        # de verdad -- un import a nivel de módulo los habría colado en el
        # build free sin importar este condicional (PyInstaller analiza el
        # árbol de imports estáticamente). self.casting/cast_btn/
        # download_panel siguen el mismo criterio más abajo.
        if self.es_version_free:
            self._cast_session = None
            self._dlna_session = None
        else:
            from core.caster import CastSession
            from core.dlna_caster import DLNASession
            self._cast_session = CastSession()
            self._dlna_session = DLNASession()
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
        if self.es_version_free:
            self.casting = None
        else:
            from ui.cast_controller import CastController
            self.casting = CastController(self)
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

        self.title_bar = build_title_bar(self)
        raiz_v.addWidget(self.title_bar)

        cuerpo = QWidget()
        root = QHBoxLayout(cuerpo)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.nav_rail = build_nav_rail(self)
        root.addWidget(self.nav_rail)

        # Sidebar de biblioteca (Recientes + Playlists = carpetas de
        # favoritos), estilo Spotify: panel aditivo entre el riel de
        # iconos y el contenido principal, colapsable con el botón de
        # abajo del todo en el riel. No sustituye a las pestañas de
        # Favoritos/Historial -- es un atajo hacia ellas.
        self.library_sidebar = LibrarySidebar(self, partial(open_favorites_folder, self))
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
        self.groups_sidebar = GroupsSidebar(partial(on_groups_sidebar_changed, self), self.channel_menu.delete_tv_groups)
        self.groups_sidebar.setVisible(False)
        root.addWidget(self.groups_sidebar)

        content = QVBoxLayout()
        content.setContentsMargins(16, 18, 12, 16)
        content.setSpacing(16)
        content.addLayout(build_top_bar(self))
        content.addWidget(self._build_content_stack(), stretch=1)

        # Se aplica después de crear las listas: el botón vive en la barra
        # superior, que se construye antes que el QStackedWidget.
        self.tv_view_toggle.setChecked(bool(self.settings.get("catalog_grid_view", False)))

        # setChecked(True) sobre el botón de Inicio (ui.nav_rail.build_nav_rail)
        # no dispara idClicked por sí solo — solo lo hace
        # un clic real del usuario. Sin esto, la portada se abriría vacía
        # hasta que el usuario cambiara de sección y volviera a Inicio.
        self._on_nav_changed(NAV_HOME)

        self.content_widget = QWidget()
        self.content_widget.setLayout(content)
        # Mínimo real: por debajo de esto, el título + filtro de categoría +
        # buscador de la barra superior no caben y se cortan (era el bug del
        # buscador cortado). El splitter no puede arrastrarse más allá.
        self.content_widget.setMinimumWidth(330)

        player_panel = build_player_panel(self)
        # La fila de controles ya no crece con el número de funciones: las
        # cinco acciones secundarias (pistas, pantalla completa, PiP,
        # temporizador, cola) que antes tenían un botón circular propio y
        # obligaban a un mínimo de 430px ahora viven en un único botón
        # "Más opciones" (ver ui.now_playing_bar_builder.build_now_playing_bar). 300px sigue dejando
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

    # _build_nav_rail / _toggle_library_sidebar / _open_favorites_folder /
    # _on_groups_sidebar_changed viven ahora en ui.nav_rail.

    # _build_top_bar / _on_catalog_sort_changed / _toggle_tv_grid_view
    # viven ahora en ui.catalog_toolbar.


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
        # Descargas (Torrents/Soulseek/audio/Podcasts) no está incluido en
        # la versión free -- ver el comentario junto a self._cast_session
        # sobre por qué el import va aquí dentro y no arriba del módulo.
        self.download_panel = None
        self._download_host = None
        if not self.es_version_free:
            self._download_host = QWidget()
            download_layout = QVBoxLayout(self._download_host)
            download_layout.setContentsMargins(0, 0, 0, 0)
        self.home_page = build_home_page(self)

        pages = [self.home_page, self.tv_list, self.radio_list, self.fav_list, self.hist_list]
        if self._download_host is not None:
            pages.append(self._download_host)
        for page in pages:
            self.stack.addWidget(page)

        return self.stack

    def _ensure_download_panel(self):
        if self.es_version_free or self._is_closing or self.download_panel is not None:
            return
        from ui.download_panel import DownloadPanel
        self.download_panel = DownloadPanel(
            dest_dir=self.downloads_dir,
            on_dest_changed=self._on_downloads_dir_changed,
            on_cast=self.casting.cast_local_file,
            on_finished=self._on_download_finished,
            on_play_audio=self._play_podcast_episode,
        )
        self._download_host.layout().addWidget(self.download_panel)

    # _build_home_page vive ahora en ui.home_page_builder.build_home_page().
    # _update_home_compact / _home_resume_or_search / _refresh_home_now_playing /
    # _refresh_home_page / _refresh_home_health / _activate_home_entry /
    # _compute_recommendations viven ahora en
    # ui.home_controller.HomeController (self.home).

    def _on_downloads_dir_changed(self, new_dir: str):
        self.downloads_dir = new_dir
        self.settings["downloads_dir"] = new_dir
        if not cfg.save_settings(self.settings):
            QMessageBox.warning(
                self,
                "No se pudieron guardar los ajustes",
                "No se pudieron guardar los ajustes. Inténtalo de nuevo.",
            )

    def _on_download_finished(self, nombre: str, _ruta: str):
        """
        Aviso de bandeja al terminar una descarga -- útil sobre todo si la
        ventana estaba minimizada mientras se descargaba algo largo, para
        no tener que ir comprobando la pestaña de Descargas a mano.
        """
        self.tray.notify("Descarga completada", nombre)

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

    # _active_cast_session / _on_cast_live_clicked / _cast_local_file /
    # _open_cast_picker_and_send viven ahora en
    # ui.cast_controller.CastController (self.casting).

    def _play_podcast_episode(self, url: str, title: str):
        """
        Reproduce un episodio de podcast (pestaña Descargas > Podcasts) con
        el mismo reproductor de audio que la radio -- un episodio de
        podcast no es más que una URL de audio, así que se reutiliza
        PlaybackController.play() en vez de montar un reproductor aparte.
        """
        self.playback.play("radio", title, url)

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

    # _build_player_panel vive ahora en ui.player_panel_builder.build_player_panel().


    def set_live_badge_visible(self, visible: bool) -> None:
        """Sincroniza el indicador visual con la emisión actual."""
        self.live_badge.setVisible(bool(visible))
        if visible:
            self.live_badge.raise_()

    # make_glow/make_separator viven ahora en ui/visual.py (funciones sin
    # estado, no dependían de self).

    # _build_now_playing_bar / _update_now_playing_compact viven ahora en
    # ui.now_playing_bar_builder.


    # _open_more_controls_menu / _show_stream_technical_info /
    # _open_tracks_menu viven ahora en ui.player_menus.


    # _build_title_bar vive ahora en ui.title_bar.build_title_bar().
    # _build_menu vive ahora en ui.app_menu.build_menu_bar().

    def _open_activation_dialog(self):
        """
        Configuración > Activar VIP…: reabre el diálogo de activación para
        quien entró en modo gratuito. Si la activación es correcta, las
        funciones VIP se desbloquean en la misma sesión: los accesos a
        Descargas y la paleta de comandos ya consultan self.activated al
        vuelo, así que solo hay que actualizar lo que se decidió al
        construir la ventana (el botón de enviar a TV y esta entrada de menú).

        Import local (no arriba del módulo): esta ruta solo se conecta a un
        menú cuando not self.es_version_free (ver ui.app_menu.build_menu_bar), así que
        ui.splash -- y core.license, que importa a su vez -- no hace falta
        que se carguen nunca en la edición free. Mismo motivo que
        core.caster/ui.download_panel más arriba (ver __init__).
        """
        from ui.splash import SplashDialog

        dialog = SplashDialog(self, show_profile_selector=False)
        dialog.exec()
        if dialog.activated and not self.activated:
            self.activated = True
            self.cast_btn.setVisible(True)
            self.activate_vip_action.setVisible(False)
            self.statusBar().showMessage("Funciones VIP activadas. ¡Gracias!", 6000)

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
            ("Gestionar canales personalizados…", lambda: self.library.open_manage_channels_dialog()),
        ]
        if self.activated and not self.es_version_free:
            acciones.append(("Ir a Descargas", lambda: self.nav_group.button(NAV_DOWNLOAD).click()))

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
            update_now_playing_bar_compact(self, event.size().width())
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
        if nav_id == NAV_DOWNLOAD:
            if self.es_version_free:
                return
            self._ensure_download_panel()
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
        self.search_box.setVisible(nav_id not in (NAV_DOWNLOAD, NAV_HOME))
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
        if nav_id not in (NAV_DOWNLOAD, NAV_HOME):
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

    def _resume_last_stream(self):
        if self._is_closing or self.current_url or not self.history:
            return
        entry = self.history[0]
        if entry.get("url") and entry.get("type") in ("tv", "radio"):
            self.playback.play(
                entry["type"], entry.get("name", "Última emisión"), entry["url"],
                entry.get("tvg_id", ""), entry.get("logo", ""),
            )

    # _check_for_update / _on_update_check_done / _on_update_download_done
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
        if self._cast_session is not None:
            self._cast_session.disconnect()
            self._dlna_session.disconnect()
        if self.download_panel is not None:
            # on_wait: se reenvía por compatibilidad con la firma anterior
            # (ver el comentario del recorder.stop() más arriba) -- con
            # libtorrent embebido en el proceso ya no hay un aria2c.exe
            # aparte que esperar a que se apague, así que en la práctica ya
            # no bloquea nada.
            self.download_panel.shutdown(on_wait=process_events_during_shutdown)
        self._taskbar.cleanup()
        # El diagnóstico automático de streams corre en un QThread propio
        # que no pasa por ActiveWorkerRegistry (StreamDiagnosticsWorker no
        # es un FetchWorker) -- sin cancelarlo y esperarlo aquí, cerrar la
        # app mientras seguía corriendo lo dejaba vivo destruyéndose la
        # ventana debajo, la misma clase de carrera que ya se corrigió para
        # Torrents/Soulseek (ver CHANGELOG).
        diagnostics_worker = self.catalog.cancel_background_diagnostics()
        workers = FetchWorker.active_workers()
        if diagnostics_worker is not None:
            workers = (*workers, diagnostics_worker)
        shutdown_workers(workers)
        self.player.release()
        event.accept()
