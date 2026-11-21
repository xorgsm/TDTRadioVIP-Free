"""
Vista de parrilla de la Guía (fase 3 del rediseño 10.0, «Teleprograma»).

Pinta la guía EPG como la parrilla de un periódico: regla de horas arriba,
columna de canales a la izquierda, una fila por canal con sus programas como
bloques y la línea vertical de «ahora». Las posiciones salen de
:func:`core.guide_grid.build_rows` (fracciones 0–1 de la ventana horaria);
aquí solo se multiplican por píxeles.

Decisiones:

- La ventana es el día entero mostrado (00:00 + 24 h, hora local naive como
  ``core.guide_grid``) con desplazamiento horizontal; al abrir hoy se coloca
  media hora antes de «ahora», y otro día en la franja de noche (20:00).
- Filas virtualizadas: ``refresh()`` solo filtra la lista de canales; las
  celdas de cada fila se calculan al pintarla por primera vez y se guardan en
  caché. Nunca se pintan más de ``MAX_PAINTED_ROWS`` filas por pasada.
- Un canal sin ``tvg_id`` también tiene fila (con «Sin programación»):
  ``build_rows`` lo omite porque no puede cruzarlo con la guía, pero en la
  vista el canal tiene que seguir ahí.
- Filtros «Cine» y «Deportes» por la categoría del canal (``Channel.group``,
  traducida con ``ui.catalog_labels.humanize_group``): ``Programme`` no trae
  género. «Favoritos» por nombre de canal (``set_favorites``).
- Colores leídos de ``ui.palette`` en cada pintado (cambio de tema en
  caliente); el programa en emisión usa la tinta de la sección Guía.
"""
from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from PySide6.QtCore import QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractScrollArea, QHBoxLayout, QPushButton, QVBoxLayout, QWidget,
)

from core.epg import Programme, channel_key, parse_xmltv_time
from core.guide_grid import GuideRow, build_rows
from ui import palette
from ui.catalog_labels import humanize_group
from ui.visual import ElidedLabel

GUIDE_FILTERS = ("all", "favorites", "cinema", "sports")
_FILTER_LABELS = {"all": "Todos", "favorites": "Favoritos", "cinema": "Cine", "sports": "Deportes"}
# Categoría traducida (humanize_group) que deja pasar cada filtro.
_FILTER_GROUPS = {"cinema": "cine", "sports": "deportes"}
_DAY_LABELS = {-1: "Ayer", 0: "Hoy", 1: "Mañana"}

NO_PROGRAMMING = "Sin programación"
MAX_PAINTED_ROWS = 60
ROW_HEIGHT = 56
RULER_HEIGHT = 34
CHANNEL_COLUMN = 132
PX_PER_HOUR = 240
DAY_HOURS = 24
_EVENING_HOUR = 20
_NOW_TICK_MS = 60_000

_WEEKDAYS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")
_MONTHS = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")


def _blend(fg: str, bg: str, alpha: float) -> str:
    a, b = QColor(fg), QColor(bg)
    mix = [round(alpha * x + (1 - alpha) * y)
           for x, y in ((a.red(), b.red()), (a.green(), b.green()), (a.blue(), b.blue()))]
    return QColor(*mix).name()


def now_cell_colors() -> Tuple[str, str, str]:
    """``(fondo, borde, texto)`` del programa en emisión: tinta de la Guía
    (``palette.ACCENT_GUIDE``) al 22 % sobre la tarjeta, como la maqueta."""
    return (
        _blend(palette.ACCENT_GUIDE, palette.BG_CARD, 0.22),
        palette.ACCENT_GUIDE,
        palette.TEXT_PRIMARY,
    )


def _display_font(pixel_size: int, weight=QFont.Bold) -> QFont:
    font = QFont()
    font.setFamilies(["Barlow Condensed", "Arial Narrow", "Segoe UI"])
    font.setPixelSize(pixel_size)
    font.setWeight(weight)
    return font


def _day_title(day: date, today: date) -> str:
    stamp = f"{_WEEKDAYS[day.weekday()]} {day.day} {_MONTHS[day.month - 1]}"
    relative = _DAY_LABELS.get((day - today).days)
    return (f"{relative} · {stamp}" if relative else stamp).upper()


