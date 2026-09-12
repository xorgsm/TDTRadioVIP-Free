"""Botón "Más ▾" de la barra de navegación superior y el icono de búsqueda
global que lo acompaña. Sustituye a la barra de menú clásica de Windows
(ui/app_menu.py, retirada) como parte del rediseño v8 -- ver
docs/superpowers/specs/2026-09-09-v8-ui-redesign-design.md §5.1/§5.2. Cada
entrada delega en el mismo controlador/método que ya usaba la barra de
menú clásica; solo cambia dónde vive el punto de entrada.
"""
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QMenu, QToolButton

from ui import icons as app_icons
from ui import palette
from ui.nav_sections import NAV_DOWNLOAD

# Índice de pestaña dentro de ui.download_panel.DownloadPanel.tabs para cada
# herramienta de audio -- ver DownloadPanel._build_ui (0=Vídeo (URL),
# 1=Torrents, 2=Podcasts, 3=Soulseek, 4=Convertir, 5=Editor MP3,
# 6=Editar info). Duplicar estos 3 índices aquí es más simple que exponer
# un mapeo nombre->índice desde download_panel.py para un solo consumidor.
_DOWNLOAD_TOOL_TABS = {
    "Convertir": 4,
    "Editor MP3": 5,
    "Editar info": 6,
}


def build_more_menu_button(win) -> QToolButton:
    """Botón "Más ▾": agrupa gestión de contenido, grabaciones, herramientas
    de audio, guía EPG, ajustes y ayuda -- todo lo que antes vivía en la
    barra de menú clásica (Archivo/Configuración/Ayuda)."""
    btn = QToolButton()
    btn.setObjectName("navButton")
    btn.setToolTip("Más opciones")
    btn.setText("Más ▾")
    btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setIconSize(QSize(20, 20))
    btn.setIcon(app_icons.icon_more(palette.TEXT_MUTED))
    btn.setPopupMode(QToolButton.InstantPopup)

    # Menú anclado al propio botón (no a win): win puede ser un doble de
    # pruebas (SimpleNamespace) en los tests de este módulo/de
    # ui.nav_top, y QMenu exige un QWidget real o ningún padre.
    menu = QMenu(btn)
    win.more_menu = menu
    _build_content_management_menu(win, menu)
    _build_recordings_menu(win, menu)
    if not win.es_version_free:
        _build_audio_tools_menu(win, menu)
    menu.addAction("Guía EPG", win.epg.open_dialog)
    _build_settings_menu(win, menu)
    _build_help_menu(win, menu)
    btn.setMenu(menu)
    return btn


def build_global_search_button(win) -> QToolButton:
    """Icono de búsqueda global (paleta de comandos, Ctrl+K) directo en la
    barra superior -- antes vivía como entrada del menú "Archivo" (ver
    spec v8 §5.1)."""
    btn = QToolButton()
    btn.setObjectName("navButton")
    btn.setToolTip("Búsqueda global (Ctrl+K)")
    btn.setCursor(Qt.PointingHandCursor)
    btn.setIconSize(QSize(20, 20))
    btn.setIcon(app_icons.icon_search(palette.TEXT_MUTED))
    btn.clicked.connect(win.dialogs.open_command_palette)
    return btn


def _build_content_management_menu(win, menu: QMenu) -> None:
    submenu = menu.addMenu("Gestión de contenido")
    submenu.addAction("Añadir canal o emisora…", win.library.open_add_entry_dialog)
    submenu.addAction("Importar lista M3U…", win.library.open_import_playlist_dialog)
    submenu.addAction("Importar lista de TV…", lambda: win.library.open_import_playlist_dialog("tv"))
    submenu.addAction("Importar lista de radio…", lambda: win.library.open_import_playlist_dialog("radio"))
    submenu.addAction("Exportar lista M3U…", win.library.export_current_playlist)
    submenu.addAction("Exportar lista de TV…", lambda: win.library.export_current_playlist("tv"))
    submenu.addAction("Exportar lista de radio…", lambda: win.library.export_current_playlist("radio"))
    submenu.addAction("Editor M3U…", win.library.open_m3u_editor)
    submenu.addAction("Gestionar canales personalizados…", lambda: win.library.open_manage_channels_dialog())
    submenu.addAction("Diagnosticar canales y emisoras…", win.dialogs.open_stream_diagnostics)
    submenu.addAction("Actualizar canales TV", lambda: win.catalog.load_tv_channels(force=True))
    submenu.addAction("Actualizar emisoras de radio", lambda: win.catalog.load_radio_stations(force=True))


def _build_recordings_menu(win, menu: QMenu) -> None:
    submenu = menu.addMenu("Grabaciones")
    submenu.addAction("Biblioteca de grabaciones…", win.library.open_recordings_library)
    submenu.addAction("Grabaciones recurrentes…", win.dialogs.open_recurring_dialog)
    submenu.addAction("Centro de grabaciones programadas…", win.dialogs.open_scheduled_recordings_dialog)
    submenu.addAction("Multivista (mosaico)…", win.dialogs.open_mosaic_view)


def _build_audio_tools_menu(win, menu: QMenu) -> None:
    """Convertir/Editor MP3/Editar info son pestañas de
    ui.download_panel.DownloadPanel, no diálogos propios -- estas entradas
    saltan a Descargas y seleccionan la pestaña pedida. Solo tiene sentido
    en la edición VIP (Descargas no se construye en Free, ver ui.nav_top)."""
    submenu = menu.addMenu("Herramientas de audio")
    for label, tab_index in _DOWNLOAD_TOOL_TABS.items():
        submenu.addAction(label, lambda idx=tab_index: _open_download_tool_tab(win, idx))


def _open_download_tool_tab(win, tab_index: int) -> None:
    win.nav_group.button(NAV_DOWNLOAD).click()
    win.download_panel.tabs.setCurrentIndex(tab_index)


def _build_settings_menu(win, menu: QMenu) -> None:
    submenu = menu.addMenu("Ajustes")
    submenu.addAction("Preferencias…", win.dialogs.open_settings)
    submenu.addAction("Ecualizador…", win.dialogs.open_equalizer_dialog)
    # Solo en la edición VIP sin activar: como el splash ya no aparece en
    # cada arranque tras elegir modo gratuito (ver ui.application.run_vip),
    # esta entrada es el camino de vuelta al diálogo de activación.
    if not win.activated and not win.es_version_free:
        win.activate_vip_action = submenu.addAction("Activar VIP…", win.dialogs.open_activation_dialog)


def _build_help_menu(win, menu: QMenu) -> None:
    submenu = menu.addMenu("Ayuda y sistema")
    submenu.addAction("Acerca de", win.dialogs.show_about)
    # Los atajos no se descubren solos: sin esta entrada, el usuario tendría
    # que dar con ellos por casualidad.
    submenu.addAction("Atajos de teclado…", win.dialogs.show_keyboard_shortcuts)
    submenu.addAction("Estadísticas de uso…", win.dialogs.open_stats_dialog)
    submenu.addAction("Buscar actualizaciones", win.updates.check_for_update)
    submenu.addAction("Abrir carpeta de logs", win.dialogs.open_logs_folder)
    submenu.addAction("Exportar copia de seguridad…", win.library.export_backup)
    submenu.addAction("Importar copia de seguridad…", win.library.import_backup)
