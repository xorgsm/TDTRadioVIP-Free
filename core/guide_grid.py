"""
Maquetación de la parrilla de la Guía: lógica pura, sin Qt.

Convierte la guía EPG (``core.epg.fetch_epg``, indexada por
:func:`core.epg.channel_key`) en filas y celdas posicionadas como fracción
0–1 de una ventana horaria, para que la vista solo tenga que multiplicar por
su ancho en píxeles.

Decisiones de borde (cubiertas por ``tests/test_guide_grid.py``):

- Horas: ``parse_xmltv_time`` devuelve datetimes naive en hora local del
  sistema, así que todo se compara en ese mismo marco. ``window_start`` y
  ``now`` naive se toman como hora local; si llegan con zona horaria se pasan
  a hora local naive igual que hace ``parse_xmltv_time``.
- Una fila por canal con ``tvg_id`` usable: un canal sin ``tvg_id`` (o cuya
  :func:`channel_key` queda vacía, p. ej. ``"@HD"``) no puede cruzar con
  ninguna guía y se omite. Se respeta el orden y las repeticiones de
  ``channels`` tal cual llegan.
- Canal con ``tvg_id`` pero sin programas en la ventana → fila con
  ``cells=[]`` (la vista pinta «sin guía» en vez de saltarse el canal).
- Se descartan programas sin fechas válidas, con ``stop <= start`` o que no
  se solapan con la ventana (tocar justo el borde no cuenta: ancho 0).
- Las celdas se recortan a ``[window_start, window_start + hours]``, pero
  ``start``/``stop`` guardan las cadenas XMLTV originales: son la clave de
  avisos y grabaciones programadas.
- ``hours <= 0``, no finito o tan grande que la ventana no cabe en un
  datetime → filas sin celdas, sin excepción: una ventana vacía no tiene
  nada que pintar.
- Límite conocido: el marco es hora local naive (contrato de
  ``parse_xmltv_time``, compartido con «ahora/siguiente», avisos y
  grabaciones), así que la hora repetida del cambio horario de otoño no se
  distingue. Un programa de 02:30+0200 a 02:30+0100 se descarta por
  ``stop <= start``. Arreglarlo exige una línea temporal aware en todo el
  código EPG, no solo aquí.
- ``is_now`` usa el intervalo semiabierto ``start <= now < stop`` con las
  horas reales (no las recortadas), para que en el instante del cambio solo
  quede marcado el programa que empieza.
"""
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

from core.epg import Programme, channel_key, parse_xmltv_time


@dataclass
class GuideCell:
    title: str
    start: str
    stop: str
    left: float
    width: float
    is_now: bool
    tvg_id: str


@dataclass
class GuideRow:
    tvg_id: str
    channel_name: str
    cells: List[GuideCell] = field(default_factory=list)


def _local_naive(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value.astimezone().replace(tzinfo=None)
    return value


def _programme_times(programme: Programme) -> Tuple[Optional[datetime], Optional[datetime]]:
    # Las guías de fetch_epg ya traen las fechas preparadas (_prepare_guide);
    # solo se parsean las construidas a mano.
    if hasattr(programme, "_start_dt"):
        return programme._start_dt, getattr(programme, "_stop_dt", None)
    return parse_xmltv_time(programme.start), parse_xmltv_time(programme.stop)


def _cells_for(
    programmes: Sequence[Programme],
    tvg_id: str,
    window_start: datetime,
    window_end: datetime,
    now: datetime,
) -> List[GuideCell]:
    total = (window_end - window_start).total_seconds()
    placed = []
    for programme in programmes:
        start, stop = _programme_times(programme)
        if start is None or stop is None or stop <= start:
            continue
        clip_start = max(start, window_start)
        clip_stop = min(stop, window_end)
        if clip_stop <= clip_start:
            continue
        left = (clip_start - window_start).total_seconds() / total
        width = (clip_stop - clip_start).total_seconds() / total
        cell = GuideCell(
            title=programme.title or "",
            start=programme.start,
            stop=programme.stop,
            left=left,
            width=width,
            is_now=start <= now < stop,
            tvg_id=tvg_id,
        )
        placed.append((start, cell))
    placed.sort(key=lambda item: item[0])
    return [cell for _, cell in placed]


def build_rows(
    guide: Dict[str, List[Programme]],
    channels: Sequence,
    window_start: datetime,
    hours: float,
    now: datetime,
) -> List[GuideRow]:
    """Filas de la parrilla para ``channels`` en la ventana
    ``[window_start, window_start + hours]``. Ver el docstring del módulo."""
    window_start = _local_naive(window_start)
    now = _local_naive(now)
    usable_window = isinstance(hours, (int, float)) and math.isfinite(hours) and hours > 0
    window_end = window_start
    if usable_window:
        try:
            window_end = window_start + timedelta(hours=hours)
        except OverflowError:
            # Duración o final de ventana fuera del rango de datetime.
            usable_window = False

    rows: List[GuideRow] = []
    for channel in channels:
        tvg_id = getattr(channel, "tvg_id", "") or ""
        key = channel_key(tvg_id)
        if not key:
            continue
        cells = (
            _cells_for(guide.get(key, []), tvg_id, window_start, window_end, now)
            if usable_window else []
        )
        rows.append(GuideRow(tvg_id=tvg_id, channel_name=getattr(channel, "name", "") or "", cells=cells))
    return rows