class GuideGrid(QAbstractScrollArea):
    """Parrilla con pintado propio. Los datos los da la ``GuideView`` dueña."""

    cell_clicked = Signal(int, int)

    def __init__(self, view: "GuideView"):
        super().__init__(view)
        self._view = view
        self.setObjectName("guideGrid")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAccessibleName("Parrilla de programación")
        self.setFocusPolicy(Qt.StrongFocus)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.viewport().setMouseTracking(True)
        self._selected: Optional[Tuple[int, int]] = None
        self._hover: Optional[Tuple[int, int]] = None
        self._pending_scroll_px: Optional[int] = None
        self._painted_labels: List[str] = []
        self._painted_rows = 0

    # ── Geometría (compartida por el pintado y la detección de clics) ──
    def row_height(self) -> int:
        return ROW_HEIGHT

    def ruler_height(self) -> int:
        return RULER_HEIGHT

    def lane_left(self) -> int:
        return CHANNEL_COLUMN

    def lane_total_width(self) -> int:
        return PX_PER_HOUR * DAY_HOURS

    def _row_top(self, index: int) -> int:
        return RULER_HEIGHT + index * ROW_HEIGHT - self.verticalScrollBar().value()

    def _lane_x(self, fraction: float) -> float:
        return CHANNEL_COLUMN + fraction * self.lane_total_width() - self.horizontalScrollBar().value()

    def _cell_rectf(self, index: int, cell) -> QRectF:
        x = self._lane_x(cell.left)
        width = cell.width * self.lane_total_width()
        return QRectF(x + 2, self._row_top(index) + 5, max(0.0, width - 4), ROW_HEIGHT - 10)

    def cell_rect(self, row_index: int, cell_index: int) -> QRect:
        """Rectángulo de la celda en coordenadas del viewport (sin recortar)."""
        cell = self._view.row(row_index).cells[cell_index]
        return self._cell_rectf(row_index, cell).toAlignedRect()

    def cell_at(self, pos) -> Optional[Tuple[int, int]]:
        x, y = pos.x(), pos.y()
        if x < CHANNEL_COLUMN or y < RULER_HEIGHT:
            return None
        index = (y - RULER_HEIGHT + self.verticalScrollBar().value()) // ROW_HEIGHT
        if not 0 <= index < self._view.row_count():
            return None
        for cell_index, cell in enumerate(self._view.row(index).cells):
            if self._cell_rectf(index, cell).contains(QPointF(x, y)):
                return index, cell_index
        return None

    def now_x(self) -> Optional[float]:
        """X de la línea de «ahora» en el viewport, o None si no se ve."""
        fraction = self._view.now_fraction()
        if fraction is None:
            return None
        x = self._lane_x(fraction)
        if x < CHANNEL_COLUMN or x > self.viewport().width():
            return None
        return x

    # ── Estado para la vista y los tests ──
    def painted_labels(self) -> List[str]:
        """Textos de la última pasada de pintado (comprobación estructural)."""
        return list(self._painted_labels)

    def painted_row_count(self) -> int:
        return self._painted_rows

    def clear_selection(self) -> None:
        self._selected = None
        self._hover = None

    def scroll_to_fraction(self, fraction: float) -> None:
        """Deja ``fraction`` de la ventana en el borde izquierdo de la pista
        (en cuanto la barra tenga rango, si aún no se ha maquetado)."""
        self._pending_scroll_px = max(0, round(fraction * self.lane_total_width()))
        self.update_scrollbars()

    def update_scrollbars(self) -> None:
        viewport = self.viewport().size()
        lane_visible = max(0, viewport.width() - CHANNEL_COLUMN)
        rows_visible = max(0, viewport.height() - RULER_HEIGHT)
        hbar, vbar = self.horizontalScrollBar(), self.verticalScrollBar()
        hbar.setRange(0, max(0, self.lane_total_width() - lane_visible))
        hbar.setPageStep(max(1, lane_visible))
        hbar.setSingleStep(PX_PER_HOUR // 4)
        vbar.setRange(0, max(0, self._view.row_count() * ROW_HEIGHT - rows_visible))
        vbar.setPageStep(max(1, rows_visible))
        vbar.setSingleStep(ROW_HEIGHT)
        if self._pending_scroll_px is not None and hbar.maximum() > 0:
            hbar.setValue(min(self._pending_scroll_px, hbar.maximum()))
            self._pending_scroll_px = None
        self.viewport().update()

    # ── Eventos ──
    def resizeEvent(self, event):  # noqa: N802 - API de Qt
        super().resizeEvent(event)
        self.update_scrollbars()

    def scrollContentsBy(self, _dx, _dy):  # noqa: N802 - API de Qt
        self.viewport().update()

    def mousePressEvent(self, event):  # noqa: N802 - API de Qt
        if event.button() == Qt.LeftButton:
            hit = self.cell_at(event.position().toPoint())
            if hit is not None:
                self._selected = hit
                self.viewport().update()
                self.cell_clicked.emit(*hit)
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # noqa: N802 - API de Qt
        hit = self.cell_at(event.position().toPoint())
        if hit != self._hover:
            self._hover = hit
            self.viewport().setCursor(Qt.PointingHandCursor if hit else Qt.ArrowCursor)
            self.viewport().update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event):  # noqa: N802 - API de Qt
        if self._hover is not None:
            self._hover = None
            self.viewport().update()
        super().leaveEvent(event)

    # ── Pintado ──
    def paintEvent(self, _event):  # noqa: N802 - API de Qt
        painter = QPainter(self.viewport())
        try:
            self._paint(painter)
        finally:
            painter.end()

    def _paint(self, p: QPainter) -> None:
        self._painted_labels = []
        width, height = self.viewport().width(), self.viewport().height()
        p.fillRect(0, 0, width, height, QColor(palette.BG_PANEL))
        body_font = QFont(self.font())
        title_font = QFont(body_font)
        title_font.setPixelSize(13)
        title_font.setWeight(QFont.Bold)
        time_font = QFont(body_font)
        time_font.setPixelSize(11)

        count = self._view.row_count()
        vbar_value = self.verticalScrollBar().value()
        first = vbar_value // ROW_HEIGHT
        fits = math.ceil(max(0, height - RULER_HEIGHT) / ROW_HEIGHT) + 1
        last = min(count, first + min(fits, MAX_PAINTED_ROWS))
        self._painted_rows = max(0, last - first)

        # Pistas de programas, recortadas a la zona a la derecha de los canales.
        p.save()
        p.setClipRect(CHANNEL_COLUMN, RULER_HEIGHT, max(0, width - CHANNEL_COLUMN),
                      max(0, height - RULER_HEIGHT))
        now_bg, now_border, now_text = now_cell_colors()
        for index in range(first, last):
            row = self._view.row(index)
            top = self._row_top(index)
            if not row.cells:
                p.setFont(time_font)
                p.setPen(QColor(palette.TEXT_DIM))
                p.drawText(QRect(CHANNEL_COLUMN + 12, top, max(0, width - CHANNEL_COLUMN - 12), ROW_HEIGHT),
                           Qt.AlignVCenter | Qt.AlignLeft, NO_PROGRAMMING)
                self._painted_labels.append(NO_PROGRAMMING)
            for cell_index, cell in enumerate(row.cells):
                rect = self._cell_rectf(index, cell)
                if rect.width() < 1 or rect.right() < CHANNEL_COLUMN or rect.left() > width:
                    continue
                self._paint_cell(p, rect, cell, (index, cell_index),
                                 title_font, time_font, (now_bg, now_border, now_text))
            p.setPen(QPen(QColor(palette.BORDER), 1))
            p.drawLine(CHANNEL_COLUMN, top + ROW_HEIGHT - 1, width, top + ROW_HEIGHT - 1)
        p.restore()

        self._paint_channels(p, first, last, height)
        self._paint_ruler(p, width)
        self._paint_now_line(p, height)

    def _paint_cell(self, p, rect: QRectF, cell, key, title_font, time_font, now_colors) -> None:
        now_bg, now_border, now_text = now_colors
        if cell.is_now:
            background, border, text = now_bg, now_border, now_text
        else:
            background, border, text = palette.BG_CARD, palette.BORDER, palette.TEXT_PRIMARY
        if key == self._hover and not cell.is_now:
            background = palette.BG_HOVER
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(QPen(QColor(border), 1))
        p.setBrush(QColor(background))
        p.drawRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), 8, 8)
        if key == self._selected:
            p.setPen(QPen(QColor(palette.TEXT_PRIMARY), 2))
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(rect.adjusted(-1, -1, 1, 1), 9, 9)
        p.setRenderHint(QPainter.Antialiasing, False)
        # La parte visible del bloque: el texto sigue al borde izquierdo de la
        # pista cuando el programa empezó antes de lo que se ve.
        visible_left = max(rect.left(), float(CHANNEL_COLUMN))
        inner = QRectF(visible_left + 10, rect.top() + 5, rect.right() - visible_left - 18,
                       rect.height() - 10)
        if inner.width() < 12:
            return
        p.setFont(title_font)
        p.setPen(QColor(text))
        title = p.fontMetrics().elidedText(cell.title, Qt.ElideRight, int(inner.width()))
        p.drawText(inner, Qt.AlignLeft | Qt.AlignTop, title)
        self._painted_labels.append(cell.title)
        start = self._view.programme_start(cell)
        if start:
            p.setFont(time_font)
            p.setPen(QColor(palette.TEXT_MUTED))
            p.drawText(inner, Qt.AlignLeft | Qt.AlignBottom,
                       p.fontMetrics().elidedText(start, Qt.ElideRight, int(inner.width())))

    def _paint_channels(self, p, first: int, last: int, height: int) -> None:
        p.fillRect(0, RULER_HEIGHT, CHANNEL_COLUMN, max(0, height - RULER_HEIGHT), QColor(palette.BG_PANEL))
        p.save()
        p.setClipRect(0, RULER_HEIGHT, CHANNEL_COLUMN, max(0, height - RULER_HEIGHT))
        p.setFont(_display_font(16))
        for index in range(first, last):
            top = self._row_top(index)
            name = (self._view.row(index).channel_name or "").upper()
            p.setPen(QColor(palette.TEXT_PRIMARY))
            text_rect = QRect(12, top, CHANNEL_COLUMN - 20, ROW_HEIGHT)
            p.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft,
                       p.fontMetrics().elidedText(name, Qt.ElideRight, text_rect.width()))
            self._painted_labels.append(name)
            p.setPen(QPen(QColor(palette.BORDER), 1))
            p.drawLine(0, top + ROW_HEIGHT - 1, CHANNEL_COLUMN, top + ROW_HEIGHT - 1)
        p.restore()
        p.setPen(QPen(QColor(palette.BORDER_STRONG), 1))
        p.drawLine(CHANNEL_COLUMN - 1, RULER_HEIGHT, CHANNEL_COLUMN - 1, height)

    def _paint_ruler(self, p, width: int) -> None:
        p.fillRect(0, 0, width, RULER_HEIGHT, QColor(palette.BG_PANEL))
        p.save()
        p.setClipRect(CHANNEL_COLUMN, 0, max(0, width - CHANNEL_COLUMN), RULER_HEIGHT)
        p.setFont(_display_font(15))
        window_start = self._view.window_start()
        half_hours = DAY_HOURS * 2
        for step in range(half_hours):
            x = round(self._lane_x(step / half_hours))
            if x > width or x + PX_PER_HOUR // 2 < CHANNEL_COLUMN:
                continue
            p.setPen(QPen(QColor(palette.BORDER), 1))
            p.drawLine(x, 0, x, RULER_HEIGHT)
            label = (window_start + timedelta(minutes=30 * step)).strftime("%H:%M")
            p.setPen(QColor(palette.TEXT_SECONDARY))
            p.drawText(QRect(x + 8, 0, PX_PER_HOUR // 2 - 8, RULER_HEIGHT),
                       Qt.AlignVCenter | Qt.AlignLeft, label)
        p.restore()
        p.setPen(QPen(QColor(palette.BORDER_STRONG), 1))
        p.drawLine(0, RULER_HEIGHT - 1, width, RULER_HEIGHT - 1)

    def _paint_now_line(self, p, height: int) -> None:
        x = self.now_x()
        if x is None:
            return
        # Bloque vivo con texto en tinta: mismo tono en ambos temas (Ink On Blocks).
        block = QColor(palette.tone("ACCENT_GUIDE", "dark"))
        line = QColor(palette.ACCENT_GUIDE)
        p.fillRect(QRectF(x - 1, RULER_HEIGHT, 2, max(0, height - RULER_HEIGHT)), line)
        label = self._view.now().strftime("%H:%M")
        font = _display_font(13, QFont.ExtraBold)
        p.setFont(font)
        badge_w = p.fontMetrics().horizontalAdvance(label) + 10
        left = min(max(x - badge_w / 2, float(CHANNEL_COLUMN)), self.viewport().width() - badge_w)
        badge = QRectF(left, 7, badge_w, RULER_HEIGHT - 14)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(Qt.NoPen)
        p.setBrush(block)
        p.drawRoundedRect(badge, 4, 4)
        p.setRenderHint(QPainter.Antialiasing, False)
        p.setPen(QColor(palette.INK))
        p.drawText(badge, Qt.AlignCenter, label)


class GuideView(QWidget):
    """Página «Guía»: cabecera con día y filtro, y la parrilla.

    ``programme_selected`` lleva ``tvg_id, channel_name, channel_url, title,
    start, stop, description`` (``start``/``stop`` en XMLTV original: clave de
    avisos y grabaciones programadas).
    """

    programme_selected = Signal(dict)

    def __init__(
        self,
        channels: Sequence,
        guide: Dict[str, List[Programme]],
        parent: Optional[QWidget] = None,
        *,
        favorites: Iterable[str] = (),
        clock: Optional[Callable[[], datetime]] = None,
    ):
        super().__init__(parent)
        self.setObjectName("guideView")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self._clock = clock or datetime.now
        self._all_channels: List = list(channels or [])
        self._guide: Dict[str, List[Programme]] = guide or {}
        self._favorites = set(favorites or ())
        self._filter = "all"
        self._day = self.now().date()
        self._channels: List = []
        self._rows: Dict[int, GuideRow] = {}
        self._row_now: Optional[datetime] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        header = QHBoxLayout()
        header.setSpacing(6)
        self.title_label = ElidedLabel()
        self.title_label.setObjectName("guideTitle")
        header.addWidget(self.title_label, stretch=1)
        self._day_chips: Dict[int, QPushButton] = {}
        for offset, text in _DAY_LABELS.items():
            chip = self._make_chip(text)
            chip.clicked.connect(lambda _checked=False, o=offset: self.set_day(self.now().date() + timedelta(days=o)))
            self._day_chips[offset] = chip
            header.addWidget(chip)
        layout.addLayout(header)

        filters = QHBoxLayout()
        filters.setSpacing(6)
        self._filter_chips: Dict[str, QPushButton] = {}
        for kind in GUIDE_FILTERS:
            chip = self._make_chip(_FILTER_LABELS[kind])
            chip.clicked.connect(lambda _checked=False, k=kind: self.set_filter(k))
            self._filter_chips[kind] = chip
            filters.addWidget(chip)
        filters.addStretch(1)
        layout.addLayout(filters)

        self.grid = GuideGrid(self)
        self.grid.cell_clicked.connect(self._on_cell_clicked)
        layout.addWidget(self.grid, stretch=1)

        # Mueve la línea de «ahora» y la celda en emisión. Se arranca aquí,
        # no en showEvent ni en cambios de estilo.
        self._now_timer = QTimer(self)
        self._now_timer.setInterval(_NOW_TICK_MS)
        self._now_timer.timeout.connect(self._on_now_tick)
        self._now_timer.start()

        self._sync_chips()
        self.refresh()
        self._scroll_to_default()

    def _make_chip(self, text: str) -> QPushButton:
        chip = QPushButton(text)
        chip.setObjectName("guideChip")
        chip.setCheckable(True)
        chip.setCursor(Qt.PointingHandCursor)
        return chip

    # ── API pública ──
    def set_day(self, day: date) -> None:
        self._day = day
        self._sync_chips()
        self.refresh()
        self._scroll_to_default()

    def set_filter(self, kind: str) -> None:
        if kind not in GUIDE_FILTERS:
            raise ValueError(f"Filtro de guía desconocido: {kind!r}")
        self._filter = kind
        self._sync_chips()
        self.refresh()
        self.grid.verticalScrollBar().setValue(0)

    def set_favorites(self, names: Iterable[str]) -> None:
        self._favorites = set(names or ())
        self.refresh()

    def set_channels(self, channels: Sequence) -> None:
        self._all_channels = list(channels or [])
        self.refresh()

    def set_guide(self, guide: Dict[str, List[Programme]]) -> None:
        self._guide = guide or {}
        self.refresh()

    def refresh(self) -> None:
        """Vuelve a filtrar los canales. Las celdas se recalculan al pintar;
        el desplazamiento vertical se conserva (acotado al nuevo rango)."""
        self._channels = [c for c in self._all_channels if self._passes_filter(c)]
        self._rows = {}
        self._row_now = self.now()
        self.grid.clear_selection()
        self.grid.update_scrollbars()

    def current_day(self) -> date:
        return self._day

    def current_filter(self) -> str:
        return self._filter

    def title_text(self) -> str:
        return self.title_label.text()

    def day_chip(self, offset: int) -> QPushButton:
        return self._day_chips[offset]

    def filter_chip(self, kind: str) -> QPushButton:
        return self._filter_chips[kind]

    def now(self) -> datetime:
        return self._clock()

    def window_start(self) -> datetime:
        return datetime.combine(self._day, time())

    def now_fraction(self) -> Optional[float]:
        """Posición de «ahora» en la ventana (0–1), o None si es otro día."""
        offset = (self.now() - self.window_start()).total_seconds()
        total = DAY_HOURS * 3600
        if not 0 <= offset <= total:
            return None
        return offset / total

    def row_count(self) -> int:
        return len(self._channels)

    def row(self, index: int) -> GuideRow:
        row = self._rows.get(index)
        if row is None:
            channel = self._channels[index]
            tvg_id = getattr(channel, "tvg_id", "") or ""
            built = build_rows(self._guide, [channel], self.window_start(), DAY_HOURS, self._row_now)
            row = built[0] if built else GuideRow(
                tvg_id=tvg_id, channel_name=getattr(channel, "name", "") or "", cells=[]
            )
            self._rows[index] = row
        return row

    def programme_start(self, cell) -> str:
        """Hora «HH:MM» de inicio real del programa de ``cell`` (no la recortada)."""
        start = parse_xmltv_time(cell.start)
        return start.strftime("%H:%M") if start else ""

    # ── Interno ──
    def _passes_filter(self, channel) -> bool:
        if self._filter == "all":
            return True
        if self._filter == "favorites":
            return (getattr(channel, "name", "") or "") in self._favorites
        wanted = _FILTER_GROUPS[self._filter]
        labels = humanize_group(getattr(channel, "group", "") or "").split(" · ")
        return any(label.casefold() == wanted for label in labels)

    def _sync_chips(self) -> None:
        today = self.now().date()
        for offset, chip in self._day_chips.items():
            chip.setChecked(self._day == today + timedelta(days=offset))
        for kind, chip in self._filter_chips.items():
            chip.setChecked(kind == self._filter)
        self.title_label.setText(_day_title(self._day, today))

    def _scroll_to_default(self) -> None:
        fraction = self.now_fraction()
        if fraction is None:
            fraction = _EVENING_HOUR / DAY_HOURS
        else:
            fraction = max(0.0, fraction - 0.5 / DAY_HOURS)
        self.grid.scroll_to_fraction(fraction)

    def _find_programme(self, cell) -> Optional[Programme]:
        for programme in self._guide.get(channel_key(cell.tvg_id), ()):
            if programme.start == cell.start and programme.stop == cell.stop and \
                    (programme.title or "") == cell.title:
                return programme
        return None

    def _on_cell_clicked(self, row_index: int, cell_index: int) -> None:
        row = self.row(row_index)
        cell = row.cells[cell_index]
        channel = self._channels[row_index]
        programme = self._find_programme(cell)
        self.programme_selected.emit({
            "tvg_id": row.tvg_id,
            "channel_name": row.channel_name,
            "channel_url": getattr(channel, "url", "") or "",
            "title": cell.title,
            "start": cell.start,
            "stop": cell.stop,
            "description": (programme.description if programme is not None else "") or "",
        })

    def showEvent(self, event) -> None:
        super().showEvent(event)
        # Oculta, el temporizador no actualiza nada: al volver, «en emisión»
        # y «ahora» tienen que ir con la hora de ahora, no con la anterior.
        self._refresh_clock()

    def _on_now_tick(self) -> None:
        if self.isVisible():
            self._refresh_clock()

    def _refresh_clock(self) -> None:
        if self._row_now is None or self.now().date() != self._row_now.date():
            # Pasó la medianoche: «Hoy» y el título cambian de día.
            self._sync_chips()
        # Recalcular «en emisión» es barato: solo se rehacen las filas que
        # se vuelvan a pintar.
        self._rows = {}
        self._row_now = self.now()
        self.grid.viewport().update()
