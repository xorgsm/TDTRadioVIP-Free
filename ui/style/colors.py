"""
Paleta de acento y utilidades de color del tema 'Coder By X@R'.

Presets del selector de Configuración, conversiones hex/RGB, mezcla de
colores, contraste WCAG y derivación de los tonos de acento.
"""

import re

from ui import palette

# Nombre visible -> color base, para el selector de Configuración.
# "Dorado" es el que llevaba la app desde siempre; el resto son los mismos
# tonos ya usados en categorías/ecualizador, reutilizados aquí para no
# meter colores nuevos que no encajen con el resto.
ACCENT_PRESETS = {
    "Dorado": "#c9a227",
    "Azul": "#5b9bd5",
    "Violeta": "#a78bfa",
    "Verde": "#65c46a",
    "Coral": "#f472b6",
    "Naranja": "#f0a04b",
}
DEFAULT_ACCENT = palette.ACCENT

LIGHT_THEME_COLORS = {
    palette.BG_ROOT: "#f4f7fb",
    palette.BG_PANEL: "#e7edf5",
    palette.BG_CARD: "#ffffff",
    palette.BG_PANEL_ALT: "#dbe4f0",
    palette.BG_HOVER: "#ced9e8",
    palette.BORDER: "#c5d0de",
    palette.BORDER_STRONG: "#aebdce",
    palette.TEXT_PRIMARY: "#172437",
    palette.TEXT_SECONDARY: "#34465d",
    palette.TEXT_MUTED: "#5f7188",
    palette.TEXT_DIM: "#73849a",
}

_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


def _hex_to_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _rgb_to_hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(c))) for c in rgb)


def _blend(hexcolor: str, target: tuple, ratio: float) -> str:
    """Mezcla lineal hacia 'target' (blanco o negro), en la proporción
    'ratio'. Probé primero QColor.lighter()/darker(): salía demasiado
    saturado (un amarillo chillón en vez del dorado suave de siempre) —
    los tonos originales se eligieron a mano por estética, no con una
    fórmula, así que ninguna fórmula los iba a reproducir exactos. Esta
    mezcla no intenta igualar el dorado (ese se deja intacto, sin tocar);
    solo da tonos razonables y consistentes para el resto de colores."""
    r, g, b = _hex_to_rgb(hexcolor)
    tr, tg, tb = target
    return _rgb_to_hex((r + (tr - r) * ratio, g + (tg - g) * ratio, b + (tb - b) * ratio))


def normalize_accent(value: object) -> str:
    """Devuelve un color #rrggbb seguro o el acento predeterminado."""
    if not isinstance(value, str):
        return DEFAULT_ACCENT
    value = value.strip()
    if not _HEX_RE.fullmatch(value):
        return DEFAULT_ACCENT
    return value.lower()


def _relative_luminance(hexcolor: str) -> float:
    channels = []
    for value in _hex_to_rgb(hexcolor):
        channel = value / 255.0
        channels.append(
            channel / 12.92
            if channel <= 0.04045
            else ((channel + 0.055) / 1.055) ** 2.4
        )
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast_ratio(first: str, second: str) -> float:
    lighter, darker = sorted(
        (_relative_luminance(first), _relative_luminance(second)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)


def accent_shades(accent: object) -> dict[str, str]:
    """
    A partir de un color de acento, calcula los mismos tonos derivados que
    antes estaban fijos al dorado (base, claro, más claro, oscuro) — se
    usan tanto en el CSS como en el código Python que pinta a mano
    (tarjeta "reproduciendo ahora", icono de PiP activo...).
    """
    base = normalize_accent(accent)
    dark_text = palette.BG_ROOT
    light_text = "#ffffff"
    on_accent = max(
        (dark_text, light_text),
        key=lambda text_color: _contrast_ratio(base, text_color),
    )

    return {
        "base": base,
        "light": _blend(base, (255, 255, 255), 0.25),
        "lighter": _blend(base, (255, 255, 255), 0.50),
        "dark": _blend(base, (0, 0, 0), 0.30),
        "hover": _blend(base, (255, 255, 255), 0.14),
        "pressed": _blend(base, (0, 0, 0), 0.18),
        "soft": _blend(base, _hex_to_rgb(palette.BG_CARD), 0.72),
        "on_accent": on_accent,
    }


