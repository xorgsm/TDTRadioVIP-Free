"""Construcción del panel del reproductor (cabecera, frame de vídeo/radio
y barra "Ahora suena"). Extraído de ui/main_window.py.
"""
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QSizePolicy, QStackedWidget, QVBoxLayout,
    QWidget,
)

from player.vlc_player import VLCPlayer
from ui.now_playing_bar_builder import build_now_playing_bar
from ui.radio_hero import RadioHeroWidget
from ui.visual import set_variant


def build_player_panel(win) -> QWidget:
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
    win.player_header_bar = QWidget()
    player_header = QHBoxLayout(win.player_header_bar)
    player_header.setContentsMargins(8, 2, 8, 4)
    win.player_context_label = QLabel("AHORA SUENA")
    win.player_context_label.setObjectName("playerContextLabel")
    player_header.addWidget(win.player_context_label)
    player_header.addStretch(1)

    # El punto rojo se mantiene separado del dorado de marca: comunica
    # que el contenido es una emisión viva, no una alerta de error.
    win.live_badge = QLabel(
        '<span style="color:#ef5350;">●</span>&nbsp;&nbsp;EN DIRECTO'
    )
    win.live_badge.setObjectName("liveBadge")
    set_variant(win.live_badge, "danger")
    win.live_badge.hide()
    player_header.addWidget(win.live_badge)
    layout.addWidget(win.player_header_bar)

    win.player_frame = QFrame()
    win.player_frame.setObjectName("playerFrame")
    win.player_frame.installEventFilter(win)
    frame_layout = QVBoxLayout(win.player_frame)
    frame_layout.setContentsMargins(0, 0, 0, 0)

    win.player_stack = QStackedWidget()
    # QStackedWidget siempre ajusta a su widget hijo actual al tamaño
    # completo DEL PROPIO STACK — pero eso no significa que el stack en
    # sí crezca dentro de frame_layout. Sin esta línea, player_stack se
    # quedaba con la política Preferred por defecto de Qt y su sizeHint
    # (dominado por EqualizerWidget.setMinimumHeight(200)); el vídeo
    # salía correctamente escalado... al tamaño pequeño que Qt le daba
    # al stack, con el fondo de playerFrame visible alrededor.
    win.player_stack.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    win.player = VLCPlayer()
    win.player.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    win.player.error_occurred.connect(win.playback.on_player_error)
    win.player.end_reached.connect(win.playback.on_player_end_reached)
    win._apply_saved_equalizer()
    # "equalizer" es el nombre histórico de este atributo (antes un
    # EqualizerWidget a pelo); ahora es la vista "Ahora Suena" completa
    # -- logo de emisora + título en directo cuando el stream lo manda
    # (ICY) -- que sigue llevando su propio EqualizerWidget dentro como
    # tira animada. start()/stop()/set_intensity() tienen la misma firma
    # que antes a propósito, así que playback_controller.py no cambia.
    win.equalizer = RadioHeroWidget(win.logo_loader)
    win.player.meta_changed.connect(win.equalizer.set_now_playing)
    win.player_stack.addWidget(win.player)
    win.player_stack.addWidget(win.equalizer)
    frame_layout.addWidget(win.player_stack, stretch=1)

    layout.addWidget(win.player_frame, stretch=1)
    win.now_playing_bar = build_now_playing_bar(win)
    layout.addWidget(win.now_playing_bar)

    # Auto-ocultar cabecera/controles en pantalla completa (ajuste
    # "fullscreen_autohide_ui") -- ver WindowChrome.enter_player_fullscreen
    # / show_fullscreen_overlay / check_fullscreen_mouse_activity. El
    # vídeo se pinta en una ventana nativa de libVLC embebida, así que
    # sus eventos de ratón no llegan a Qt: en vez de un eventFilter se
    # sondea la posición global del cursor con un QTimer periódico.
    win._fs_last_cursor_pos = None
    win._fs_mouse_poll_timer = QTimer(win)
    win._fs_mouse_poll_timer.setInterval(180)
    win._fs_mouse_poll_timer.timeout.connect(
        win.window_chrome.check_fullscreen_mouse_activity
    )
    win._fs_overlay_hide_timer = QTimer(win)
    win._fs_overlay_hide_timer.setSingleShot(True)
    win._fs_overlay_hide_timer.setInterval(2500)
    win._fs_overlay_hide_timer.timeout.connect(
        win.window_chrome.hide_fullscreen_overlay
    )

    return panel
