"""Lógica pura del dock «Ahora suena»: progreso del programa en curso y
texto de la etiqueta de calidad del canal. Sin Qt, para probarla aislada;
los widgets están en ui.now_playing_bar_builder y los alimenta
ui.playback_controller.PlaybackController.
"""
from __future__ import annotations

from datetime import datetime

from core.epg import Programme, parse_xmltv_time

_EMPTY = (0.0, "", "")


def programme_progress(current: Programme | None, now: datetime) -> tuple[float, str, str]:
    """``(fracción 0–1, "HH:MM" de inicio, "HH:MM" de fin)`` de ``current``.

    ``(0.0, "", "")`` si no hay programa o sus fechas no son válidas (fin no
    posterior al inicio incluido). Fuera del intervalo se fija en 0.0 o 1.0.
    """
    if current is None:
        return _EMPTY
    start = parse_xmltv_time(current.start)
    stop = parse_xmltv_time(current.stop)
    if start is None or stop is None or stop <= start:
        return _EMPTY
    fraction = (now - start).total_seconds() / (stop - start).total_seconds()
    fraction = min(1.0, max(0.0, fraction))
    return fraction, start.strftime("%H:%M"), stop.strftime("%H:%M")


# Estado de core.stream_health_store -> (texto, estado visual de la etiqueta).
_QUALITY = {
    "stable": ("Señal · estable", "stable"),
    "slow": ("Señal · lenta", "slow"),
    "down": ("Sin señal", "down"),
    "restricted": ("Acceso restringido", "down"),
}


def quality_badge(status: str | None, *, failed: bool) -> tuple[str, str]:
    """Texto y estado de la etiqueta de calidad del dock.

    ``status`` es el último diagnóstico guardado del stream (o ``None`` si
    nunca se ha medido); ``failed`` indica que la reproducción en vivo acaba
    de fallar, y manda sobre el diagnóstico. ``("", "")`` oculta la etiqueta:
    sin datos no se inventa una calidad.
    """
    if failed:
        return _QUALITY["down"]
    return _QUALITY.get(status or "", ("", ""))
