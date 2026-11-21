"""
Paleta de colores compartida por la interfaz — Coder By X@R.

Antes estos valores vivían repetidos como literales sueltos en varios
archivos de ui/ (main_window.py, widgets.py, epg_dialog.py, cast_dialog.py,
splash.py, download_panel.py, torrent_panel.py...). Cambiar un tono
obligaba a buscar y tocar cada coincidencia de texto en vez de un solo
sitio; con constantes con nombre, se cambia aquí y se propaga sola.

Los tonos que sí varían con el "color de acento" que el usuario
elige en Configuración > Apariencia siguen resolviéndose en tiempo real vía
ui.style.accent_shades() — este módulo solo cubre los tonos fijos del tema
oscuro (fondos, texto, bordes) y los acentos secundarios por función
(cast, sleep, info...) que no cambian con el acento del usuario.

Uso en código Python (QColor, argumentos de icon_*(), texto de
setStyleSheet() de una sola línea):

    from ui import palette
    QColor(palette.ACCENT)
    icon_tv(palette.ACCENT_TV)

Los estilos estructurales compartidos se construyen en ui.style. Solo se
mantienen junto al widget los estilos que dependen de datos dinámicos o de
un estado local que no forma parte del sistema visual común.
"""

# ── Fondos ───────────────────────────────────────────────────────────────
# Tinta de plató: negro cálido, neutro para que los bloques de color de
# cada sección sean lo único saturado de la pantalla.
BG_ROOT = "#12110e"
BG_PANEL = "#1a1814"
BG_CARD = "#23211b"
BG_PANEL_ALT = "#2d2a22"
BG_HOVER = "#38342a"
BORDER = "#3d3930"
BORDER_STRONG = "#6b6454"
# Marco del vídeo: nunca tintado, el color de la imagen manda.
VIDEO_BLACK = "#08060c"
# Texto e iconos sobre un bloque de color vivo. Es fijo en ambos temas (a
# diferencia de BG_ROOT, que el tema claro sustituye por un tono claro).
INK = "#12110e"
# Texto e iconos sobre el negro del vídeo, también fijos en ambos temas.
ON_VIDEO = "#faf7ff"

# ── Texto ────────────────────────────────────────────────────────────────
# Todos cumplen WCAG AA (4.5:1) sobre los cinco fondos, BG_HOVER incluido:
# lo vigila tests/test_palette_contrast.py.
TEXT_PRIMARY = "#f3edde"
TEXT_SECONDARY = "#d9d2bf"
TEXT_MUTED = "#cdc6b0"
TEXT_DIM = "#bfb8a2"

# ── Acento de marca (magenta por defecto) ────────────────────────────────
ACCENT = "#ff2d78"
ACCENT_LIGHT = "#ff6299"
ACCENT_LIGHTER = "#ff96bb"

# ── Semánticos ───────────────────────────────────────────────────────────
DANGER = "#ff6b6b"
SUCCESS = "#3de68f"
WARNING = "#ffc53d"

# ── Color de identidad de cada sección ──────────────────────────────────
# Fijos, no siguen al acento del usuario: cada sección se reconoce por su
# bloque de color, como una cadena por su cabecera.
ACCENT_HOME = "#ff9f1c"
ACCENT_TV = "#19b5f0"  # Televisión
ACCENT_RADIO = "#f0338f"  # Radio y podcasts
ACCENT_GUIDE = "#ffd92e"  # Guía de programación
# Favoritos, Historial y «Mi lista»: el crema del texto, sin color propio.
ACCENT_LIST = "#f3edde"
ACCENT_RECORD = "#f2452f"
ACCENT_DOWNLOAD = "#2fbf71"
ACCENT_TOOLS = "#8a7bf5"

# ── Acentos secundarios por función ─────────────────────────────────────
# Cada función tiene su propio color para no confundirse visualmente entre
# sí (cast ≠ favorito ≠ grabando ≠ apagado programado).
ACCENT_CAST = "#19e3c2"
ACCENT_SLEEP = "#b794ff"

# ── Guía EPG (rejilla de programación) ──────────────────────────────────
# Celda del programa en emisión ahora mismo vs. resto de celdas de la
# rejilla (ui/epg_dialog.py). Distintos de BG_PANEL/TEXT_SECONDARY porque
# necesitan más contraste dentro de una tabla densa.
# Negro cálido como el resto; la celda en emisión, tintada de magenta sobre
# BG_CARD (como el programa en curso de la maqueta v10).
EPG_NOW_BG = "#502535"
EPG_CELL_BG = "#1a1814"
EPG_CELL_TEXT = "#d9d2bf"

# ── Tema ─────────────────────────────────────────────────────────────────
# Tono de cada color en el tema claro. Los que no aparecen aquí son iguales
# en ambos temas. Para cambiar de tema se reescriben estas constantes, así
# que hay que leerlas siempre como palette.X, nunca copiarlas al importar.
_LIGHT = {
    "BG_ROOT": "#f7f3e8",
    "BG_PANEL": "#ede8da",
    "BG_CARD": "#fffdf6",
    "BG_PANEL_ALT": "#e2dccb",
    "BG_HOVER": "#d6cfbb",
    "BORDER": "#cfc7b2",
    "BORDER_STRONG": "#a39a82",
    "TEXT_PRIMARY": "#1c1a14",
    "TEXT_SECONDARY": "#3d392d",
    "TEXT_MUTED": "#4d4838",
    "TEXT_DIM": "#585340",
    "ACCENT_LIGHT": "#d01a5e",
    "ACCENT_LIGHTER": "#b3104f",
    "DANGER": "#c81e3a",
    "SUCCESS": "#0d7a45",
    "WARNING": "#8a5f00",
    "ACCENT_HOME": "#995200",
    "ACCENT_TV": "#0a6e99",
    "ACCENT_RADIO": "#b8105f",
    "ACCENT_GUIDE": "#756000",
    "ACCENT_LIST": "#4d4838",
    "ACCENT_RECORD": "#c42a14",
    "ACCENT_DOWNLOAD": "#16783f",
    "ACCENT_TOOLS": "#5b4bd0",
    "ACCENT_CAST": "#0a7d6b",
    "ACCENT_SLEEP": "#6a3fd0",
    "EPG_NOW_BG": "#ffd6e5",
    "EPG_CELL_BG": "#fffdf6",
    "EPG_CELL_TEXT": "#1c1a14",
}
_DARK = {name: globals()[name] for name in _LIGHT}


def tone(name: str, theme: str) -> str:
    """El valor de una constante de este módulo en el tema pedido."""
    return _LIGHT[name] if theme == "light" else _DARK[name]


def apply_theme(theme: str) -> None:
    """Hace de `theme` el tema activo para todo lo que lea palette.X."""
    globals().update({name: tone(name, theme) for name in _LIGHT})
