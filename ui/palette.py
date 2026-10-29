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
# Escala azul noche: superficies diferenciadas y acentos luminosos.
BG_ROOT = "#0b152b"
BG_PANEL = "#122440"
BG_CARD = "#193354"
BG_PANEL_ALT = "#244267"
BG_HOVER = "#2c4b70"
BORDER = "#31547c"
BORDER_STRONG = "#527aa6"

# ── Texto ────────────────────────────────────────────────────────────────
TEXT_PRIMARY = "#f2efe6"
TEXT_SECONDARY = "#bcc9da"
# Aclarado desde #8fa1b8: pasaba AA (4.5:1+) sobre BG_ROOT/BG_PANEL/BG_CARD
# pero caía a 4.19:1 sobre BG_PANEL_ALT y 3.90:1 sobre BG_HOVER -- los dos
# fondos más claros del stack, donde este tono también se usa como texto
# real (filas con estado hover). Ahora >=4.53:1 sobre los cinco fondos.
TEXT_MUTED = "#c3d2e5"
# Aclarado desde #687c93 (contraste WCAG AA: 3.36:1 sobre BG_PANEL, 2.95:1
# sobre BG_CARD -- por debajo del mínimo de 4.5:1 para texto normal, y se
# usaba como texto real en estados vacíos y metadatos, no como decoración).
# Ahora >=4.58:1 sobre BG_ROOT/BG_PANEL/BG_CARD.
TEXT_DIM = "#b9cce2"

# ── Acento de marca (índigo por defecto) ────────────────────────────────
ACCENT = "#7c6cff"
ACCENT_LIGHT = "#a095ff"
ACCENT_LIGHTER = "#c4bcff"

# ── Semánticos ───────────────────────────────────────────────────────────
# Aclarado desde #ef5350 (contraste WCAG AA: 4.14:1 sobre BG_PANEL, por
# debajo del mínimo de 4.5:1 -- y es justo el color de los mensajes de
# error reales, mediaStatus/now_subtitle/splash/EPG). Ahora >=4.57:1 sobre
# BG_PANEL, BG_ROOT y los fondos de la rejilla EPG.
DANGER = "#ff8589"
SUCCESS = "#4ce3a0"

# ── Acentos secundarios por función ─────────────────────────────────────
# Cada función tiene su propio color para no confundirse visualmente entre
# sí (cast ≠ favorito ≠ grabando ≠ apagado programado).
ACCENT_CAST = "#25f2cf"
ACCENT_SLEEP = "#c0a0ff"
ACCENT_INFO = "#4dccff"
ACCENT_CATEGORY_ORANGE = "#ffae45"

# ── Guía EPG (rejilla de programación) ──────────────────────────────────
# Celda del programa en emisión ahora mismo vs. resto de celdas de la
# rejilla (ui/epg_dialog.py). Distintos de BG_PANEL/TEXT_SECONDARY porque
# necesitan más contraste dentro de una tabla densa.
EPG_NOW_BG = "#262245"
EPG_CELL_BG = "#121419"
EPG_CELL_TEXT = "#c7ced8"
