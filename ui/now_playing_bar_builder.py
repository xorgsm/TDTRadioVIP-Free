"""Construcción del dock "Ahora suena" (info + controles de reproducción)
de MainWindow. Extraído de ui/main_window.py.

Desde la 10.0 es un dock a todo el ancho bajo el contenido (lo coloca
MainWindow._build_ui), con tres columnas: qué suena | transporte y progreso
del programa | opciones.
"""
from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QFrame, QGridLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton,
    QSizePolicy, QSlider, QVBoxLayout, QWidget,
)

from ui import icons as app_icons
from ui import palette
from ui.player_menus import open_more_controls_menu, open_tracks_menu
from ui.visual import ElidedLabel, make_separator, set_variant, set_visual_state

# Alto del dock (DESIGN.md, Layout). También lo usan PiP y su salida.
DOCK_HEIGHT = 76
# Por debajo de este ancho de ventana el dock oculta calidad, PiP y
# temporizador (DESIGN.md: "Essential Controls Survive").
DOCK_COMPACT_BELOW = 700
# Por debajo de este, además, logo, avance/retroceso y separador (PiP).
DOCK_NARROW_BELOW = 520
DOCK_ROTULO_MIN_WIDTH = 140
_PROGRESS_STEPS = 1000


class DockProgress(QWidget):
    """Fila fina de progreso del programa: "HH:MM ━━━━── HH:MM".

    Oculta mientras no hay programa en curso (radio, canal sin guía).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dockProgress")
        # Subclase de QWidget: sin esto Qt ignora fondo/borde de su QSS.
        self.setAttribute(Qt.WA_StyledBackground, True)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self._start = QLabel()
        self._start.setObjectName("dockProgressTime")
        self._bar = QProgressBar()
        self._bar.setObjectName("dockProgressBar")
        self._bar.setRange(0, _PROGRESS_STEPS)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(4)
        self._end = QLabel()
        self._end.setObjectName("dockProgressTime")
        row.addWidget(self._start)
        row.addWidget(self._bar, stretch=1)
        row.addWidget(self._end)
        self.setMaximumWidth(440)
        self.setVisible(False)

    def set_progress(self, fraction: float, start: str, end: str) -> None:
        """Valores de ui.dock_progress.programme_progress; sin horas se oculta."""
        self._bar.setValue(round(max(0.0, min(1.0, fraction)) * _PROGRESS_STEPS))
        self._start.setText(start)
        self._end.setText(end)
        self.setVisible(bool(start and end))

    def fraction(self) -> float:
        return self._bar.value() / _PROGRESS_STEPS

    def times(self) -> tuple[str, str]:
        return self._start.text(), self._end.text()


class NowRotulo(QFrame):
    """Bloque con el logo y el nombre de lo que suena."""

    def set_state(self, state: str) -> None:
        """Estado "tv", "radio", "error" o "default". Las etiquetas cambian
        de color con un selector del padre: Qt no las recalcula por sí solo."""
        set_visual_state(self, state)
        for label in self.findChildren(QLabel):
            label.style().unpolish(label)
            label.style().polish(label)


def build_now_playing_bar(win) -> QFrame:
    bar = QFrame()
    bar.setObjectName("nowPlayingBar")
    bar.setFixedHeight(DOCK_HEIGHT)
    # Rejilla de tres columnas (DESIGN.md, maqueta): qué suena | transporte
    # y progreso | opciones. Las laterales estiran igual para que el
    # transporte quede centrado en la ventana pase lo que pase a los lados.
    grid = QGridLayout(bar)
    grid.setContentsMargins(16, 6, 16, 6)
    grid.setHorizontalSpacing(16)
    grid.setVerticalSpacing(0)
    win._now_bar_layout = grid

    left_group = QHBoxLayout()
    left_group.setSpacing(8)
    # El rótulo: logo y nombre sobre un bloque del color de lo que suena (ver
    # PlaybackController, que le pone el estado "tv", "radio" o "error").
    win.now_rotulo = NowRotulo()
    win.now_rotulo.setObjectName("nowRotulo")
    rotulo_row = QHBoxLayout(win.now_rotulo)
    rotulo_row.setContentsMargins(4, 4, 12, 4)
    rotulo_row.setSpacing(10)
    win.now_logo = QLabel()
    win.now_logo.setObjectName("nowLogo")
    win.now_logo.setFixedSize(44, 44)
    win.now_logo.setAlignment(Qt.AlignCenter)
    win.now_logo.setPixmap(app_icons.icon_play(palette.TEXT_DIM, 22).pixmap(22, 22))
    rotulo_row.addWidget(win.now_logo)

    text_col = QVBoxLayout()
    text_col.setSpacing(0)
    win.now_title = ElidedLabel("Nada en reproducción")
    win.now_title.setObjectName("nowTitle")
    # Nombre del canal en mayúsculas de rótulo (Barlow Condensed por QSS).
    # La hoja de estilos no fija la capitalización, así que se conserva.
    title_font = win.now_title.font()
    title_font.setCapitalization(QFont.AllUppercase)
    win.now_title.setFont(title_font)
    win.now_subtitle = ElidedLabel("Elige un canal o una emisora")
    win.now_subtitle.setObjectName("nowSubtitle")
    text_col.addWidget(win.now_title)
    text_col.addWidget(win.now_subtitle)
    rotulo_row.addLayout(text_col, stretch=1)
    # Ignored + mínimo: el nombre se recorta (ElidedLabel) antes que empujar
    # al transporte, pero nunca desaparece salvo en el dock estrecho de PiP
    # (ver update_now_playing_bar_compact).
    win.now_rotulo.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
    win.now_rotulo.setMinimumWidth(DOCK_ROTULO_MIN_WIDTH)
    left_group.addWidget(win.now_rotulo, stretch=1)

    win.volume_slider = QSlider(Qt.Horizontal)
    win.volume_slider.setObjectName("volumeSlider")
    win.volume_slider.setRange(0, 100)
    win.volume_slider.setValue(win.settings.get("volume", 80))
    win.volume_slider.setFixedWidth(96)
    win.volume_slider.setAccessibleName("Volumen")
    win.volume_slider.valueChanged.connect(win.playback.on_volume_changed)

    center_group = QHBoxLayout()
    center_group.setSpacing(4)
    right_group = QHBoxLayout()
    right_group.setSpacing(6)

    win.fav_btn = QPushButton()
    win.fav_btn.setObjectName("ctrlButton")
    win.fav_btn.setIconSize(QSize(15, 15))
    win.fav_btn.setIcon(app_icons.icon_favorite(palette.ACCENT_LIST, size=18))
    win.fav_btn.setToolTip("Añadir a favoritos")
    win.fav_btn.setAccessibleName("Añadir a favoritos")
    win.fav_btn.setCheckable(True)
    win.fav_btn.clicked.connect(win.playback.toggle_favorite_current)

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
            # "checked" pinta el icono con palette.INK, igual que
            # #castButton[uiVariant="cast"]:checked en ui/style.py sobre
            # el fondo palette.ACCENT_CAST -- ver comentario equivalente
            # en tv_btn más arriba.
            lambda checked: win.cast_btn.setIcon(app_icons.icon_cast(palette.INK if checked else palette.ACCENT_CAST))
        )
        win.cast_btn.setVisible(win.activated)

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
    win.play_btn.setIcon(app_icons.icon_play(palette.INK, size=22))
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
    # Grabar va con el transporte, como en la maqueta: es un control esencial.
    center_group.addSpacing(4)
    center_group.addWidget(win.record_btn)

    win.mute_btn = QPushButton()
    win.mute_btn.setObjectName("muteButton")
    set_variant(win.mute_btn, "info")
    win.mute_btn.setIconSize(QSize(15, 15))
    win.mute_btn.setIcon(app_icons.icon_speaker(palette.ACCENT_TV, muted=False))
    win.mute_btn.setCheckable(True)
    win.mute_btn.setToolTip("Silenciar")
    win.mute_btn.setAccessibleName("Silenciar")
    win.mute_btn.clicked.connect(win.playback.apply_mute)

    win.now_controls_separator = make_separator()

    # Pistas/pantalla completa/cola no tienen botón visible: viven en "Más
    # opciones" y estos widgets se conservan como "guardianes de estado"
    # (iconos, tooltips, checked) que lee ese menú. PiP y temporizador sí
    # tienen sitio en el dock a todo el ancho (columna de opciones) y se
    # ocultan por debajo de DOCK_COMPACT_BELOW; el menú los sigue ofreciendo.
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
        # Mismo motivo que cast_btn: palette.INK es el "color" que
        # usa #sleepButton[uiVariant="sleep"]:checked en ui/style.py
        # sobre el fondo palette.ACCENT_SLEEP.
        lambda checked: win.sleep_btn.setIcon(app_icons.icon_moon(palette.INK if checked else palette.ACCENT_SLEEP))
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

    win._sleep_timer = QTimer(win)
    win._sleep_timer.setSingleShot(True)
    win._sleep_timer.timeout.connect(win.playback.on_sleep_timeout)
    win._sleep_countdown = QTimer(win)
    win._sleep_countdown.setInterval(60000)   # cada minuto
    win._sleep_countdown.timeout.connect(win.playback.update_sleep_tooltip)
    win._sleep_minutes_left = 0

    # Salud del canal que suena (ver set_quality_badge): oculta sin datos.
    win.dock_quality_badge = QLabel()
    win.dock_quality_badge.setObjectName("dockQualityBadge")
    win.dock_quality_badge.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
    win.dock_quality_badge.setVisible(False)

    # Columna 1: qué suena (+ favorito).
    left_group.addWidget(win.fav_btn)
    left = QWidget()
    left.setObjectName("dockColumn")
    left.setLayout(left_group)
    left_group.setContentsMargins(0, 0, 0, 0)

    # Columna 2: transporte y, debajo, el progreso del programa.
    center = QWidget()
    center.setObjectName("dockColumn")
    center_col = QVBoxLayout(center)
    center_col.setContentsMargins(0, 0, 0, 0)
    center_col.setSpacing(4)
    center_col.addLayout(center_group)
    center_group.setAlignment(Qt.AlignHCenter)
    # Centrada y ocupando el ancho de la columna hasta su máximo (440 px).
    progress_row = QHBoxLayout()
    progress_row.setContentsMargins(0, 0, 0, 0)
    win.dock_progress = DockProgress()
    progress_row.addStretch(1)
    progress_row.addWidget(win.dock_progress, stretch=100)
    progress_row.addStretch(1)
    center_col.addLayout(progress_row)

    # Columna 3: calidad, PiP, Cast, temporizador | silencio, volumen, más.
    right_group.addStretch(1)
    right_group.addWidget(win.dock_quality_badge)
    right_group.addWidget(win.pip_btn)
    if win.cast_btn is not None:
        right_group.addWidget(win.cast_btn)
    right_group.addWidget(win.sleep_btn)
    right_group.addWidget(win.now_controls_separator)
    right_group.addWidget(win.mute_btn)
    right_group.addWidget(win.volume_slider)
    right_group.addWidget(win.more_btn)
    right = QWidget()
    right.setObjectName("dockColumn")
    right.setLayout(right_group)
    right_group.setContentsMargins(0, 0, 0, 0)

    grid.addWidget(left, 0, 0, Qt.AlignVCenter)
    grid.addWidget(center, 0, 1, Qt.AlignVCenter)
    grid.addWidget(right, 0, 2, Qt.AlignVCenter)
    grid.setColumnStretch(0, 1)
    grid.setColumnStretch(1, 1)
    grid.setColumnStretch(2, 1)
    return bar


def update_now_playing_bar_compact(win, width: int) -> None:
    """Adapta el dock al ancho de la ventana sin solapar controles.

    El dock ocupa todo el ancho, así que ``width`` es el de la ventana. Por
    debajo de DOCK_COMPACT_BELOW se ocultan calidad, PiP y temporizador
    (siguen en "Más opciones"); por debajo de DOCK_NARROW_BELOW (PiP),
    también logo, avance/retroceso y separador. Reproducir, detener,
    grabar, volumen y "Más opciones" no se ocultan nunca aquí.
    """
    compact = width < DOCK_COMPACT_BELOW
    narrow = width < DOCK_NARROW_BELOW
    win.now_playing_bar.setProperty("dockCompact", compact)
    margin = 8 if narrow else 16
    win._now_bar_layout.setContentsMargins(margin, 6, margin, 6)
    win._now_bar_layout.setHorizontalSpacing(8 if compact else 16)
    win.now_logo.setVisible(not narrow)
    win.now_rotulo.setMinimumWidth(0 if narrow else DOCK_ROTULO_MIN_WIDTH)
    win.volume_slider.setFixedWidth(56 if narrow else 72 if compact else 96)
    # En directo no aportan nada; en contenido posicionable reaparecen
    # al ensanchar, evitando sacrificar controles esenciales.
    win.seek_back_btn.setVisible(not narrow)
    win.seek_fwd_btn.setVisible(not narrow)
    win.now_controls_separator.setVisible(not narrow)
    # En PiP (460 px) el botón de PiP es la salida visible: no se oculta.
    win.pip_btn.setVisible(not compact or bool(getattr(win, "_pip_mode", False)))
    win.sleep_btn.setVisible(not compact)
    win.dock_quality_badge.setVisible(not compact and bool(win.dock_quality_badge.text()))


def set_quality_badge(win, text: str, state: str) -> None:
    """Pone la etiqueta de calidad (ui.dock_progress.quality_badge).

    Sin texto se oculta; con el dock en modo compacto sigue oculta aunque
    reciba texto (update_now_playing_bar_compact la recupera al ensanchar).
    """
    badge = win.dock_quality_badge
    badge.setText(text)
    # "health" y no uiState: los estados de salud (stable/slow/down) no son
    # estados visuales genéricos de ui.visual. Qt no repinta un selector de
    # propiedad dinámica por sí solo: hace falta el repolish.
    badge.setProperty("health", state or "none")
    badge.style().unpolish(badge)
    badge.style().polish(badge)
    badge.setVisible(bool(text) and not win.now_playing_bar.property("dockCompact"))
