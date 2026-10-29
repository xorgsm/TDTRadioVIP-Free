"""Construcción de la barra "Ahora suena" (info + controles de
reproducción) de MainWindow. Extraído de ui/main_window.py.
"""
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy, QSlider,
    QVBoxLayout,
)

from ui import icons as app_icons
from ui import palette
from ui.player_menus import open_more_controls_menu, open_tracks_menu
from ui.visual import make_separator, set_variant


def build_now_playing_bar(win) -> QFrame:
    bar = QFrame()
    bar.setObjectName("nowPlayingBar")
    bar.setFixedHeight(142)
    outer = QVBoxLayout(bar)
    outer.setContentsMargins(16, 16, 16, 16)
    outer.setSpacing(12)
    win._now_bar_layout = outer

    info_row = QHBoxLayout()
    win.now_logo = QLabel()
    win.now_logo.setFixedSize(50, 50)
    win.now_logo.setStyleSheet(f"background-color: {palette.BG_PANEL_ALT}; border-radius: 12px;")
    win.now_logo.setAlignment(Qt.AlignCenter)
    info_row.addWidget(win.now_logo)

    text_col = QVBoxLayout()
    text_col.setSpacing(2)
    win.now_title = QLabel("Nada en reproducción")
    win.now_title.setObjectName("nowTitle")
    win.now_title.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
    win.now_subtitle = QLabel("Elige un canal o una emisora")
    win.now_subtitle.setObjectName("nowSubtitle")
    win.now_subtitle.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
    text_col.addWidget(win.now_title)
    text_col.addWidget(win.now_subtitle)
    info_row.addLayout(text_col, stretch=1)

    # El volumen vivía en la fila de botones de abajo, donde con muchos
    # botones + separadores no queda sitio de sobra: con ventana
    # estrecha el slider (que necesita un ancho mínimo para no
    # convertirse en un punto suelto irreconocible) se comía a sus
    # vecinos. Aquí arriba, junto al nombre del canal, sí hay margen.
    win.volume_slider = QSlider(Qt.Horizontal)
    win.volume_slider.setObjectName("volumeSlider")
    win.volume_slider.setRange(0, 100)
    win.volume_slider.setValue(win.settings.get("volume", 80))
    win.volume_slider.setFixedWidth(108)
    win.volume_slider.valueChanged.connect(win.playback.on_volume_changed)
    info_row.addWidget(win.volume_slider)

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

    win.fav_btn = QPushButton()
    win.fav_btn.setObjectName("ctrlButton")
    win.fav_btn.setIconSize(QSize(15, 15))
    win.fav_btn.setIcon(app_icons.icon_favorite(palette.ACCENT, size=18))
    win.fav_btn.setToolTip("Añadir a favoritos")
    win.fav_btn.setAccessibleName("Añadir a favoritos")
    win.fav_btn.setCheckable(True)
    win.fav_btn.clicked.connect(win.playback.toggle_favorite_current)
    left_group.addWidget(win.fav_btn)

    # Igual que NAV_DOWNLOAD/download_panel: en la versión free ni
    # siquiera se construye (self.casting es None ahí, ver __init__).
    if win.es_version_free:
        win.cast_btn = None
    else:
        win.cast_btn = QPushButton()
        win.cast_btn.setObjectName("castButton")
        set_variant(win.cast_btn, "cast")
        win.cast_btn.setIconSize(QSize(15, 15))
        win.cast_btn.setIcon(app_icons.icon_cast(palette.ACCENT_CAST))
        win.cast_btn.setCheckable(True)
        win.cast_btn.setToolTip("Enviar a Chromecast / TV")
        win.cast_btn.setAccessibleName("Enviar a Chromecast o TV")
        win.cast_btn.clicked.connect(win.casting.on_cast_live_clicked)
        win.cast_btn.toggled.connect(
            # "checked" pinta el icono con palette.BG_ROOT, igual que
            # #castButton[uiVariant="cast"]:checked en ui/style.py sobre
            # el fondo palette.ACCENT_CAST -- ver comentario equivalente
            # en tv_btn más arriba.
            lambda checked: win.cast_btn.setIcon(app_icons.icon_cast(palette.BG_ROOT if checked else palette.ACCENT_CAST))
        )
        win.cast_btn.setVisible(win.activated)
        left_group.addWidget(win.cast_btn)

    win.stop_btn = QPushButton()
    win.stop_btn.setObjectName("ctrlButton")
    win.stop_btn.setIcon(app_icons.icon_stop(palette.TEXT_PRIMARY, size=18))
    win.stop_btn.setIconSize(QSize(15, 15))
    win.stop_btn.setToolTip("Detener")
    win.stop_btn.setAccessibleName("Detener reproducción")
    win.stop_btn.clicked.connect(win.playback.stop_playback)
    center_group.addWidget(win.stop_btn)

    # Avance rápido / retroceso de 30 s. Solo tienen efecto real en
    # contenido posicionable (VOD, series, ficheros locales) -- un
    # canal de TV o emisora de radio en directo puro no admite
    # set_time(), así que empiezan desactivados y PlaybackController
    # los activa/desactiva según VLCPlayer.is_seekable() confirme lo
    # que se está reproduciendo (ver _confirm_playback_ok).
    win.seek_back_btn = QPushButton()
    win.seek_back_btn.setObjectName("ctrlButton")
    win.seek_back_btn.setIcon(app_icons.icon_seek(palette.TEXT_PRIMARY, size=18, forward=False))
    win.seek_back_btn.setIconSize(QSize(15, 15))
    win.seek_back_btn.setToolTip("Retroceder 30 s")
    win.seek_back_btn.setAccessibleName("Retroceder 30 segundos")
    win.seek_back_btn.setEnabled(False)
    win.seek_back_btn.clicked.connect(lambda: win.playback.seek(-30_000))
    center_group.addWidget(win.seek_back_btn)

    center_group.addSpacing(4)
    win.play_btn = QPushButton()
    win.play_btn.setObjectName("playCircle")
    win.play_btn.setIcon(app_icons.icon_play(palette.BG_ROOT, size=22))
    win.play_btn.setIconSize(QSize(19, 19))
    win.play_btn.setToolTip("Reproducir")
    win.play_btn.setAccessibleName("Reproducir")
    set_variant(win.play_btn, "primary")
    win.play_btn.clicked.connect(win.playback.toggle_play)
    center_group.addWidget(win.play_btn)
    center_group.addSpacing(4)

    win.seek_fwd_btn = QPushButton()
    win.seek_fwd_btn.setObjectName("ctrlButton")
    win.seek_fwd_btn.setIcon(app_icons.icon_seek(palette.TEXT_PRIMARY, size=18))
    win.seek_fwd_btn.setIconSize(QSize(15, 15))
    win.seek_fwd_btn.setToolTip("Avanzar 30 s")
    win.seek_fwd_btn.setAccessibleName("Avanzar 30 segundos")
    win.seek_fwd_btn.setEnabled(False)
    win.seek_fwd_btn.clicked.connect(lambda: win.playback.seek(30_000))
    center_group.addWidget(win.seek_fwd_btn)

    win.retry_btn = QPushButton()
    win.retry_btn.setObjectName("ctrlButton")
    win.retry_btn.setIcon(app_icons.icon_retry(palette.TEXT_PRIMARY, size=18))
    win.retry_btn.setIconSize(QSize(15, 15))
    win.retry_btn.setToolTip("Reintentar conexión")
    win.retry_btn.setAccessibleName("Reintentar conexión")
    win.retry_btn.clicked.connect(win.playback.retry_playback)
    win.retry_btn.setVisible(False)
    center_group.addWidget(win.retry_btn)

    win.record_btn = QPushButton()
    win.record_btn.setObjectName("recordButton")
    win.record_btn.setIcon(app_icons.icon_record(palette.DANGER, size=18))
    win.record_btn.setIconSize(QSize(15, 15))
    win.record_btn.setToolTip("Iniciar grabación")
    win.record_btn.setAccessibleName("Iniciar grabación")
    set_variant(win.record_btn, "danger")
    win.record_btn.setCheckable(True)
    win.record_btn.clicked.connect(win.playback.toggle_recording)
    right_group.addWidget(win.record_btn)

    win.mute_btn = QPushButton()
    win.mute_btn.setObjectName("muteButton")
    set_variant(win.mute_btn, "info")
    win.mute_btn.setIconSize(QSize(15, 15))
    win.mute_btn.setIcon(app_icons.icon_speaker(palette.ACCENT_INFO, muted=False))
    win.mute_btn.setCheckable(True)
    win.mute_btn.setToolTip("Silenciar")
    win.mute_btn.setAccessibleName("Silenciar")
    win.mute_btn.clicked.connect(win.playback.apply_mute)
    right_group.addWidget(win.mute_btn)

    win.now_controls_separator = make_separator()
    right_group.addWidget(win.now_controls_separator)

    # Pistas/pantalla completa/PiP/temporizador/cola: antes cada uno
    # tenia su propio boton circular en esta fila. Con 8 botones +
    # separador no cabian en ventanas estrechas y quedaban solapados o
    # cortados (reportado con captura). Se siguen creando igual -- el
    # resto del codigo (iconos, tooltips, estado checked/toggled) sigue
    # dependiendo de estos widgets como "guardianes de estado" -- pero
    # ya NO se anaden a right_group: se agrupan bajo un unico boton
    # "Mas opciones" siempre visible, asi la fila no crece con el
    # numero de funciones, solo con las acciones realmente frecuentes.
    win.tracks_btn = QPushButton("CC")
    win.tracks_btn.setObjectName("ctrlButton")
    win.tracks_btn.setToolTip("Pistas de audio y subtítulos")
    win.tracks_btn.clicked.connect(lambda: open_tracks_menu(win))

    win.fullscreen_btn = QPushButton()
    win.fullscreen_btn.setObjectName("ctrlButton")
    win.fullscreen_btn.setIcon(app_icons.icon_fullscreen(palette.TEXT_PRIMARY, size=18))
    win.fullscreen_btn.setIconSize(QSize(15, 15))
    win.fullscreen_btn.setToolTip("Pantalla completa (F11)")
    win.fullscreen_btn.setAccessibleName("Pantalla completa")
    win.fullscreen_btn.clicked.connect(win.window_chrome.toggle_player_fullscreen)

    win.pip_btn = QPushButton()
    win.pip_btn.setObjectName("ctrlButton")
    win.pip_btn.setIconSize(QSize(15, 15))
    win.pip_btn.setIcon(app_icons.icon_pip(palette.TEXT_PRIMARY))
    win.pip_btn.setToolTip("Ventana flotante")
    win.pip_btn.setAccessibleName("Abrir ventana flotante")
    win.pip_btn.clicked.connect(win.window_chrome.toggle_pip_mode)

    win.sleep_btn = QPushButton()
    win.sleep_btn.setObjectName("sleepButton")
    set_variant(win.sleep_btn, "sleep")
    win.sleep_btn.setIconSize(QSize(15, 15))
    win.sleep_btn.setIcon(app_icons.icon_moon(palette.ACCENT_SLEEP))
    win.sleep_btn.setCheckable(True)
    win.sleep_btn.setToolTip("Temporizador de apagado")
    win.sleep_btn.setAccessibleName("Temporizador de apagado")
    win.sleep_btn.clicked.connect(win.playback.on_sleep_btn_clicked)
    win.sleep_btn.toggled.connect(
        # Mismo motivo que cast_btn: palette.BG_ROOT es el "color" que
        # usa #sleepButton[uiVariant="sleep"]:checked en ui/style.py
        # sobre el fondo palette.ACCENT_SLEEP.
        lambda checked: win.sleep_btn.setIcon(app_icons.icon_moon(palette.BG_ROOT if checked else palette.ACCENT_SLEEP))
    )

    win.queue_btn = QPushButton()
    win.queue_btn.setObjectName("ctrlButton")
    win.queue_btn.setIconSize(QSize(15, 15))
    win.queue_btn.setIcon(app_icons.icon_queue(palette.TEXT_PRIMARY))
    win.queue_btn.setToolTip("Cola de reproducción (vacía)")
    win.queue_btn.setAccessibleName("Cola de reproducción")
    win.queue_btn.clicked.connect(win.queue.toggle_panel)

    win.more_btn = QPushButton()
    win.more_btn.setObjectName("ctrlButton")
    win.more_btn.setIconSize(QSize(15, 15))
    win.more_btn.setIcon(app_icons.icon_more(palette.TEXT_PRIMARY))
    win.more_btn.setToolTip("Más opciones (pistas, pantalla completa, PiP, temporizador, cola)")
    win.more_btn.setAccessibleName("Más opciones de reproducción")
    win.more_btn.clicked.connect(lambda: open_more_controls_menu(win))
    right_group.addWidget(win.more_btn)

    win._sleep_timer = QTimer(win)
    win._sleep_timer.setSingleShot(True)
    win._sleep_timer.timeout.connect(win.playback.on_sleep_timeout)
    win._sleep_countdown = QTimer(win)
    win._sleep_countdown.setInterval(60000)   # cada minuto
    win._sleep_countdown.timeout.connect(win.playback.update_sleep_tooltip)
    win._sleep_minutes_left = 0

    controls.addLayout(left_group)
    controls.addStretch(1)
    controls.addLayout(center_group)
    controls.addStretch(1)
    controls.addLayout(right_group)

    outer.addLayout(controls)
    return bar


def update_now_playing_bar_compact(win, width: int) -> None:
    """Adapta la barra de reproducción sin solapar controles."""
    compact = width < 390
    margin = 14 if compact else 16
    win._now_bar_layout.setContentsMargins(margin, 16, margin, 16)
    win.now_logo.setVisible(not compact)
    win.volume_slider.setFixedWidth(56 if compact else 108)
    # En directo no aportan nada; en contenido posicionable reaparecen
    # al ensanchar el panel, evitando sacrificar controles esenciales.
    win.seek_back_btn.setVisible(not compact)
    win.seek_fwd_btn.setVisible(not compact)
    win.now_controls_separator.setVisible(not compact)
