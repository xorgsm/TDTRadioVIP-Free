"""Menús contextuales del reproductor ("Más opciones", pistas de audio/
subtítulos) e información técnica del stream. Extraído de
ui/main_window.py.
"""
from PySide6.QtWidgets import QMenu, QMessageBox

from ui import palette


def _apply_menu_style(win, menu: QMenu) -> None:
    acento = win.settings.get("accent_color", palette.ACCENT)
    menu.setStyleSheet(
        f"QMenu {{ background-color: {palette.BG_PANEL}; color: {palette.TEXT_PRIMARY}; "
        f"border: 1px solid {palette.BORDER}; }}"
        f"QMenu::item:selected {{ background-color: {acento}; color: {palette.BG_ROOT}; }}"
    )


def open_more_controls_menu(win) -> None:
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
    menu = QMenu(win)
    _apply_menu_style(win, menu)

    menu.addAction("Pistas de audio y subtítulos…", lambda: open_tracks_menu(win))

    texto_fullscreen = (
        "Salir de pantalla completa" if win._player_fullscreen
        else "Pantalla completa (F11)"
    )
    menu.addAction(texto_fullscreen, win.window_chrome.toggle_player_fullscreen)

    texto_pip = "Salir de ventana flotante" if win._pip_mode else "Ventana flotante"
    menu.addAction(texto_pip, win.window_chrome.toggle_pip_mode)

    menu.addSeparator()

    if win._sleep_timer.isActive():
        texto_sleep = f"Cancelar temporizador ({win._sleep_minutes_left} min restantes)"
    else:
        texto_sleep = "Temporizador de apagado…"
    # on_sleep_btn_clicked ya decide internamente si abre el selector
    # de minutos o cancela el temporizador activo -- no hace falta
    # duplicar esa rama aquí, solo el texto que se muestra.
    menu.addAction(texto_sleep, win.playback.on_sleep_btn_clicked)

    menu.addAction(win.queue_btn.toolTip(), win.queue.toggle_panel)

    menu.addSeparator()
    texto_audio_only = (
        "Desactivar modo solo audio (TV)" if win._audio_only_tv
        else "Modo solo audio (TV)…"
    )
    menu.addAction(texto_audio_only, win.playback.toggle_audio_only_tv)
    menu.addAction("Ecualizador…", win._open_equalizer_dialog)

    menu.addAction("Información técnica…", lambda: show_stream_technical_info(win))
    menu.exec(win.more_btn.mapToGlobal(win.more_btn.rect().bottomLeft()))


def show_stream_technical_info(win) -> None:
    if not win.current_url:
        QMessageBox.information(win, "Información técnica", "No hay ninguna emisión activa.")
        return
    info = win.player.technical_info()
    labels = {
        "resolution": "Resolución", "volume": "Volumen",
        "audio_tracks": "Pistas de audio", "subtitle_tracks": "Pistas de subtítulos",
        "state": "Estado VLC", "input_bitrate": "Bitrate de entrada",
        "demux_bitrate": "Bitrate demux",
    }
    lines = [f"Canal: {win.current_name}", f"URL: {win.current_url}"]
    for key, label in labels.items():
        if key in info:
            value = info[key]
            if key.endswith("bitrate"):
                value = f"{value:.2f} Mb/s"
            lines.append(f"{label}: {value}")
    QMessageBox.information(win, "Información técnica del stream", "\n".join(lines))


def open_tracks_menu(win) -> None:
    """
    Menú de pistas de audio y subtítulos del stream actual (solo TV:
    las emisoras de radio no traen subtítulos y casi nunca más de una
    pista de audio). Se construye cada vez que se abre, no una vez al
    arrancar, porque las pistas disponibles dependen del canal que
    esté sonando en ese momento.
    """
    if win.current_type != "tv" or not win.player.disponible:
        QMessageBox.information(
            win, "Sin pistas disponibles",
            "Las pistas de audio y subtítulos solo están disponibles "
            "mientras se reproduce un canal de TV."
        )
        return

    menu = QMenu(win)
    _apply_menu_style(win, menu)

    audio_menu = menu.addMenu("Pista de audio")
    pistas_audio = win.player.audio_tracks()
    if not pistas_audio:
        audio_menu.addAction("(Solo una pista disponible)").setEnabled(False)
    else:
        actual = win.player.current_audio_track()
        for track_id, nombre in pistas_audio:
            accion = audio_menu.addAction(nombre)
            accion.setCheckable(True)
            accion.setChecked(track_id == actual)
            accion.triggered.connect(lambda _c=False, tid=track_id: win.player.set_audio_track(tid))

    subs_menu = menu.addMenu("Subtítulos")
    pistas_subs = win.player.subtitle_tracks()
    if not pistas_subs:
        subs_menu.addAction("(Este stream no trae subtítulos)").setEnabled(False)
    else:
        actual_sub = win.player.current_subtitle_track()
        for track_id, nombre in pistas_subs:
            accion = subs_menu.addAction(nombre)
            accion.setCheckable(True)
            accion.setChecked(track_id == actual_sub)
            accion.triggered.connect(lambda _c=False, tid=track_id: win.player.set_subtitle_track(tid))

    # Se ancla a more_btn (no a tracks_btn): tracks_btn ya no vive en
    # ningún layout visible -- ver el comentario en _build_now_playing_bar
    # -- así que su propia posición en pantalla no sería fiable.
    menu.exec(win.more_btn.mapToGlobal(win.more_btn.rect().bottomLeft()))
