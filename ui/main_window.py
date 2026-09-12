"""
Ventana principal de TDT & Radio VIP — interfaz moderna.
Coder By X@R
"""
from functools import partial
from pathlib import Path
from typing import Optional

from PySide6.QtCore import (
    QEvent, Qt,
)
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout, QListWidget, QMainWindow, QMessageBox,
    QSizeGrip, QSplitter, QStackedWidget,
    QVBoxLayout, QWidget,
)

from core import config as cfg
from core import favorites as fav_store
from core import history as hist_store
from core import recorder as rec_module
from core import recording_schedule
from ui.channel_menu_controller import ChannelMenuController
from ui.app_lifecycle import AppLifecycle
from ui.catalog_load_controller import CatalogLoadController
from ui.dialog_actions import DialogActionsController
from ui.home_controller import HomeController
from ui.keyboard_shortcuts import register_shortcuts
from ui.catalog_toolbar import build_top_bar
from ui.home_page_builder import build_home_page
from ui.nav_top import (
    build_nav_top, on_groups_sidebar_changed, open_favorites_folder, update_nav_top_compact,
)
from ui.navigation_controller import NavigationController
from ui.now_playing_bar_builder import update_now_playing_bar_compact
from ui.player_panel_builder import build_player_panel
from ui.title_bar import build_title_bar
from ui.channel_lists_controller import ChannelListsController
from ui.channel_model import ChannelListModel, ChannelListView
from ui.epg_controller import EpgController
from ui.groups_sidebar import GroupsSidebar
from ui.library_controller import LibraryController
from ui.library_sidebar import LibrarySidebar
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
from ui.nav_sections import NAV_HOME

DEFAULT_DOWNLOADS_DIRNAME = "TDT Radio VIP"

