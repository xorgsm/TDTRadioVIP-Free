"""
Vista "Ahora Suena" para radio: sustituye al QStackedWidget de vídeo (que
para radio no tiene nada que mostrar) por una portada grande con el logo de
la emisora, más el nombre/género y, cuando el stream lo manda (ICY/
Shoutcast, ver player.vlc_player.VLCPlayer.meta_changed), la canción o
programa que suena ahora mismo.

Es la vista que dibuja resources/design/panel-principal-mockup.png (mockup
original del rediseño 7.5.8, ver ui/palette.py) y que nunca se llegó a
construir -- antes, escuchar radio solo mostraba el ecualizador animado
(ui.widgets.EqualizerWidget) solo, sin identidad de la emisora en pantalla.

Coder By X@R
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ui import icons as app_icons
from ui import palette
from ui.widgets import EqualizerWidget

COVER_SIZE = 220
LOGO_SIZE = 150


class RadioHeroWidget(QWidget):
    """
    Sustituye al ecualizador "a pelo" en player_stack cuando suena radio.
    Contiene el propio EqualizerWidget (más pequeño, como tira animada bajo
    la portada) en vez de duplicar la lógica de animación.
    """

    def __init__(self, logo_loader, parent=None):
        super().__init__(parent)
        self.setObjectName("radioHero")
        self._logo_loader = logo_loader
        self._logo_token = 0  # descarta respuestas de logo que ya no tocan

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 12)
        layout.setSpacing(18)
        layout.addStretch(1)

        self.cover = QLabel()
        self.cover.setObjectName("radioHeroCover")
        self.cover.setFixedSize(COVER_SIZE, COVER_SIZE)
        self.cover.setAlignment(Qt.AlignCenter)
        self.cover.setStyleSheet(
            f"QLabel#radioHeroCover {{"
            f"  background: qlineargradient(x1:0, y1:0, x2:1, y2:1,"
            f"    stop:0 {palette.BG_CARD}, stop:1 {palette.BG_ROOT});"
            f"  border: 1px solid {palette.BORDER};"
            f"  border-radius: 24px;"
            f"}}"
        )
        layout.addWidget(self.cover, alignment=Qt.AlignHCenter)

        self.equalizer = EqualizerWidget(bars=11)
        self.equalizer.setFixedHeight(56)
        self.equalizer.setFixedWidth(COVER_SIZE)
        layout.addWidget(self.equalizer, alignment=Qt.AlignHCenter)

        self.station_label = QLabel()
        self.station_label.setAlignment(Qt.AlignCenter)
        self.station_label.setStyleSheet(
            f"color: {palette.ACCENT}; font-weight: 800; font-size: 12pt; "
            f"letter-spacing: 1.5px;"
        )
        layout.addWidget(self.station_label)

        self.song_label = QLabel()
        self.song_label.setAlignment(Qt.AlignCenter)
        self.song_label.setWordWrap(True)
        self.song_label.setStyleSheet(
            f"color: {palette.TEXT_PRIMARY}; font-weight: 750; font-size: 20pt;"
        )
        self.song_label.hide()
        layout.addWidget(self.song_label)

        self.meta_label = QLabel()
        self.meta_label.setAlignment(Qt.AlignCenter)
        self.meta_label.setWordWrap(True)
        self.meta_label.setStyleSheet(
            f"color: {palette.TEXT_MUTED}; font-size: 11pt;"
        )
        layout.addWidget(self.meta_label)

        layout.addStretch(1)

        self._show_fallback_cover()

    # ---------- estado ----------

    def start(self):
        self.equalizer.start()

    def stop(self):
        self.equalizer.stop()

    def set_intensity(self, level: float):
        self.equalizer.set_intensity(level)

    def set_station(self, name: str, favicon: str, tags: str):
        """Llamado desde PlaybackController.play() al arrancar una emisora."""
        self.station_label.setText(name.upper())
        self.meta_label.setText(tags.strip() if tags and tags.strip() else "Radio en directo")
        self.song_label.hide()
        self.song_label.clear()
        self._show_fallback_cover()

        self._logo_token += 1
        token = self._logo_token
        if favicon:
            self._logo_loader.load(favicon, lambda pix, t=token: self._on_logo_ready(pix, t), size=LOGO_SIZE)

    def set_now_playing(self, text: str):
        """Llamado desde VLCPlayer.meta_changed -- '' significa 'sin dato'."""
        text = (text or "").strip()
        if text:
            self.song_label.setText(text)
            self.song_label.show()
        else:
            self.song_label.hide()
            self.song_label.clear()

    # ---------- portada ----------

    def _show_fallback_cover(self):
        """Nota musical dorada -- mismo lenguaje visual que el resto de la
        app cuando no hay logo real que mostrar (ver widgets.rounded_pixmap
        / los placeholders de carousel.py)."""
        self.cover.setPixmap(app_icons.icon_music_note(palette.ACCENT, size=52).pixmap(52, 52))

    def _on_logo_ready(self, pixmap, token: int):
        if token != self._logo_token:
            return  # la emisora ya cambió otra vez; este logo llegó tarde
        self.cover.setPixmap(pixmap)
