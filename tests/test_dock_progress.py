"""Lógica pura del dock «Ahora suena» (ui.dock_progress): progreso del
programa en curso y texto de la etiqueta de calidad del canal."""
from datetime import datetime

from core.epg import Programme, _parse_xmltv_time, parse_xmltv_time
from ui.dock_progress import programme_progress, quality_badge


def _prog(start="20261120210000", stop="20261120220000"):
    return Programme(channel_id="la1", title="Telediario 2", start=start, stop=stop)


def test_progress_midway():
    assert programme_progress(_prog(), datetime(2026, 11, 20, 21, 30)) == (0.5, "21:00", "22:00")


def test_progress_none_when_no_programme():
    now = datetime(2026, 11, 20, 21, 30)
    assert programme_progress(None, now) == (0.0, "", "")
    assert programme_progress(_prog(start="basura"), now) == (0.0, "", "")
    assert programme_progress(_prog(stop=""), now) == (0.0, "", "")
    # Un fin que no es posterior al inicio no da una duración válida.
    assert programme_progress(_prog(stop="20261120210000"), now) == (0.0, "", "")


def test_progress_clamped_outside_range():
    assert programme_progress(_prog(), datetime(2026, 11, 20, 20, 0)) == (0.0, "21:00", "22:00")
    assert programme_progress(_prog(), datetime(2026, 11, 20, 23, 0)) == (1.0, "21:00", "22:00")


def test_parse_xmltv_time_is_public_and_keeps_the_private_alias():
    assert parse_xmltv_time is _parse_xmltv_time
    assert parse_xmltv_time("20261120210000") == datetime(2026, 11, 20, 21, 0)


def test_quality_badge_texts():
    assert quality_badge("stable", failed=False) == ("Señal · estable", "stable")
    assert quality_badge("slow", failed=False) == ("Señal · lenta", "slow")
    assert quality_badge("down", failed=False) == ("Sin señal", "down")
    assert quality_badge("restricted", failed=False) == ("Acceso restringido", "down")
    # Sin diagnóstico no se inventa nada: la etiqueta se oculta.
    assert quality_badge(None, failed=False) == ("", "")
    assert quality_badge("desconocido", failed=False) == ("", "")
    # El fallo en vivo manda sobre el último diagnóstico guardado.
    assert quality_badge("stable", failed=True) == ("Sin señal", "down")
