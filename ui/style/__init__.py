"""
Tema "Continuidad" de TDT & Radio VIP: tinta de plató y un color de
identidad por sección.

Paquete repartido en: `colors` (acentos y utilidades de color), `qss_base`
y `qss_surfaces` (plantillas QSS con tokens) y `builder` (composición
final). Los imports existentes `from ui.style import X`
siguen funcionando gracias a estas reexportaciones.
"""

from ui.style.builder import build_style
from ui.style.colors import (
    ACCENT_PRESETS,
    DEFAULT_ACCENT,
    accent_shades,
    normalize_accent,
)
from ui.style.qss_base import DARK_STYLE

__all__ = [
    "ACCENT_PRESETS",
    "DARK_STYLE",
    "DEFAULT_ACCENT",
    "accent_shades",
    "build_style",
    "normalize_accent",
]
