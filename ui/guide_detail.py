"""
Panel de detalle del programa elegido en la parrilla de la Guía (fase 3 del
rediseño 10.0).

Recibe el ``dict`` de ``GuideView.programme_selected`` (``tvg_id,
channel_name, channel_url, title, start, stop, description``) y ofrece cuatro
acciones: **Ver ahora**, **Grabar este programa**, **Avisarme** y **Grabar
siempre (serie)**. No tiene lógica propia de persistencia: reutiliza
``core.epg_reminders``, ``core.recording_schedule`` y
``core.recurring_recordings`` tal cual, y los avisos de conflicto de
``ui.dialogs._common`` (los mismos que el diálogo de la EPG).

Decisiones:

- Ver ahora no sintoniza por sí mismo: emite ``tune_requested(tvg_id)`` y lo
  resuelve quien aloje el panel (``EpgController.tune_to_tvg_id``).
- La cancelación de una reserva se inyecta (``cancel_scheduled``): en la
  ventana real es ``win.tray.cancel_scheduled``, que además para una grabación
  en curso; por defecto solo la quita del calendario.
- La edición Free no graba: con ``recording_enabled=False`` los botones de
  Grabar y Serie no existen en pantalla. Nada aquí importa módulos privados.
- Los botones de acción tienen un guardia contra el doble clic: dos clics
  seguidos sobre el mismo botón cuentan como uno (si no, Avisar/Grabar, que
  alternan, se activarían y se desharían al instante).
- El estado (deshabilitado por «ya terminó», etc.) depende de la hora: se
  recalcula en ``showEvent``, porque oculto el panel no recibe ningún tick.
"""
from __future__ import annotations

import math
import time
from datetime import datetime
from typing import Callable, Dict, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QPushButton, QScrollArea, QVBoxLayout, QWidget

from core import epg_reminders, recording_schedule, recurring_recordings
from core.epg import parse_xmltv_time
from ui.dialogs._common import (
    warn_recording_conflict, warn_rule_conflict, warn_rule_invalid,
)
from ui.visual import plain_label

PANEL_WIDTH = 300
# Dos clics del mismo botón con menos de esto entre sí cuentan como uno.
DOUBLE_CLICK_GUARD_S = 0.5

_WEEKDAYS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


