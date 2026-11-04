"""
Paleta de acento y utilidades de color del tema 'Coder By X@R'.

Presets del selector de Configuración, conversiones hex/RGB, mezcla de
colores, contraste WCAG y derivación de los tonos de acento.
"""

import re

from ui import palette

# Nombre visible -> color base, para el selector de Configuración.
ACCENT_PRESETS = {
    "Magenta": "#ff2d78",
    "Azul": "#4d94ff",
    "Turquesa": "#19e3c2",
    "Verde": "#3de68f",
    "Lima": "#c8f031",
    "Amarillo": "#ffd02e",
    "Naranja": "#ff8a1f",
    "Violeta": "#b794ff",
}
DEFAULT_ACCENT = palette.ACCENT

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


def hex_to_rgba(hexcolor: str, alpha: int) -> str:
    """'#rrggbb' -> 'rgba(r, g, b, alpha)' (alpha 0-255, como pide QSS)."""
    r, g, b = _hex_to_rgb(hexcolor)
    return f"rgba({r}, {g}, {b}, {alpha})"


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


def readable_on_surface(color: str) -> str:
    """Un color vivo, oscurecido si hace falta, para un icono sobre el panel
    del tema activo (WCAG pide 3:1 a los elementos gráficos)."""
    while _contrast_ratio(color, palette.BG_PANEL) < 3.0:
        color = _blend(color, (0, 0, 0), 0.10)
    return color


def accent_shades(accent: object, theme: str = "dark") -> dict[str, str]:
    """
    A partir de un color de acento, calcula sus tonos derivados -- se usan
    tanto en el QSS como en el código Python que pinta a mano (tarjeta
    "reproduciendo ahora", icono de PiP activo...).
    """
    base = normalize_accent(accent)
    on_accent = max(
        (palette.INK, "#ffffff"),
        key=lambda text_color: _contrast_ratio(base, text_color),
    )
    surface = palette.tone("BG_CARD", theme)
    dark = _blend(base, (0, 0, 0), 0.30)
    # El acento usado como texto: en tema claro se oscurece hasta leerse,
    # porque un amarillo o un lima puros no contrastan sobre fondo claro.
    text = base
    if theme == "light":
        text = dark
        while _contrast_ratio(text, surface) < 4.5:
            text = _blend(text, (0, 0, 0), 0.10)

    return {
        "base": base,
        "light": _blend(base, (255, 255, 255), 0.25),
        "lighter": _blend(base, (255, 255, 255), 0.50),
        "dark": dark,
        "hover": _blend(base, (255, 255, 255), 0.14),
        "pressed": _blend(base, (0, 0, 0), 0.18),
        "soft": _blend(base, _hex_to_rgb(surface), 0.72),
        "on_accent": on_accent,
        "text": text,
    }
