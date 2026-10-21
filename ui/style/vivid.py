"""
Tipografía y color "vivo" del tema.

Bloque QSS que `build_style` añade al final: títulos, menús y ventanas en
serif (Playfair Display), botones de opciones más grandes y, solo en el
tema oscuro, fondos con degradados tintados que siguen el color de acento
y el color propio de cada sección.
"""

from ui import palette

DISPLAY_FONT = "'Playfair Display', 'Georgia', serif"

# Tinte violeta del extremo oscuro de los degradados (el azul noche base
# vira suavemente hacia él).
_DEEP_BLUE = "#0b1d33"
_DEEP_NAVY = "#0a1628"
_DEEP_VIOLET = "#120f2a"
_PLAYER_BLUE = "#16315a"
_PLAYER_VIOLET = "#1b1240"
_SECTION_GLOW_ALPHA = 120
_SECTION_HOVER_ALPHA = 55

_TITLE_SELECTORS = (
    "QLabel#sectionTitle",
    "QLabel#titleBrand",
    "QLabel#dialogTitle",
    "QDialog QLabel#dialogTitle",
    "QLabel#homeGreeting",
    "QDialog QLabel#titulo",
)


def hex_to_rgba(hexcolor: str, alpha: int) -> str:
    """'#rrggbb' -> 'rgba(r, g, b, alpha)' (alpha 0-255, como pide QSS)."""
    value = hexcolor.lstrip("#")
    r, g, b = (int(value[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {alpha})"


def _titles_block() -> str:
    selectors = ",\n".join(_TITLE_SELECTORS)
    return f"""
{selectors} {{
    font-family: {DISPLAY_FONT};
    font-weight: 700;
}}
"""


# Menús desplegables y ventanas que se abren: letra serif, algo más grande.
_MENU_FONT_SELECTORS = (
    "QMenu",
    "QMenu::item",
    "QDialog",
    "QDialog QLabel",
    "QDialog QPushButton",
    "QDialog QCheckBox",
    "QDialog QRadioButton",
    "QDialog QComboBox",
    "QDialog QGroupBox",
    "QDialog QTabBar::tab",
    "QMessageBox QLabel",
    "QMessageBox QPushButton",
)

# Botones del reproductor con tamaño fijo en QSS (min == max).
_CONTROL_BUTTONS = ("ctrlButton", "castButton", "sleepButton", "muteButton", "recordButton")
_CONTROL_SIZE_PX = 34
_PLAY_SIZE_PX = 46


def _menus_font_block() -> str:
    selectors = ",\n".join(_MENU_FONT_SELECTORS)
    return f"""
{selectors} {{
    font-family: {DISPLAY_FONT};
    font-size: 11pt;
    font-weight: 600;
}}
QMenu::item {{
    padding: 12px 20px;
}}
"""


def _bigger_buttons_block() -> str:
    controls = ",\n".join(f"QPushButton#{name}" for name in _CONTROL_BUTTONS)
    radius = _CONTROL_SIZE_PX // 2 - 1
    play_radius = _PLAY_SIZE_PX // 2
    return f"""
QPushButton {{
    padding: 10px 20px;
    min-height: 22px;
    font-size: 11pt;
    font-weight: 600;
    border-radius: 9px;
}}
{controls} {{
    min-width: {_CONTROL_SIZE_PX}px;
    max-width: {_CONTROL_SIZE_PX}px;
    min-height: {_CONTROL_SIZE_PX}px;
    max-height: {_CONTROL_SIZE_PX}px;
    border-radius: {radius}px;
    padding: 0;
}}
QPushButton#playCircle {{
    min-width: {_PLAY_SIZE_PX}px;
    max-width: {_PLAY_SIZE_PX}px;
    min-height: {_PLAY_SIZE_PX}px;
    max-height: {_PLAY_SIZE_PX}px;
    border-radius: {play_radius}px;
    padding: 0;
}}
QToolButton#navButton {{
    font-size: 11pt;
    font-weight: 700;
    padding: 11px 16px;
    min-height: 26px;
}}
"""


def _gradients_block(shades: dict, section_colors: dict) -> str:
    block = f"""
QPushButton[uiVariant="primary"] {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {shades['base']}, stop:1 {shades['lighter']});
    border: 1px solid {shades['hover']};
}}
QPushButton:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {shades['soft']}, stop:1 {palette.BG_PANEL_ALT});
    border: 1px solid {shades['base']};
}}
QPushButton#ctrlButton:checked {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {shades['base']}, stop:1 {shades['lighter']});
}}
QMenu::item:selected {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {shades['base']}, stop:1 {shades['lighter']});
}}
QWidget#appSurface {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {_DEEP_BLUE}, stop:0.6 {_DEEP_NAVY}, stop:1 {_DEEP_VIOLET});
}}
QWidget#navTopBar {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {shades['soft']}, stop:0.5 {_DEEP_NAVY}, stop:1 {_DEEP_VIOLET});
    border-bottom: 1px solid {shades['dark']};
}}
QFrame#playerFrame {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {_PLAYER_BLUE}, stop:1 {_PLAYER_VIOLET});
    border: 1px solid {palette.BORDER_STRONG};
    border-radius: 20px;
}}
QFrame#nowPlayingBar {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {palette.BG_PANEL}, stop:1 {shades['soft']});
    border: 1px solid {palette.BORDER_STRONG};
    border-radius: 18px;
}}
QSlider#volumeSlider::sub-page:horizontal {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {shades['dark']}, stop:1 {shades['lighter']});
    border-radius: 2px;
}}
"""
    for variant, color in section_colors.items():
        block += f"""QToolButton#navButton[uiVariant="{variant}"]:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {hex_to_rgba(color, _SECTION_HOVER_ALPHA)}, stop:1 transparent);
    color: {palette.TEXT_PRIMARY};
}}
QToolButton#navButton[uiVariant="{variant}"]:checked {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {hex_to_rgba(color, _SECTION_GLOW_ALPHA)}, stop:1 {palette.BG_PANEL_ALT});
    color: {palette.TEXT_PRIMARY};
    border-left: 3px solid {color};
}}
"""
    return block


def vivid_block(shades: dict, theme: str, section_colors: dict) -> str:
    """QSS de tipografía, tamaño de botones y, en tema oscuro, degradados."""
    block = _titles_block() + _menus_font_block() + _bigger_buttons_block()
    if theme != "light":
        block += _gradients_block(shades, section_colors)
    return block