class GuideDetailPanel(QWidget):
    EMPTY_TITLE = "Elige un programa"
    EMPTY_HINT = "Toca un programa de la parrilla para ver su detalle."
    VIEW_TEXT = "Ver ahora"
    RECORD_TEXT = "Grabar este programa"
    CANCEL_RECORD_TEXT = "Cancelar grabación"
    REMIND_TEXT = "Avisarme"
    UNREMIND_TEXT = "Quitar aviso"
    SERIES_TEXT = "Grabar siempre (serie)"
    UNSERIES_TEXT = "Dejar de grabar la serie"

    tune_requested = Signal(str)

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        *,
        cancel_scheduled: Optional[Callable[[str, str, str], object]] = None,
        recording_enabled: bool = True,
        clock: Optional[Callable[[], datetime]] = None,
        monotonic: Optional[Callable[[], float]] = None,
    ):
        super().__init__(parent)
        self.setObjectName("guideDetail")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedWidth(PANEL_WIDTH)
        self._cancel_scheduled = cancel_scheduled or recording_schedule.remove_scheduled
        self._recording_enabled = recording_enabled
        self._clock = clock or datetime.now
        self._monotonic = monotonic or time.monotonic
        self._last_click: Dict[str, float] = {}
        self._info: Optional[dict] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        self.title_label = plain_label()
        self.title_label.setObjectName("guideDetailTitle")
        self.title_label.setWordWrap(True)
        self.meta_label = plain_label()
        self.meta_label.setObjectName("guideDetailMeta")
        self.meta_label.setWordWrap(True)
        self.description_label = plain_label()
        self.description_label.setObjectName("guideDetailText")
        self.description_label.setWordWrap(True)
        self.description_label.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        # Título, hora y sinopsis se desplazan juntos si no caben: los botones
        # nunca salen del panel aunque el texto sea largo o la ventana baja.
        text = QWidget()
        text.setObjectName("guideDetailBody")
        text.setAttribute(Qt.WA_StyledBackground, True)
        text_layout = QVBoxLayout(text)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(6)
        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.meta_label)
        text_layout.addWidget(self.description_label)
        text_layout.addStretch(1)
        self._scroll = QScrollArea()
        self._scroll.setObjectName("guideDetailScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QScrollArea.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setWidget(text)
        root.addWidget(self._scroll, stretch=1)

        self.view_btn = self._make_button("Ver ahora", "view", self._on_view)
        self.record_btn = self._make_button(self.RECORD_TEXT, "record", self._on_record)
        self.remind_btn = self._make_button(self.REMIND_TEXT, "remind", self._on_remind)
        self.series_btn = self._make_button(self.SERIES_TEXT, "series", self._on_series)
        self.view_btn.setProperty("primaryAction", True)
        for button in (self.view_btn, self.record_btn, self.remind_btn, self.series_btn):
            root.addWidget(button)
        for button in (self.record_btn, self.series_btn):
            button.setVisible(recording_enabled)

        self._refresh()

    def _make_button(self, text: str, key: str, handler) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("guideDetailBtn")
        button.setCursor(Qt.PointingHandCursor)
        button.clicked.connect(lambda _checked=False, k=key, h=handler: self._guarded(k, h))
        return button

    # ── API pública ──
    def show_programme(self, info: Optional[dict]) -> None:
        """Muestra el programa de ``info``; ``None`` vuelve al estado vacío."""
        previous = self._identity()
        self._info = dict(info) if info else None
        if self._identity() != previous:
            # El antirrebote es por programa: otro programa no es un doble clic.
            self._last_click.clear()
        self._refresh()

    def title_text(self) -> str:
        return self.title_label.text()

    def meta_text(self) -> str:
        return self.meta_label.text()

    def description_text(self) -> str:
        return self.description_label.text()

    # ── Estado derivado del programa y de la hora ──
    def _times(self):
        info = self._info or {}
        return parse_xmltv_time(info.get("start") or ""), parse_xmltv_time(info.get("stop") or "")

    def _duration_minutes(self) -> Optional[int]:
        start, stop = self._times()
        if start is None or stop is None or stop <= start:
            return None
        return math.ceil((stop - start).total_seconds() / 60)

    def _matching_rule(self):
        info = self._info or {}
        start, _stop = self._times()
        duration = self._duration_minutes()
        if start is None or duration is None:
            return None
        hhmm = start.strftime("%H:%M")
        for rule in recurring_recordings.load_rules():
            if (rule.channel_url == info.get("channel_url") and rule.days == [start.weekday()]
                    and rule.start_time == hhmm and rule.duration_minutes == duration):
                return rule
        return None

    def _identity(self):
        info = self._info or {}
        return info.get("tvg_id") or "", info.get("title") or "", info.get("start") or ""

    def _refresh(self) -> None:
        info = self._info
        if not info:
            self.title_label.setText(self.EMPTY_TITLE)
            self.meta_label.setText("")
            self.description_label.setText(self.EMPTY_HINT)
            for button in (self.view_btn, self.record_btn, self.remind_btn, self.series_btn):
                button.setEnabled(False)
            self.record_btn.setText(self.RECORD_TEXT)
            self.remind_btn.setText(self.REMIND_TEXT)
            self.series_btn.setText(self.SERIES_TEXT)
            return

        start, stop = self._times()
        now = self._clock()
        url = bool(info.get("channel_url"))
        ended = stop is not None and stop <= now
        started = start is not None and start <= now
        tvg_id, title, start_raw = self._identity()

        self.title_label.setText(title)
        when = ""
        if start is not None:
            when = start.strftime("%H:%M") + (f" – {stop.strftime('%H:%M')}" if stop else "")
            when = f"{_WEEKDAYS[start.weekday()]} {when}"
        self.meta_label.setText(" · ".join(p for p in (info.get("channel_name") or "", when) if p))
        self.description_label.setText(info.get("description") or "")

        self.view_btn.setEnabled(url and bool(tvg_id))

        scheduled = bool(tvg_id and start_raw) and recording_schedule.has_scheduled(tvg_id, title, start_raw)
        self.record_btn.setText(self.CANCEL_RECORD_TEXT if scheduled else self.RECORD_TEXT)
        self.record_btn.setEnabled(
            scheduled
            or (url and stop is not None and start is not None and start < stop and not ended)
        )

        reminded = bool(tvg_id and start_raw) and epg_reminders.has_reminder(tvg_id, title, start_raw)
        self.remind_btn.setText(self.UNREMIND_TEXT if reminded else self.REMIND_TEXT)
        self.remind_btn.setEnabled(bool(tvg_id and start_raw) and (reminded or (start is not None and not started)))

        rule = self._matching_rule()
        duration = self._duration_minutes()
        self.series_btn.setText(self.UNSERIES_TEXT if rule else self.SERIES_TEXT)
        self.series_btn.setEnabled(
            rule is not None
            or (url and not ended and duration is not None
                and 1 <= duration <= recurring_recordings.MAX_DURATION_MINUTES)
        )

    def showEvent(self, event) -> None:  # noqa: N802 - API de Qt
        super().showEvent(event)
        self._refresh()

    # ── Acciones ──
    def _guarded(self, key: str, handler) -> None:
        now = self._monotonic()
        last = self._last_click.get(key)
        if last is not None and now - last < DOUBLE_CLICK_GUARD_S:
            return
        self._last_click[key] = now
        if self._info:
            # La hora pudo cambiar desde el último refresco: se revalida antes de actuar.
            self._refresh()
            handler()
        self._refresh()

    def _on_view(self) -> None:
        tvg_id = (self._info or {}).get("tvg_id") or ""
        if tvg_id and self.view_btn.isEnabled():
            self.tune_requested.emit(tvg_id)

    def _on_remind(self) -> None:
        if not self.remind_btn.isEnabled():
            return
        info = self._info
        tvg_id, title, start = self._identity()
        if epg_reminders.has_reminder(tvg_id, title, start):
            epg_reminders.remove_reminder(tvg_id, title, start)
        else:
            epg_reminders.add_reminder(epg_reminders.Reminder(
                tvg_id=tvg_id, channel_name=info.get("channel_name") or "", title=title, start=start,
            ))

    def _on_record(self) -> None:
        if not self._recording_enabled or not self.record_btn.isEnabled():
            return
        info = self._info
        tvg_id, title, start = self._identity()
        if recording_schedule.has_scheduled(tvg_id, title, start):
            self._cancel_scheduled(tvg_id, title, start)
            return
        nueva = recording_schedule.ScheduledRecording(
            tvg_id=tvg_id, channel_name=info.get("channel_name") or "",
            channel_url=info.get("channel_url") or "", title=title, start=start,
            stop=info.get("stop") or "",
        )
        conflictos = recording_schedule.find_conflicts(nueva)
        if conflictos:
            warn_recording_conflict(self, conflictos)
        else:
            recording_schedule.add_scheduled(nueva)

    def _on_series(self) -> None:
        if not self._recording_enabled or not self.series_btn.isEnabled():
            return
        rule = self._matching_rule()
        if rule is not None:
            recurring_recordings.remove_rule(rule.id)
            return
        start, _stop = self._times()
        duration = self._duration_minutes()
        info = self._info
        days = [start.weekday()]
        hhmm = start.strftime("%H:%M")
        conflicts = recurring_recordings.find_rule_conflicts(days, hhmm, duration)
        if conflicts:
            warn_rule_conflict(self, conflicts)
            return
        try:
            recurring_recordings.add_rule(
                info.get("channel_name") or "", info.get("channel_url") or "", days, hhmm, duration,
            )
        except ValueError as exc:
            # Nombre o URL inválidos: no hay regla que crear, pero se avisa.
            warn_rule_invalid(self, str(exc))
