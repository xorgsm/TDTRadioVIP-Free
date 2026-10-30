"""
Vista de reposo del área de emisión: lo que ocupa player_stack mientras
no suena nada. Antes ahí quedaba el lienzo negro de libVLC, casi la mitad
de la ventana sin ninguna función; ahora ofrece retomar la última emisión,
abrir la búsqueda (Ctrl+K) y saltar a las emisiones recientes y favoritas
sin cambiar de sección.

Solo presenta datos: quien la puebla (refresh) es MainWindow a través de
PlaybackController/HomeController, con las mismas entradas de historial y
favoritos que ya usan los carruseles de Inicio.

Coder By X@R
"""
from typing import Callable, Iterable

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QLabel, QPushButton, QSizePolicy, QToolButton, QVBoxLayout,
    QWidget,
)

from ui import icons as app_icons
from ui import palette
from ui.catalog_labels import split_name_tags
from ui.visual import set_variant

# Umbrales de la vista según el espacio del área de emisión: a 860×580
# solo caben título y botones; el icono, la explicación y los accesos
# rápidos aparecen cuando hay sitio (ver _apply_size).
ICON_MIN_HEIGHT = 380
DETAILS_MIN_HEIGHT = 300
SEARCH_TEXT_MIN_WIDTH = 360
# Accesos rápidos visibles a la vez: más de cuatro convierte la vista de
# reposo en un segundo catálogo, que ya existe en TV/Radio/Favoritos.
MAX_QUICK_ENTRIES = 4


def _entry_key(entry: dict) -> tuple:
    return (entry.get("type", "tv"), entry.get("name", ""))


def pick_quick_entries(history: Iterable[dict], favorites: Iterable[dict],
                       exclude: dict | None = None, limit: int = MAX_QUICK_ENTRIES) -> list:
    """
    Recientes primero y después favoritos, sin repetir canal ni incluir
    `exclude` (la entrada que ya ofrece el botón principal). Solo entradas
    con URL: una tarjeta que no se puede reproducir no es un acceso rápido.
    """
    seen = {_entry_key(exclude)} if exclude else set()
    picked = []
    for entry in list(history or []) + list(favorites or []):
        if not isinstance(entry, dict) or not entry.get("url"):
            continue
        key = _entry_key(entry)
        if key in seen:
            continue
        seen.add(key)
        picked.append(entry)
        if len(picked) >= limit:
            break
    return picked