# ---------------------------------------------------------------------------
# Mapa de responsabilidades extraídas de MainWindow (refactor de
# main_window.py, ver la rama refactor/split-main-window). Todo lo listado
# aquí vivía antes como método de esta clase; se agrupa por módulo/
# controlador de destino en vez de repetir un comentario "vive ahora en..."
# junto a cada hueco que dejó.
#
# ui.tray_controller.TrayReminderController (self.tray):
#     _setup_tray_and_reminders, _check_epg_reminders, _check_scheduled_recordings,
#     _check_scheduled_recording_alive, _on_tray_message_clicked
# ui.app_lifecycle.AppLifecycle (self.lifecycle):
#     schedule_startup_tasks, show_onboarding, warn_vlc_unavailable,
#     run_automatic_backup, resume_last_stream, shutdown
# ui.nav_top (funciones de módulo):
#     _build_nav_top, _toggle_library_sidebar, _open_favorites_folder,
#     _on_groups_sidebar_changed, update_nav_top_compact (colapso a
#     solo-iconos, spec v8 §5.4)
# ui.catalog_toolbar (funciones de módulo):
#     _build_top_bar, _on_catalog_sort_changed, _toggle_tv_grid_view
# ui.home_page_builder.build_home_page(): _build_home_page
# ui.home_controller.HomeController (self.home):
#     _update_home_compact, _home_resume_or_search, _refresh_home_now_playing,
#     _refresh_home_page, _refresh_home_health, _activate_home_entry,
#     _compute_recommendations
# ui.dialog_actions.DialogActionsController (self.dialogs):
#     _open_equalizer_dialog, _open_activation_dialog, _open_stream_diagnostics,
#     _open_command_palette, _open_recurring_dialog, _open_scheduled_recordings_dialog,
#     _open_mosaic_view, _open_stats_dialog, _open_settings, _abrir_carpeta_logs,
#     _show_about
# ui.cast_controller.CastController (self.casting):
#     _active_cast_session, _on_cast_live_clicked, _cast_local_file,
#     _open_cast_picker_and_send
# ui.player_panel_builder.build_player_panel(): _build_player_panel
# ui.visual (funciones de módulo, sin estado): make_glow, make_separator
# ui.now_playing_bar_builder (funciones de módulo):
#     _build_now_playing_bar, _update_now_playing_compact
# ui.player_menus (funciones de módulo):
#     _open_more_controls_menu, _show_stream_technical_info, _open_tracks_menu
# ui.title_bar.build_title_bar(): _build_title_bar
# ui.more_menu (funciones de módulo, sustituyen a la QMenuBar clásica
# retirada -- ui.app_menu.build_menu_bar, spec v8 §5.2):
#     build_more_menu_button, build_global_search_button
# ui.window_chrome.WindowChrome (self.window_chrome):
#     _toggle_maximize, _maximizar, _restaurar_tamano, _toggle_player_fullscreen,
#     _salir_fullscreen_si_activo, _toggle_pip_mode, _enter_pip_mode,
#     _exit_pip_mode, _enter_player_fullscreen, _exit_player_fullscreen
# ui.playback_controller.PlaybackController (self.playback):
#     _on_sleep_btn_clicked, _iniciar_sleep, _cancelar_sleep, _update_sleep_tooltip,
#     _on_sleep_timeout, _play_prev, _play_next, _play, _update_now_logo,
#     _toggle_play, _on_player_error, _on_player_end_reached, _retry_playback,
#     _stop_playback, _on_volume_changed, _toggle_mute, _toggle_favorite_current,
#     _toggle_recording, _update_epg_display, _on_item_activated, _activate_item,
#     _auto_skip_next
# ui.navigation_controller.NavigationController (self.navigation):
#     _on_nav_changed, _animate_page
# ui.catalog_load_controller.CatalogLoadController (self.catalog):
#     _update_catalog_count, _load_tv_channels, _on_tv_channels_loaded,
#     _load_radio_stations, _on_radio_stations_loaded,
#     _maybe_start_background_diagnostics, _on_background_diagnostics_completed
# ui.epg_controller.EpgController (self.epg):
#     _open_epg_dialog, _tune_to_tvg_id, _load_epg, _on_epg_loaded
# ui.update_check_controller.UpdateCheckController (self.updates):
#     check_for_update, on_update_check_done, _on_update_download_done
# ui.library_controller.LibraryController (self.library):
#     _open_add_entry_dialog, _edit_custom_entry, _delete_custom_entry,
#     _open_import_playlist_dialog, _fetch_playlist_text, _on_playlist_fetched,
#     _exportar_backup, _importar_backup
# ui.channel_lists_controller.ChannelListsController (self.lists):
#     _request_logo, _populate_tv_list, _populate_radio_list,
#     _refresh_favorites_tab, _refresh_history_tab, _mark_playing_everywhere,
#     _mark_favorites_everywhere, _filter_current_list
# ui.channel_menu_controller.ChannelMenuController (self.channel_menu):
#     _show_context_menu, _hide_public_tv_channel, _delete_tv_groups,
#     _mover_a_carpeta, _toggle_favorite_for
# ---------------------------------------------------------------------------


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
        # (ver ui.nav_top.build_nav_top/toggle_library_sidebar): con él visible por
        # defecto la ventana necesitaba 210px de más, y en pantallas más
        # pequeñas la app se abría demasiado grande y con la barra de
        # controles y la barra superior apretadas. Quien lo quiera, lo
        # activa con el botón de biblioteca de la barra superior — sigue
        # disponible, solo que no ocupa sitio si no se pide.
        # El lienzo de Pencil se ha planteado a 1280 px: arrancar algo más
        # cerca de esa proporción deja respirar el catálogo, la emisión y
        # la navegación textual, sin obligar a maximizar la ventana.
        self.resize(1280, 760)
        # 1000px de mínimo era más de lo que la propia interfaz necesita:
        # al ser mayor que la mitad del ancho de muchas pantallas (p. ej.
        # 1920px ÷ 2 = 960), Windows no dejaba encajar la ventana en la
        # mitad de la pantalla ni al arrastrarla al borde izquierdo -- se
        # quedaba "a medias" (bug reportado).
        # 900 tenía margen sobre el desglose real de la interfaz cuando la
        # navegación era un riel lateral compartiendo fila con el contenido
        # (riel 76 + lista de canales 420 + panel de vídeo 300 + divisor
        # ≈ 800-820px). Con la navegación en su propia fila horizontal
        # (ui.nav_top, ver spec v8 §4.1) ese desglose ya no aplica: ahora
        # la barra de navegación es una restricción de ancho independiente
        # (7 pestañas de texto, sin colapso a iconos todavía -- ver spec v8
        # §5.4) que puede o no caber en 860px según la fuente/DPI real.
        # Pendiente de medir con la interfaz corriendo (ver plan Fase 1,
        # Task 2, Step 10) antes de dar este mínimo por bueno de nuevo.
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
        # ui.dialog_actions.DialogActionsController.show_about). Los imports
        # de core.caster/core.dlna_caster (y por
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
        self.dialogs = DialogActionsController(self)
        self.navigation = NavigationController(self)
        self.lifecycle = AppLifecycle(self)

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
        self.lifecycle.schedule_startup_tasks()

    # ---------- Construcción de la interfaz ----------

    def _build_ui(self):
        central = QWidget()
        central.setObjectName("appSurface")
        raiz_v = QVBoxLayout(central)
        raiz_v.setContentsMargins(0, 0, 0, 0)
        raiz_v.setSpacing(0)

        self.title_bar = build_title_bar(self)
        raiz_v.addWidget(self.title_bar)

        # La barra de navegación vive como fila propia del layout vertical
        # (no como columna del QHBoxLayout de más abajo): en el modelo v8
        # las secciones son pestañas horizontales, no un raíl lateral que
        # comparte fila con el contenido. Ver spec v8 §4.1.
        self.nav_top = build_nav_top(self)
        raiz_v.addWidget(self.nav_top)
        # Colapso a solo-iconos por debajo del ancho real que necesitan las
        # pestañas con texto completo (spec v8 §5.4) -- ver
        # ui.nav_top.update_nav_top_compact, invocado desde eventFilter().
        self.nav_top.installEventFilter(self)

        cuerpo = QWidget()
        root = QHBoxLayout(cuerpo)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Sidebar de biblioteca (Recientes + Playlists = carpetas de
        # favoritos), estilo Spotify: panel aditivo entre la barra de
        # navegación superior y el contenido principal, colapsable con el
        # botón de biblioteca al final de la barra (ui.nav_top). No
        # sustituye a las pestañas de Favoritos/Historial -- es un atajo
        # hacia ellas.
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
        # ui.navigation_controller.NavigationController.on_nav_changed(),
        # no con un botón propio en la barra de navegación.
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

        # setChecked(True) sobre el botón de Inicio (ui.nav_top.build_nav_top)
        # no dispara idClicked por sí solo — solo lo hace
        # un clic real del usuario. Sin esto, la portada se abriría vacía
        # hasta que el usuario cambiara de sección y volviera a Inicio.
        self.navigation.on_nav_changed(NAV_HOME)

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

    def set_live_badge_visible(self, visible: bool) -> None:
        """Sincroniza el indicador visual con la emisión actual."""
        self.live_badge.setVisible(bool(visible))
        if visible:
            self.live_badge.raise_()

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
        if obj is getattr(self, "nav_top", None) and event.type() == QEvent.Resize:
            update_nav_top_compact(self, event.size().width())
        result = self.window_chrome.event_filter(obj, event)
        if result is None:
            return super().eventFilter(obj, event)
        return result

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

        # Búsqueda global (paleta de comandos): antes era el atajo de la
        # QAction "Búsqueda global…" de la barra de menú clásica, retirada
        # en el rediseño v8 (spec §5.2) -- el icono equivalente vive ahora
        # en ui.nav_top (ver ui.more_menu.build_global_search_button), pero
        # el atajo de teclado necesita registrarse aparte, a nivel de
        # ventana, igual que F11/Esc arriba.
        atajo_busqueda = QShortcut(QKeySequence("Ctrl+K"), self)
        atajo_busqueda.setContext(Qt.WindowShortcut)
        atajo_busqueda.activated.connect(self.dialogs.open_command_palette)

        # Controles de reproducción y salto entre secciones. Se guardan en
        # self porque ni el filtro ni los QShortcut mantienen viva su propia
        # referencia: sin esto el recolector se los lleva y los atajos dejan
        # de responder sin ningún error visible. Ver ui/keyboard_shortcuts.py
        # para el porqué de usar un filtro de eventos en las teclas simples
        # (un QShortcut le robaría las flechas a la lista de canales).
        self._filtro_atajos, self._atajos = register_shortcuts(
            self,
            self.playback,
            lambda indice: self.nav_group.button(indice).click(),
            self.window_chrome.toggle_player_fullscreen,
        )


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

    def closeEvent(self, event):
        if self._is_closing:
            event.ignore()
            return
        self.lifecycle.shutdown()
        event.accept()
