"""
Paleta de colores compartida por la interfaz — Coder By X@R.

Antes estos valores vivían repetidos como literales sueltos en varios
archivos de ui/ (main_window.py, widgets.py, epg_dialog.py, cast_dialog.py,
splash.py, download_panel.py, torrent_panel.py...). Cambiar un tono
obligaba a buscar y tocar cada coincidencia de texto en vez de un solo
sitio; con constantes con nombre, se cambia aquí y se propaga sola.

Los tonos dorados que sí varían con el "color de acento" que el usuario
elige en Configuración > Apariencia siguen resolviéndose en tiempo real vía
ui.style.accent_shades() — este módulo solo cubre los tonos fijos del tema
oscuro (fondos, texto, bordes) y los acentos secundarios por función
(cast, sleep, info...) que no cambian con el acento del usuario.

Uso en código Python (QColor, argumentos de icon_*(), texto de
setStyleSheet() de una sola línea):

    from ui import palette
    QColor(palette.ACCENT)
    icon_tv(palette.ACCENT_INFO)

Los estilos estructurales compartidos se construyen en ui.style. Solo se
mantienen junto al widget los estilos que dependen de datos dinámicos o de
un estado local que no forma parte del sistema visual común.
"""

# ── Fondos ───────────────────────────────────────────────────────────────
# Escala navy del rediseño 7.5.8 (mockup ui-diseno/panel principal.pen):
# base #0D1B2A y paneles #1B2A41, con los pasos superiores derivados en el
# mismo matiz para conservar la jerarquía card < alt < hover.
BG_ROOT = "#0d1b2a"
BG_PANEL = "#1b2a41"
BG_CARD = "#223350"
BG_PANEL_ALT = "#283c5e"
BG_HOVER = "#2f466d"
BORDER = "#2a3b55"
BORDER_STRONG = "#3d5578"

# ── Texto ────────────────────────────────────────────────────────────────
TEXT_PRIMARY = "#f2efe6"
TEXT_SECONDARY = "#bcc9da"
# Aclarado desde #8fa1b8: pasaba AA (4.5:1+) sobre BG_ROOT/BG_PANEL/BG_CARD
# pero caía a 4.19:1 sobre BG_PANEL_ALT y 3.90:1 sobre BG_HOVER -- los dos
# fondos más claros del stack, donde este tono también se usa como texto
# real (filas con estado hover). Ahora >=4.53:1 sobre los cinco fondos.
TEXT_MUTED = "#a6b5c7"
# Aclarado desde #687c93 (contraste WCAG AA: 3.36:1 sobre BG_PANEL, 2.95:1
# sobre BG_CARD -- por debajo del mínimo de 4.5:1 para texto normal, y se
# usaba como texto real en estados vacíos y metadatos, no como decoración).
# Ahora >=4.58:1 sobre BG_ROOT/BG_PANEL/BG_CARD.
TEXT_DIM = "#8e9daf"

# ── Acento de marca (dorado por defecto) ────────────────────────────────
ACCENT = "#c9a227"
ACCENT_LIGHT = "#e8c360"
ACCENT_LIGHTER = "#f4d476"

# ── Semánticos ───────────────────────────────────────────────────────────
# Aclarado desde #ef5350 (contraste WCAG AA: 4.14:1 sobre BG_PANEL, por
# debajo del mínimo de 4.5:1 -- y es justo el color de los mensajes de
# error reales, mediaStatus/now_subtitle/splash/EPG). Ahora >=4.57:1 sobre
# BG_PANEL, BG_ROOT y los fondos de la rejilla EPG.
DANGER = "#f26f6c"
SUCCESS = "#42c985"

# ── Acentos secundarios por función ─────────────────────────────────────
# Cada función tiene su propio color para no confundirse visualmente entre
# sí (cast ≠ favorito ≠ grabando ≠ apagado programado).
ACCENT_CAST = "#31c7b2"
ACCENT_SLEEP = "#9b7bea"
ACCENT_INFO = "#55a7e8"
ACCENT_CATEGORY_ORANGE = "#f39a55"

# ── Guía EPG (rejilla de programación) ──────────────────────────────────
# Celda del programa en emisión ahora mismo vs. resto de celdas de la
# rejilla (ui/epg_dialog.py). Distintos de BG_PANEL/TEXT_SECONDARY porque
# necesitan más contraste dentro de una tabla densa.
EPG_NOW_BG = "#3a2e14"
EPG_CELL_BG = "#16223a"
EPG_CELL_TEXT = "#c7ced8"