class PlayerIdleView(QWidget):
    """Estado vacío accionable del reproductor."""

    def __init__(self, on_activate: Callable[[dict], None], on_search: Callable[[], None], parent=None):
        super().__init__(parent)
        self.setObjectName("playerIdleView")
        self._on_activate = on_activate
        self._on_search = on_search
        self._resume_entry = None
        self._resume_name = ""
        self._has_quick_entries = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(0)
        outer.addStretch(1)

        column = QVBoxLayout()
        column.setSpacing(10)

        self.icon_label = QLabel()
        self.icon_label.setObjectName("playerIdleIcon")
        self.icon_label.setFixedSize(64, 64)
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setPixmap(app_icons.icon_play(palette.ACCENT, 30).pixmap(30, 30))
        self.icon_label.setStyleSheet(
            f"QLabel#playerIdleIcon {{ background-color: {palette.BG_CARD};"
            f" border: 1px solid {palette.BORDER}; border-radius: 32px; }}"
        )
        column.addWidget(self.icon_label, alignment=Qt.AlignHCenter)
        column.addSpacing(6)

        # No repite "Nada en reproducción": eso ya lo dice la barra de abajo.
        self.title = QLabel("¿Qué te apetece ver o escuchar?")
        self.title.setObjectName("nowTitle")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setWordWrap(True)
        column.addWidget(self.title)

        self.subtitle = QLabel()
        self.subtitle.setObjectName("nowSubtitle")
        self.subtitle.setAlignment(Qt.AlignCenter)
        self.subtitle.setWordWrap(True)
        column.addWidget(self.subtitle)
        column.addSpacing(8)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions.addStretch(1)
        self.resume_btn = QPushButton()
        set_variant(self.resume_btn, "primary")
        self.resume_btn.setCursor(Qt.PointingHandCursor)
        self.resume_btn.clicked.connect(self._resume)
        actions.addWidget(self.resume_btn)
        self.search_btn = QPushButton("Buscar")
        set_variant(self.search_btn, "secondary")
        self.search_btn.setIcon(app_icons.icon_search(palette.TEXT_SECONDARY, 18))
        self.search_btn.setToolTip("Buscar canal o emisora (Ctrl+K)")
        self.search_btn.setCursor(Qt.PointingHandCursor)
        self.search_btn.clicked.connect(lambda: self._on_search())
        actions.addWidget(self.search_btn)
        actions.addStretch(1)
        column.addLayout(actions)
        column.addSpacing(18)

        self.quick_heading = QLabel("RECIENTES Y FAVORITOS")
        self.quick_heading.setObjectName("dialogSectionLabel")
        self.quick_heading.setAlignment(Qt.AlignCenter)
        column.addWidget(self.quick_heading)

        self._quick_layout = QVBoxLayout()
        self._quick_layout.setSpacing(4)
        column.addLayout(self._quick_layout)

        # Ancho de lectura acotado: en un panel de reproductor ancho, los
        # accesos rápidos estirados de borde a borde se leen peor.
        holder = QWidget()
        holder.setLayout(column)
        holder.setMaximumWidth(420)
        holder.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        outer.addWidget(holder, alignment=Qt.AlignHCenter)
        outer.addStretch(2)

        self.refresh([], [])

    def resizeEvent(self, event):  # noqa: N802 - API de Qt
        super().resizeEvent(event)
        self._apply_size()

    def _apply_size(self) -> None:
        width, height = self.width(), self.height()
        self.icon_label.setVisible(height >= ICON_MIN_HEIGHT)
        roomy = height >= DETAILS_MIN_HEIGHT
        self.subtitle.setVisible(roomy)
        self.quick_heading.setVisible(roomy and self._has_quick_entries)
        for i in range(self._quick_layout.count()):
            widget = self._quick_layout.itemAt(i).widget()
            if widget is not None:
                widget.setVisible(roomy)
        wide = width >= SEARCH_TEXT_MIN_WIDTH
        self.search_btn.setText("Buscar" if wide else "")
        if self._resume_name:
            # El botón se queda con lo que deja libre Buscar (y los márgenes);
            # el texto, con eso menos icono y padding.
            btn_width = max(120, min(280, width - (130 if wide else 70) - 64))
            self.resume_btn.setMaximumWidth(btn_width)
            self.resume_btn.setText(self.resume_btn.fontMetrics().elidedText(
                f"Volver a {self._resume_name}", Qt.ElideRight, btn_width - 64
            ))

    # ---------- Poblado ----------

    def refresh(self, history, favorites) -> None:
        recent = next(
            (e for e in (history or []) if isinstance(e, dict) and e.get("url")), None
        )
        self._resume_entry = recent
        self._resume_name = split_name_tags(recent.get("name", ""))[0] if recent else ""
        if recent:
            self.subtitle.setText("Retoma lo último que pusiste o elige otra emisión.")
            self.resume_btn.setToolTip(f"Volver a {self._resume_name}")
            self.resume_btn.setIcon(app_icons.icon_play(palette.BG_ROOT, 18))
            self.resume_btn.setVisible(True)
        else:
            self.subtitle.setText("Elige un canal o una emisora, o búscalo con Ctrl+K.")
            self.resume_btn.setVisible(False)

        while self._quick_layout.count():
            item = self._quick_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        entries = pick_quick_entries(history, favorites, exclude=recent)
        for entry in entries:
            self._quick_layout.addWidget(self._make_quick_button(entry))
        self._has_quick_entries = bool(entries)
        self._apply_size()

    def _make_quick_button(self, entry: dict) -> QToolButton:
        btn = QToolButton()
        btn.setObjectName("playerIdleQuick")
        btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn.setCursor(Qt.PointingHandCursor)
        is_tv = entry.get("type", "tv") == "tv"
        color = palette.ACCENT_INFO if is_tv else palette.ACCENT_CATEGORY_ORANGE
        btn.setIcon(app_icons.icon_tv(color, 18) if is_tv else app_icons.icon_radio(color, 18))
        btn.setIconSize(QSize(18, 18))
        name = split_name_tags(entry.get("name", ""))[0]
        btn.setText(btn.fontMetrics().elidedText(name, Qt.ElideRight, 320))
        btn.setToolTip(f"Reproducir {name}")
        btn.setStyleSheet(
            f"QToolButton#playerIdleQuick {{ background: transparent; color: {palette.TEXT_SECONDARY};"
            f" border: 1px solid transparent; border-radius: 10px; padding: 7px 12px; text-align: left; }}"
            f"QToolButton#playerIdleQuick:hover {{ background-color: {palette.BG_CARD};"
            f" border-color: {palette.BORDER}; color: {palette.TEXT_PRIMARY}; }}"
            f"QToolButton#playerIdleQuick:focus {{ border-color: {palette.ACCENT_LIGHT}; }}"
        )
        btn.clicked.connect(lambda _checked=False, e=entry: self._on_activate(e))
        return btn

    def _resume(self) -> None:
        if self._resume_entry:
            self._on_activate(self._resume_entry)
