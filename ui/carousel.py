"""
Carrusel horizontal de tarjetas de canal/emisora, estilo "Recientes" /
"Recomendado para ti" de Spotify: fila de tarjetas compactas (logo arriba,
nombre debajo) con scroll horizontal propio.

ChannelDelegate (ui/widgets.py) no sirve para esto: está pensado para filas
anchas de lista (logo a la izquierda, texto a la derecha), no para
tarjetas cuadradas en fila. Por eso este módulo tiene su propio widget de
tarjeta en vez de reutilizar el delegado.

No gestiona datos propios: recibe ya construida la lista de entradas
(dict con type/name/url/logo/tvg_id) a mostrar y una función a la que
llamar al pinchar una tarjeta -- así sirve igual para "Recientes" (desde
win.history) que para "Recomendado para ti" (heurística en MainWindow)
sin duplicar lógica de selección aquí.

Coder By X@R
"""
from typing import Callable, List
from collections import defaultdict, deque

from PySide6.QtCore import Qt
from shiboken6 import isValid
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from ui import palette
from ui.icons import icon_radio, icon_tv
from ui.visual import set_variant, set_visual_state

CARD_WIDTH = 128
CARD_LOGO_SIZE = 96


class CarouselCard(QFrame):
    """Tarjeta compacta clicable: logo arriba, nombre y tipo debajo."""

    def __init__(self, entry: dict, on_activate: Callable[[dict], None], logo_loader=None):
        super().__init__()
        self.setObjectName("carouselCard")
        is_tv = entry.get("type") == "tv"
        set_variant(self, "tv" if is_tv else "radio")
        self.setFixedWidth(CARD_WIDTH)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self._entry = dict(entry)
        self._logo_token = 0
        self._on_activate = on_activate
        self.setAccessibleName(f"Reproducir {entry.get('name', '')}")
        self.setToolTip(entry.get("name", ""))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.logo_label = QLabel()
        self.logo_label.setObjectName("carouselLogo")
        self.logo_label.setFixedSize(CARD_LOGO_SIZE, CARD_LOGO_SIZE)
        self.logo_label.setAlignment(Qt.AlignCenter)
        placeholder_builder = icon_tv if is_tv else icon_radio
        placeholder_color = palette.ACCENT_INFO if is_tv else palette.ACCENT_CATEGORY_ORANGE
        self.logo_label.setPixmap(placeholder_builder(placeholder_color, size=36).pixmap(36, 36))
        layout.addWidget(self.logo_label, alignment=Qt.AlignHCenter)

        name_label = QLabel(entry.get("name", ""))
        self.name_label = name_label
        name_label.setObjectName("carouselName")
        name_label.setWordWrap(True)
        name_label.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        name_label.setFixedHeight(34)
        layout.addWidget(name_label)

        # "subtitle" (opcional) sustituye al texto fijo "TV en directo" /
        # "Radio online" -- lo usa el panel "Ahora en antena" de Inicio
        # para enseñar qué programa está emitiendo cada canal ahora mismo,
        # en vez de solo repetir el tipo de contenido.
        kind_label = QLabel(entry.get("subtitle") or ("TV en directo" if is_tv else "Radio online"))
        self.kind_label = kind_label
        kind_label.setObjectName("carouselMeta")
        kind_label.setAlignment(Qt.AlignHCenter)
        kind_label.setWordWrap(True)
        kind_label.setFixedHeight(28)
        layout.addWidget(kind_label)

        logo_url = entry.get("logo", "")
        self._logo_loader = logo_loader
        if logo_url and logo_loader is not None:
            self._load_logo(logo_url)

    def _load_logo(self, url):
        token = self._logo_token
        self._logo_loader.load(
            url, lambda pixmap: self._on_logo_ready(pixmap, token), size=CARD_LOGO_SIZE,
        )

    def _on_logo_ready(self, pixmap, token):
        if isValid(self.logo_label) and token == self._logo_token:
            self.logo_label.setPixmap(pixmap)

    def update_entry(self, entry):
        if self._entry == entry:
            return
        old_logo = self._entry.get("logo", "")
        self._entry = dict(entry)
        name = entry.get("name", "")
        self.name_label.setText(name)
        self.setAccessibleName(f"Reproducir {name}")
        self.setToolTip(name)
        is_tv = entry.get("type") == "tv"
        self.kind_label.setText(entry.get("subtitle") or ("TV en directo" if is_tv else "Radio online"))
        if old_logo != entry.get("logo", ""):
            self._logo_token += 1
            builder = icon_tv if is_tv else icon_radio
            color = palette.ACCENT_INFO if is_tv else palette.ACCENT_CATEGORY_ORANGE
            self.logo_label.setPixmap(builder(color, size=36).pixmap(36, 36))
            if entry.get("logo") and self._logo_loader is not None:
                self._load_logo(entry["logo"])

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            if not event.isAutoRepeat() and self._entry.get("url"):
                self._on_activate(self._entry)
            event.accept()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._entry.get("url"):
            self._on_activate(self._entry)
        super().mousePressEvent(event)


class Carousel(QWidget):
    """Fila horizontal de CarouselCard con scroll propio y mensaje vacío."""

    def __init__(
        self,
        on_activate: Callable[[dict], None],
        logo_loader=None,
        empty_text: str = "Nada que mostrar todavía.",
    ):
        super().__init__()
        self._on_activate = on_activate
        self._logo_loader = logo_loader
        self._cards = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll.setFixedHeight(190)

        self._inner = QWidget()
        self._row = QHBoxLayout(self._inner)
        self._row.setContentsMargins(2, 2, 2, 8)
        self._row.setSpacing(10)
        self._row.addStretch(1)
        self.scroll.setWidget(self._inner)
        outer.addWidget(self.scroll)

        self.empty_label = QLabel(empty_text)
        self.empty_label.setObjectName("carouselEmpty")
        self.empty_label.setWordWrap(True)
        self.empty_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        set_visual_state(self.empty_label, "empty")
        outer.addWidget(self.empty_label)
        self.empty_label.setVisible(False)

    def set_entries(self, entries: List[dict]):
        entries = [e for e in entries if e.get("url")]
        if [card._entry for card in self._cards] == entries:
            self.empty_label.setVisible(not entries)
            self.scroll.setVisible(bool(entries))
            return
        available = defaultdict(deque)
        for card in self._cards:
            available[(card._entry.get("type"), card._entry.get("url"))].append(card)
            self._row.removeWidget(card)
        cards = []
        for entry in entries:
            matches = available[(entry.get("type"), entry.get("url"))]
            if matches:
                card = matches.popleft()
                card.update_entry(entry)
            else:
                card = CarouselCard(entry, self._on_activate, self._logo_loader)
            self._row.insertWidget(self._row.count() - 1, card)
            cards.append(card)
        for remaining in available.values():
            for card in remaining:
                card.hide()
                card.deleteLater()
        self._cards = cards
        self.empty_label.setVisible(not entries)
        self.scroll.setVisible(bool(entries))
