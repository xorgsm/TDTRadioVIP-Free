"""Construcción de la barra de menú (Archivo/Configuración/Ayuda) de
MainWindow. Extraído de ui/main_window.py: solo ensambla QAction que
delegan en los controladores/métodos ya existentes de la ventana.
"""
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QMenuBar


def build_menu_bar(win) -> QMenuBar:
    menu = QMenuBar()
    menu.setObjectName("appMenuBar")
    menu.setNativeMenuBar(False)
    win.menu_bar = menu

    file_menu = menu.addMenu("Archivo")
    global_search_action = QAction("Búsqueda global…", win)
    global_search_action.setShortcut(QKeySequence("Ctrl+K"))
    global_search_action.triggered.connect(win.dialogs.open_command_palette)
    file_menu.addAction(global_search_action)
    file_menu.addSeparator()

    refresh_tv_action = QAction("Actualizar canales TV", win)
    refresh_tv_action.triggered.connect(lambda: win.catalog.load_tv_channels(force=True))
    file_menu.addAction(refresh_tv_action)

    refresh_radio_action = QAction("Actualizar emisoras de radio", win)
    refresh_radio_action.triggered.connect(lambda: win.catalog.load_radio_stations(force=True))
    file_menu.addAction(refresh_radio_action)

    diagnostics_action = QAction("Diagnosticar canales y emisoras…", win)
    diagnostics_action.triggered.connect(win.dialogs.open_stream_diagnostics)
    file_menu.addAction(diagnostics_action)

    file_menu.addSeparator()
    add_entry_action = QAction("Añadir canal o emisora…", win)
    add_entry_action.triggered.connect(win.library.open_add_entry_dialog)
    file_menu.addAction(add_entry_action)

    import_action = QAction("Importar lista M3U…", win)
    import_action.triggered.connect(win.library.open_import_playlist_dialog)
    file_menu.addAction(import_action)

    editor_m3u_action = QAction("Editor M3U…", win)
    editor_m3u_action.triggered.connect(win.library.open_m3u_editor)
    file_menu.addAction(editor_m3u_action)

    import_tv_action = QAction("Importar lista de TV...", win)
    import_tv_action.triggered.connect(lambda: win.library.open_import_playlist_dialog("tv"))
    file_menu.addAction(import_tv_action)

    import_radio_action = QAction("Importar lista de radio...", win)
    import_radio_action.triggered.connect(lambda: win.library.open_import_playlist_dialog("radio"))
    file_menu.addAction(import_radio_action)

    export_playlist_action = QAction("Exportar lista M3U…", win)
    export_playlist_action.triggered.connect(win.library.export_current_playlist)
    file_menu.addAction(export_playlist_action)

    export_tv_action = QAction("Exportar lista de TV...", win)
    export_tv_action.triggered.connect(lambda: win.library.export_current_playlist("tv"))
    file_menu.addAction(export_tv_action)

    export_radio_action = QAction("Exportar lista de radio...", win)
    export_radio_action.triggered.connect(lambda: win.library.export_current_playlist("radio"))
    file_menu.addAction(export_radio_action)

    manage_action = QAction("Gestionar canales personalizados…", win)
    manage_action.triggered.connect(lambda: win.library.open_manage_channels_dialog())
    file_menu.addAction(manage_action)

    file_menu.addSeparator()
    recordings_action = QAction("Biblioteca de grabaciones…", win)
    recordings_action.triggered.connect(win.library.open_recordings_library)
    file_menu.addAction(recordings_action)

    recurring_action = QAction("Grabaciones recurrentes…", win)
    recurring_action.triggered.connect(win.dialogs.open_recurring_dialog)
    file_menu.addAction(recurring_action)

    scheduled_action = QAction("Centro de grabaciones programadas…", win)
    scheduled_action.triggered.connect(win.dialogs.open_scheduled_recordings_dialog)
    file_menu.addAction(scheduled_action)

    mosaic_action = QAction("Multivista (mosaico)…", win)
    mosaic_action.triggered.connect(win.dialogs.open_mosaic_view)
    file_menu.addAction(mosaic_action)

    file_menu.addSeparator()
    export_backup_action = QAction("Exportar copia de seguridad…", win)
    export_backup_action.triggered.connect(win.library.export_backup)
    file_menu.addAction(export_backup_action)

    import_backup_action = QAction("Importar copia de seguridad…", win)
    import_backup_action.triggered.connect(win.library.import_backup)
    file_menu.addAction(import_backup_action)

    file_menu.addSeparator()
    exit_action = QAction("Salir", win)
    exit_action.triggered.connect(win.close)
    file_menu.addAction(exit_action)

    settings_menu = menu.addMenu("Configuración")
    settings_action = QAction("Preferencias…", win)
    settings_action.triggered.connect(win.dialogs.open_settings)
    settings_menu.addAction(settings_action)

    # Solo en la edición VIP sin activar: como el splash ya no aparece en
    # cada arranque tras elegir modo gratuito (ver ui/application.run_vip),
    # esta entrada es el camino de vuelta al diálogo de activación.
    if not win.activated and not win.es_version_free:
        win.activate_vip_action = QAction("Activar VIP…", win)
        win.activate_vip_action.triggered.connect(win.dialogs.open_activation_dialog)
        settings_menu.addAction(win.activate_vip_action)

    help_menu = menu.addMenu("Ayuda")
    about_action = QAction("Acerca de", win)
    about_action.triggered.connect(win.dialogs.show_about)
    help_menu.addAction(about_action)

    stats_action = QAction("Estadísticas de uso…", win)
    stats_action.triggered.connect(win.dialogs.open_stats_dialog)
    help_menu.addAction(stats_action)

    update_action = QAction("Buscar actualizaciones", win)
    update_action.triggered.connect(win.updates.check_for_update)
    help_menu.addAction(update_action)

    logs_action = QAction("Abrir carpeta de logs", win)
    logs_action.triggered.connect(win.dialogs.open_logs_folder)
    help_menu.addAction(logs_action)

    return menu
