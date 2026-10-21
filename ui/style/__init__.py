"""
Tema oscuro 'Coder By X@R' v2 (navy + dorado) para TDT & Radio VIP.

Este paquete sustituye al antiguo módulo único ui/style.py (1293 líneas,
por encima del límite de 800 del proyecto), repartido en: `colors`
(paleta y utilidades de color), `qss_base` (plantilla QSS) y `builder`
(composición final). Los imports existentes `from ui.style import X`
siguen funcionando gracias a estas reexportaciones.
"""

from ui.style.builder import build_style
from ui.style.colors import (
    ACCENT_PRESETS,
    DEFAULT_ACCENT,
    LIGHT_THEME_COLORS,
    accent_shades,
    normalize_accent,
)
from ui.style.qss_base import DARK_STYLE

__all__ = [
    "ACCENT_PRESETS",
    "DARK_STYLE",
    "DEFAULT_ACCENT",
    "LIGHT_THEME_COLORS",
    "accent_shades",
    "build_style",
    "normalize_accent",
]
