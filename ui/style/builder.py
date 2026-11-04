"""
Composición de la hoja de estilos final.

`build_style` resuelve los tokens de las plantillas QSS con los colores del
tema y del acento elegidos, y añade las reglas de cada sección.
"""

from string import Template

from ui import palette
from ui.style.colors import accent_shades, DEFAULT_ACCENT
from ui.style.qss_base import DARK_STYLE
from ui.style.qss_surfaces import SURFACES_STYLE

BODY_FONT = "'Figtree', 'Segoe UI', sans-serif"
DISPLAY_FONT = "'Bricolage Grotesque', 'Figtree', 'Segoe UI', sans-serif"

# Variante de cada sección -> su color de identidad. Las secciones son las
# de ui.nav_sections, que importa de este paquete: no se puede importar aquí.
SECTION_IDENTS = {
    "home": palette.ACCENT_HOME,
    "tv": palette.tone("ACCENT_INFO", "dark"),
    "radio": palette.tone("ACCENT_CATEGORY_ORANGE", "dark"),
    "favorite": palette.tone("ACCENT_FAVORITE", "dark"),
    "history": palette.ACCENT_HISTORY,
    "download": palette.ACCENT_DOWNLOAD,
}

_SECTION_RULES = Template("""
QToolButton#navButton[uiVariant="$variant"]:hover {
    background-color: $bg_hover;
    color: $text;
}
QToolButton#navButton[uiVariant="$variant"]:checked {
    background-color: $color;
    color: $ink;
}
QToolButton#navButton[uiVariant="$variant"]:checked:focus {
    border: 1px solid $ink;
}
QLabel#sectionTitle[uiVariant="$variant"] { color: $title_color; }
""")


def _ident_stops() -> str:
    """Tramos de color sólidos, sin fundido, de la franja de identidad."""
    colors = list(SECTION_IDENTS.values())
    stops = []
    for index, color in enumerate(colors):
        stops.append(f"stop:{index / len(colors):.4f} {color}")
        stops.append(f"stop:{(index + 1) / len(colors) - 0.0001:.4f} {color}")
    return ", ".join(stops)


def _tokens(shades: dict, theme: str) -> dict[str, str]:
    light = theme == "light"
    return {
        "body_font": BODY_FONT,
        "display_font": DISPLAY_FONT,
        "ident_stops": _ident_stops(),
        "bg_root": palette.tone("BG_ROOT", theme),
        "bg_panel": palette.tone("BG_PANEL", theme),
        "bg_card": palette.tone("BG_CARD", theme),
        "bg_alt": palette.tone("BG_PANEL_ALT", theme),
        "bg_hover": palette.tone("BG_HOVER", theme),
        "border": palette.tone("BORDER", theme),
        "border_strong": palette.tone("BORDER_STRONG", theme),
        "text": palette.tone("TEXT_PRIMARY", theme),
        "text2": palette.tone("TEXT_SECONDARY", theme),
        "muted": palette.tone("TEXT_MUTED", theme),
        "dim": palette.tone("TEXT_DIM", theme),
        "wash": "rgba(26, 21, 38, 12)" if light else "rgba(255, 255, 255, 12)",
        "wash_strong": "rgba(26, 21, 38, 24)" if light else "rgba(255, 255, 255, 24)",
        "video": palette.VIDEO_BLACK,
        "ink": palette.INK,
        "danger": palette.tone("DANGER", theme),
        "success": palette.tone("SUCCESS", theme),
        "home": palette.ACCENT_HOME,
        "tv": palette.tone("ACCENT_INFO", theme),
        "radio": palette.tone("ACCENT_CATEGORY_ORANGE", theme),
        "cast": palette.tone("ACCENT_CAST", theme),
        "sleep": palette.tone("ACCENT_SLEEP", theme),
        "download": palette.ACCENT_DOWNLOAD,
        # Bloques con texto en tinta: mismo tono vivo en ambos temas. Los
        # tokens de arriba se oscurecen en el claro porque son texto y bordes.
        "block_danger": palette.tone("DANGER", "dark"),
        "block_success": palette.tone("SUCCESS", "dark"),
        "block_tv": palette.tone("ACCENT_INFO", "dark"),
        "block_radio": palette.tone("ACCENT_CATEGORY_ORANGE", "dark"),
        "block_cast": palette.tone("ACCENT_CAST", "dark"),
        "block_sleep": palette.tone("ACCENT_SLEEP", "dark"),
        "accent": shades["base"],
        "accent_light": shades["light"],
        "accent_hover": shades["hover"],
        "accent_pressed": shades["pressed"],
        "on_accent": shades["on_accent"],
        "accent_text": shades["text"],
    }


def _section_rules(tokens: dict, theme: str) -> str:
    rules = ""
    for variant, color in SECTION_IDENTS.items():
        rules += _SECTION_RULES.substitute(
            variant=variant,
            color=color,
            ink=tokens["ink"],
            bg_hover=tokens["bg_hover"],
            text=tokens["text"],
            # Los colores de identidad no se leen como texto sobre fondo claro.
            title_color=tokens["text"] if theme == "light" else color,
        )
    return rules


def build_style(accent: object = DEFAULT_ACCENT, theme: str = "dark") -> str:
    """Hoja de estilos de la aplicación para un acento y un tema."""
    tokens = _tokens(accent_shades(accent, theme), theme)
    base = Template(DARK_STYLE).substitute(tokens)
    surfaces = Template(SURFACES_STYLE).substitute(tokens)
    return base + surfaces + _section_rules(tokens, theme)
