"""
Tema oscuro 'Coder By X@R' v2 (navy + dorado) para TDT & Radio VIP.
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


def build_style(accent: object = DEFAULT_ACCENT, theme: str = "dark") -> str:
    """
    Construye el tema oscuro moderno con los tonos derivados del acento
    elegido y selecciona automáticamente texto legible sobre ese color.
    """
    shades = accent_shades(accent)
    style = DARK_STYLE
    fixed_tokens = {
        "#0a0a0a": palette.BG_ROOT,
        "#060606": palette.BG_ROOT,
        "#0d0d0d": palette.BG_ROOT,
        "#121212": palette.BG_PANEL,
        "#101010": palette.BG_PANEL,
        "#161616": palette.BG_CARD,
        "#181818": palette.BG_CARD,
        "#1a1a1a": palette.BG_PANEL_ALT,
        "#1c1c1c": palette.BG_PANEL_ALT,
        "#232323": palette.BG_HOVER,
        "#242424": palette.BG_HOVER,
        "#2a2a2a": palette.BORDER,
        "#2e2e2e": palette.BG_PANEL_ALT,
        "#333333": palette.BORDER_STRONG,
        "#444444": palette.TEXT_DIM,
        "#e6edf3": palette.TEXT_PRIMARY,
        "#b9c2ce": palette.TEXT_SECONDARY,
        "#8b949e": palette.TEXT_MUTED,
        "#6e7787": palette.TEXT_DIM,
        "#da3633": palette.DANGER,
        "#3fb950": palette.SUCCESS,
        "#8b7ae0": palette.ACCENT_SLEEP,
        "#5b9bd5": palette.ACCENT_INFO,
    }
    for old, new in fixed_tokens.items():
        style = style.replace(old, new)

    for old, new in {
        "#c9a227": shades["base"],
        "#e0bb4a": shades["light"],
        "#e8c360": shades["lighter"],
        "#f0cd6e": shades["lighter"],
        "#f4d476": shades["lighter"],
        "#b3891c": shades["dark"],
    }.items():
        style = style.replace(old, new)

    style += f"""
QPushButton[uiVariant="primary"] {{
    background-color: {shades['base']};
    color: {shades['on_accent']};
    border: 1px solid {shades['hover']};
    border-radius: 10px;
}}
QPushButton[uiVariant="primary"]:hover {{ background-color: {shades['hover']}; }}
QPushButton[uiVariant="primary"]:pressed {{ background-color: {shades['pressed']}; }}
QPushButton[uiVariant="danger"] {{ background-color: {palette.DANGER}; color: #ffffff; }}
QPushButton[uiVariant="cast"], QLabel[uiVariant="cast"] {{ color: {palette.ACCENT_CAST}; }}
QPushButton[uiVariant="sleep"], QLabel[uiVariant="sleep"] {{ color: {palette.ACCENT_SLEEP}; }}
QPushButton[uiVariant="info"], QLabel[uiVariant="info"],
QPushButton[uiVariant="tv"], QLabel[uiVariant="tv"] {{ color: {palette.ACCENT_INFO}; }}
QPushButton[uiVariant="radio"], QLabel[uiVariant="radio"],
QPushButton[uiVariant="podcast"], QLabel[uiVariant="podcast"] {{ color: {palette.ACCENT_CATEGORY_ORANGE}; }}
QWidget[uiState="error"] {{ border: 1px solid {palette.DANGER}; }}
QWidget[uiState="loading"] {{ color: {palette.ACCENT_INFO}; }}
QWidget[uiState="empty"] {{ color: {palette.TEXT_MUTED}; }}
QFrame#homeHero {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #19314a, stop:0.55 {palette.BG_PANEL_ALT}, stop:1 {palette.BG_PANEL});
    border: 1px solid {palette.BORDER_STRONG};
    border-radius: 20px;
}}
QFrame#dialogPanel[uiSurface="homeSectionCard"] {{
    background-color: {palette.BG_CARD};
    border: 1px solid {palette.BORDER};
    border-radius: 14px;
}}
QPushButton#homeQuickButton[uiVariant="tv"] {{
    background-color: {palette.ACCENT_INFO};
    color: {palette.BG_ROOT};
    border: 1px solid {palette.ACCENT_INFO};
}}
QPushButton#homeQuickButtonAlt[uiVariant="radio"] {{
    background-color: {shades['soft']};
    color: {palette.ACCENT_CATEGORY_ORANGE};
    border: 1px solid {palette.ACCENT_CATEGORY_ORANGE};
}}
QLabel#sectionTitle[uiVariant="success"] {{ color: {ACCENT_PRESETS['Verde']}; }}
QLabel#sectionTitle[uiVariant="tv"] {{ color: {palette.ACCENT_INFO}; }}
QLabel#sectionTitle[uiVariant="radio"] {{ color: {palette.ACCENT_CATEGORY_ORANGE}; }}
QLabel#sectionTitle[uiVariant="primary"] {{ color: {shades['base']}; }}
QLabel#sectionTitle[uiVariant="sleep"] {{ color: {ACCENT_PRESETS['Violeta']}; }}
QLabel#sectionTitle[uiVariant="cast"] {{ color: {palette.ACCENT_CAST}; }}
QLabel#sectionTitle[uiVariant="download"] {{ color: {ACCENT_PRESETS['Coral']}; }}
QLabel#liveBadge {{
    background-color: transparent;
    color: {shades['base']};
    border: 1px solid {shades['base']};
    border-radius: 14px;
    padding: 5px 11px;
    font-size: 8.5pt;
    font-weight: 800;
    letter-spacing: 1px;
}}
QLabel#playerContextLabel {{
    color: {palette.TEXT_MUTED};
    font-size: 8pt;
    font-weight: 800;
    letter-spacing: 1.6px;
}}
QWidget#playerPanel {{
    background-color: {palette.BG_ROOT};
}}
QFrame#playerFrame {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #14283d, stop:1 #091827);
    border: 1px solid {palette.BORDER_STRONG};
    border-radius: 20px;
}}
QFrame#nowPlayingBar {{
    background-color: {palette.BG_PANEL};
    border: 1px solid {palette.BORDER_STRONG};
    border-radius: 18px;
}}
QWidget#navRail {{
    background-color: {palette.BG_PANEL};
    border-right: 1px solid {palette.BORDER};
}}
QToolButton#navButton {{
    border-radius: 10px;
    margin: 2px 0;
    padding: 8px 10px;
}}
QToolButton#navButton:hover {{
    background-color: {palette.BG_PANEL_ALT};
}}
QLineEdit#searchBox, QComboBox#groupFilter {{
    background-color: {palette.BG_PANEL};
    border: 1px solid {palette.BORDER};
}}
QLineEdit#searchBox:focus {{
    border: 1px solid {shades['base']};
    background-color: {palette.BG_CARD};
}}
QToolButton#catalogViewToggle {{
    background-color: {palette.BG_PANEL};
    color: {palette.TEXT_DIM};
    border: 1px solid {palette.BORDER};
    border-radius: 9px;
    padding: 3px;
}}
QToolButton#catalogViewToggle:hover {{
    background-color: {palette.BG_HOVER};
    border-color: {palette.BORDER_STRONG};
}}
QToolButton#catalogViewToggle:checked {{
    background-color: {shades['base']};
    border-color: {shades['hover']};
}}
QSlider#volumeSlider::groove:horizontal {{
    background: {palette.BG_ROOT};
    height: 5px;
    border-radius: 2px;
}}
QSlider#volumeSlider::sub-page:horizontal {{
    background: {shades['base']};
    border-radius: 2px;
}}
QSlider#volumeSlider::handle:horizontal {{
    background: {shades['base']};
    border: 2px solid {palette.BG_PANEL};
    width: 13px;
    margin: -5px 0;
    border-radius: 7px;
}}
QPushButton#castButton[uiVariant="cast"]:checked {{
    background-color: {palette.ACCENT_CAST};
    color: {palette.BG_ROOT};
}}
QPushButton#sleepButton[uiVariant="sleep"]:checked {{
    background-color: {palette.ACCENT_SLEEP};
    color: {palette.BG_ROOT};
}}
QPushButton#muteButton[uiVariant="info"]:checked {{
    background-color: {palette.ACCENT_INFO};
    color: {palette.BG_ROOT};
}}
QFrame#carouselCard {{
    background-color: {palette.BG_CARD};
    border: 1px solid {palette.BORDER};
    border-radius: 14px;
}}
QFrame#carouselCard:hover {{
    background-color: {palette.BG_HOVER};
    border-color: {palette.BORDER_STRONG};
}}
QFrame#carouselCard[uiVariant="tv"] {{
    background-color: {accent_shades(palette.ACCENT_INFO)['soft']};
    border-bottom: 3px solid {palette.ACCENT_INFO};
}}
QFrame#carouselCard[uiVariant="radio"] {{
    background-color: {accent_shades(palette.ACCENT_CATEGORY_ORANGE)['soft']};
    border-bottom: 3px solid {palette.ACCENT_CATEGORY_ORANGE};
}}
QFrame#carouselCard[uiVariant="tv"]:hover {{
    background-color: {palette.BG_HOVER};
    border-color: {palette.BORDER_STRONG};
}}
QFrame#carouselCard[uiVariant="radio"]:hover {{
    background-color: {palette.BG_HOVER};
    border-color: {palette.BORDER_STRONG};
}}
QFrame#carouselCard QLabel {{ background: transparent; }}
QLabel#carouselLogo {{ background-color: {palette.BG_PANEL}; border-radius: 10px; }}
QLabel#carouselName {{ color: {palette.TEXT_PRIMARY}; font-size: 9pt; font-weight: 650; }}
QLabel#carouselMeta {{ color: {palette.TEXT_MUTED}; font-size: 7.5pt; }}
QLabel#carouselEmpty {{ color: {palette.TEXT_DIM}; font-size: 8.5pt; padding: 8px; }}
QWidget#librarySidebar[uiSurface="sidebar"] {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {palette.BG_PANEL_ALT}, stop:1 {palette.BG_PANEL});
    border-right: 1px solid {palette.BORDER};
}}
QWidget#librarySidebar QLabel#libraryHeading {{
    color: {palette.TEXT_PRIMARY};
    font-size: 11pt;
    font-weight: 800;
    letter-spacing: 1.1px;
}}
QWidget#librarySidebar QLabel#libSectionTitle {{
    color: {palette.TEXT_MUTED};
    font-size: 9pt;
    font-weight: 700;
    letter-spacing: 1px;
}}
QListWidget#libraryRecentList, QListWidget#libraryPlaylistsList {{
    background: transparent;
    border: none;
    color: {palette.TEXT_PRIMARY};
    font-size: 9.5pt;
}}
QListWidget#libraryRecentList::item, QListWidget#libraryPlaylistsList::item {{
    padding: 8px 10px;
    border-radius: 9px;
    margin: 2px 0;
}}
QListWidget#libraryRecentList::item:selected, QListWidget#libraryPlaylistsList::item:selected {{
    background-color: {shades['soft']};
    color: {shades['lighter']};
}}
QListWidget#libraryRecentList::item:hover, QListWidget#libraryPlaylistsList::item:hover {{
    background-color: {palette.BG_HOVER};
}}
QWidget#groupsSidebar[uiSurface="sidebar"] {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {palette.BG_PANEL_ALT}, stop:1 {palette.BG_PANEL});
    border-right: 1px solid {palette.BORDER};
}}
QListWidget#groupsSidebarList {{
    background: transparent;
    border: none;
    color: {palette.TEXT_PRIMARY};
    font-size: 9.5pt;
}}
QListWidget#groupsSidebarList::item {{
    padding: 8px 10px;
    border-radius: 9px;
    margin: 2px 0;
}}
QListWidget#groupsSidebarList::item:selected {{
    background-color: {shades['soft']};
    color: {shades['lighter']};
}}
QListWidget#groupsSidebarList::item:hover {{
    background-color: {palette.BG_HOVER};
}}
QWidget#equalizerWidget {{
    background-color: {palette.BG_ROOT};
    border-radius: 14px;
}}
QPushButton[uiVariant="secondary"], QToolButton[uiVariant="secondary"] {{
    background-color: {palette.BG_PANEL_ALT};
    color: {palette.TEXT_PRIMARY};
    border: 1px solid {palette.BORDER};
    border-radius: 10px;
}}
QPushButton[uiVariant="secondary"]:hover, QToolButton[uiVariant="secondary"]:hover {{
    background-color: {palette.BG_HOVER};
    border-color: {palette.BORDER_STRONG};
}}
QPushButton[uiVariant="danger"], QToolButton[uiVariant="danger"] {{
    background-color: {shades['soft']};
    color: {palette.DANGER};
    border: 1px solid {palette.DANGER};
    border-radius: 10px;
}}
QPushButton[uiVariant="danger"]:hover, QToolButton[uiVariant="danger"]:hover {{
    background-color: {palette.DANGER};
    color: #ffffff;
}}
QWidget[uiSurface="mediaPanel"] {{ background: transparent; }}
QTabWidget#mediaTabs::pane {{
    background-color: {palette.BG_PANEL};
    border: 1px solid {palette.BORDER};
    border-radius: 14px;
}}
QProgressBar#mediaProgress {{
    background-color: {palette.BG_PANEL_ALT};
    color: {palette.TEXT_PRIMARY};
    border: 1px solid {palette.BORDER};
    border-radius: 8px;
    font-size: 7.5pt;
    font-weight: 650;
}}
QProgressBar#mediaProgress::chunk {{
    background-color: {shades['base']};
    border-radius: 7px;
}}
QLabel#mediaStatus {{ color: {palette.TEXT_MUTED}; font-size: 8.5pt; border: none; }}
QLabel#mediaStatus[uiState="loading"] {{ color: {palette.ACCENT_INFO}; }}
QLabel#mediaStatus[uiState="empty"] {{ color: {palette.TEXT_DIM}; }}
QLabel#mediaStatus[uiState="error"] {{ color: {palette.DANGER}; border: none; }}
QFrame#mediaSeparator {{ color: {palette.BORDER}; }}
QToolButton#mediaToolbarButton {{ min-width: 34px; min-height: 34px; font-size: 13pt; }}
QToolButton#mediaToolbarButton[uiVariant="primary"] {{
    background-color: {shades['base']};
    color: {shades['on_accent']};
    border: 1px solid {shades['hover']};
}}
QToolButton#mediaToolbarButton[uiVariant="info"] {{
    color: {palette.ACCENT_INFO};
    border-color: {palette.ACCENT_INFO};
}}
QPushButton[uiVariant="cast"] {{
    background-color: {palette.BG_PANEL_ALT};
    color: {palette.ACCENT_CAST};
    border: 1px solid {palette.ACCENT_CAST};
    border-radius: 8px;
}}
QPushButton[uiVariant="cast"]:hover {{
    background-color: {palette.ACCENT_CAST};
    color: {palette.BG_ROOT};
}}
QLabel#mediaMeta {{ color: {palette.TEXT_DIM}; font-size: 8pt; }}
QLabel#mediaPath {{ color: {palette.ACCENT_INFO}; font-size: 8pt; }}
QLabel#mediaSection {{ color: {palette.TEXT_MUTED}; font-weight: 700; font-size: 8.5pt; }}
QLabel#mediaRowIcon {{ font-size: 15pt; }}
QLabel#mediaRowTitle {{ color: {palette.TEXT_PRIMARY}; font-weight: 650; font-size: 9pt; }}
QLabel#mediaRowMeta {{ color: {palette.TEXT_SECONDARY}; font-size: 7.5pt; }}
QLabel#mediaRowDetail {{ color: {palette.TEXT_DIM}; font-size: 7.5pt; }}
QDialog[uiSurface="dialog"] {{
    background-color: {palette.BG_ROOT};
    color: {palette.TEXT_PRIMARY};
}}
QWidget[uiSurface="floating"] {{
    background-color: {palette.BG_PANEL};
    border: 1px solid {palette.BORDER_STRONG};
    border-radius: 14px;
}}
QDialog#commandPalette[uiSurface="floating"] {{ padding: 2px; }}
QLineEdit#commandSearch {{
    background-color: {palette.BG_PANEL_ALT};
    color: {palette.TEXT_PRIMARY};
    border: 1px solid {palette.BORDER};
    border-radius: 10px;
    padding: 9px 11px;
    font-size: 10.5pt;
}}
QListWidget#commandResults {{ background: transparent; border: none; color: {palette.TEXT_PRIMARY}; }}
QListWidget#commandResults::item {{ padding: 8px 9px; border-radius: 8px; }}
QListWidget#commandResults::item:selected {{ background-color: {shades['soft']}; color: {shades['lighter']}; }}
QFrame#toastNotice QLabel#toastMessage {{ color: {palette.TEXT_PRIMARY}; background: transparent; }}
QPushButton#toastAction {{ background: transparent; color: {shades['base']}; border: none; font-weight: 700; }}
QPushButton#toastClose, QPushButton[uiVariant="ghost"] {{
    background: transparent;
    color: {palette.TEXT_MUTED};
    border: none;
}}
QPushButton#toastClose:hover, QPushButton[uiVariant="ghost"]:hover {{ color: {palette.TEXT_PRIMARY}; }}
QLabel#splashStatus {{ color: {palette.TEXT_MUTED}; font-size: 8pt; border: none; }}
QLabel#splashStatus[uiState="active"] {{ color: {palette.SUCCESS}; }}
QLabel#splashStatus[uiState="error"] {{ color: {palette.DANGER}; border: none; }}
QDialog QLabel#titulo {{ color: {shades['base']}; font-size: 18pt; font-weight: 750; }}
QDialog QLabel#version {{ color: {palette.TEXT_DIM}; font-size: 8pt; }}
QDialog QLabel#aviso, QDialog QLabel#hw_label {{ color: {palette.TEXT_SECONDARY}; font-size: 10pt; }}
QDialog QLabel#hw_id {{
    color: {shades['lighter']};
    font-family: 'Consolas';
    font-size: 13pt;
    font-weight: 650;
    letter-spacing: 2px;
}}
QDialog QLabel#funciones_free {{ color: {palette.TEXT_MUTED}; font-size: 8pt; }}
QDialog QLineEdit#codigo_input {{
    background-color: {palette.BG_PANEL};
    border: 1px solid {palette.BORDER};
    border-radius: 10px;
    padding: 8px 14px;
    color: {palette.TEXT_PRIMARY};
    font-family: 'Consolas';
}}
QDialog QPushButton#btn_activar {{
    background-color: {shades['base']};
    color: {shades['on_accent']};
    border-radius: 10px;
    font-weight: 700;
}}
QDialog QPushButton#btn_continuar {{
    background-color: {palette.BG_PANEL_ALT};
    color: {palette.TEXT_SECONDARY};
    border: 1px solid {palette.BORDER};
    border-radius: 10px;
}}
"""
    # Color propio por sección en el botón de navegación seleccionado --
    # antes usaba siempre el degradado del acento elegido por el usuario
    # (vía los tokens #e0bb4a/#b3891c en DARK_STYLE), perdiendo la
    # distinción por categoría que sí tienen el icono y el título de
    # sección. "primary" (Favoritos) no está aquí a propósito: para esa
    # sección SÍ es correcto seguir usando el acento del usuario. Estos
    # valores deben reflejar SECTION_COLORS de ui/main_window.py -- no se
    # importan desde aquí para evitar un ciclo de imports (main_window ya
    # importa de este módulo).
    nav_variant_colors = {
        "primary": shades["base"],
        "success": ACCENT_PRESETS["Verde"],
        "tv": palette.ACCENT_INFO,
        "radio": palette.ACCENT_CATEGORY_ORANGE,
        "sleep": ACCENT_PRESETS["Violeta"],
        "download": ACCENT_PRESETS["Coral"],
    }
    for variant, color in nav_variant_colors.items():
        style += f"""
QToolButton#navButton[uiVariant="{variant}"]:checked {{
    background-color: {palette.BG_PANEL_ALT};
    color: {palette.TEXT_PRIMARY};
    border-left: 1px solid {color};
}}
"""

    if theme == "light":
        # Sustitución simultánea para que un color claro no vuelva a
        # coincidir accidentalmente con otra clave durante el recorrido.
        color_pattern = re.compile(
            "|".join(re.escape(color) for color in LIGHT_THEME_COLORS),
            re.IGNORECASE,
        )
        light_lookup = {key.lower(): value for key, value in LIGHT_THEME_COLORS.items()}
        style = color_pattern.sub(lambda match: light_lookup[match.group(0).lower()], style)
    return style


DARK_STYLE = """
QMainWindow, QDialog {
    background-color: #0a0a0a;
    color: #e6edf3;
    font-family: 'Inter', 'Segoe UI', sans-serif;
    font-size: 10pt;
}
QWidget {
    background-color: transparent;
    color: #e6edf3;
    font-family: 'Inter', 'Segoe UI', sans-serif;
    font-size: 10pt;
}
QWidget#appSurface {
    background-color: #08131f;
}

/* La ventana raíz es transparente: el redondeado real lo dan la barra de
   menú (arriba) y la barra de estado (abajo), que sí pintan su propio fondo. */
QMainWindow#mainWindowRoot {
    background: transparent;
}

/* ---------- Raíl de navegación ---------- */
QWidget#navRail {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #0e1b2a, stop:0.48 #091522, stop:1 #06101a);
    border-right: 1px solid rgba(255, 255, 255, 12);
}
QToolButton#navButton {
    background: transparent;
    border: none;
    border-left: 1px solid transparent;
    border-radius: 10px;
    color: #a6b5c7;
    font-size: 10pt;
    font-weight: 650;
    padding: 9px 12px;
    margin: 2px 0;
    min-height: 24px;
    text-align: left;
}
QToolButton#navButton:hover {
    background: rgba(255, 255, 255, 9);
    color: #e6edf3;
    border-left: 1px solid rgba(255, 255, 255, 28);
}
QToolButton#navButton:checked {
    background-color: #283c5e;
    color: #f2efe6;
    border-left: 1px solid #c9a227;
}
QToolButton#navButton:focus {
    border: 1px solid #e8c360;
}

/* ---------- Barra superior ---------- */
QLabel#sectionTitle {
    color: #ffffff;
    font-size: 17pt;
    font-weight: 800;
}
QLabel#catalogCount {
    color: #8b949e;
    background-color: rgba(255, 255, 255, 8);
    border: 1px solid rgba(255, 255, 255, 14);
    border-radius: 9px;
    padding: 4px 8px;
    font-size: 7.5pt;
    font-weight: 800;
    letter-spacing: 0.8px;
}
QLabel#navCaption {
    color: #8b96a8;
    font-size: 11pt;
    font-weight: 800;
    letter-spacing: 1.4px;
    padding: 0 10px 6px 10px;
}
QLineEdit#searchBox {
    background-color: #0d1b2a;
    border: 1px solid #2a3b55;
    border-radius: 10px;
    padding: 9px 14px;
    color: #e6edf3;
}
QLineEdit#searchBox:focus {
    border: 1px solid #c9a227;
    background-color: #12243a;
}
QComboBox#groupFilter:focus {
    border: 1px solid #c9a227;
    color: #f2efe6;
}
QComboBox#groupFilter {
    background-color: #142338;
    border: 1px solid #2a3b55;
    border-radius: 10px;
    padding: 7px 12px;
    color: #b9c2ce;
}
QComboBox#groupFilter:hover {
    background-color: #1a2d45;
    border-color: #405675;
    color: #f2efe6;
}
QComboBox#groupFilter::drop-down {
    border: none;
    width: 22px;
}

/* ---------- Listas tipo tarjeta ---------- */
QListWidget#channelList {
    background-color: transparent;
    border: none;
    outline: none;
}
QListWidget#channelList::item {
    border: none;
}
QListWidget#channelList::item:selected {
    background: transparent;
}

/* ---------- Panel de vídeo / ecualizador ---------- */
QFrame#playerFrame {
    background-color: #060606;
    border: 1px solid #2a3b55;
    border-radius: 16px;
}

/* ---------- Barra "Reproduciendo ahora" ---------- */
QFrame#nowPlayingBar {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #1e2c3e, stop:0.5 #111d2a, stop:1 #0a0a0a);
    border: 1px solid rgba(255, 255, 255, 18);
    border-top: 1px solid rgba(255, 255, 255, 26);
    border-radius: 18px;
}
QLabel#nowTitle {
    color: #ffffff;
    font-size: 14pt;
    font-weight: 750;
}
QLabel#nowSubtitle {
    color: #bcc9da;
    font-size: 8.5pt;
}
/* ---------- Botones de control ---------- */
QPushButton#playCircle {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #e0bb4a, stop:1 #b3891c);
    color: #0a0a0a;
    border: 1px solid rgba(255, 255, 255, 60);
    border-radius: 19px;
    font-size: 13pt;
    min-width: 38px;
    max-width: 38px;
    min-height: 38px;
    max-height: 38px;
    padding: 0;
}
QPushButton#playCircle:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #f0cd6e, stop:1 #c9a227);
    border: 1px solid rgba(255, 255, 255, 80);
}
QPushButton#ctrlButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #2e2e2e, stop:1 #1c1c1c);
    color: #e6edf3;
    border: 1px solid rgba(255, 255, 255, 14);
    border-radius: 11px;
    min-width: 26px;
    max-width: 26px;
    min-height: 26px;
    max-height: 26px;
    font-size: 9pt;
    padding: 0;
}
QPushButton#ctrlButton:hover {
    background: rgba(255, 255, 255, 10);
    border: 1px solid rgba(255, 255, 255, 30);
    color: #ffffff;
}
QPushButton#ctrlButton:checked {
    background-color: #c9a227;
    color: #0a0a0a;
    border: 1px solid rgba(255, 255, 255, 50);
}

/* Enviar a Chromecast/TV: acento propio (teal) al estar activo, para no
   confundirlo visualmente con "favorito" (dorado) ni con "grabando" (rojo). */
QPushButton#castButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #2e2e2e, stop:1 #1c1c1c);
    color: #e6edf3;
    border: 1px solid rgba(255, 255, 255, 14);
    border-radius: 11px;
    min-width: 26px;
    max-width: 26px;
    min-height: 26px;
    max-height: 26px;
    padding: 0;
    font-size: 9pt;
}
QPushButton#castButton:hover {
    background: rgba(47, 181, 154, 12);
    border: 1px solid rgba(58, 209, 181, 110);
}
QPushButton#castButton:checked {
    background-color: #2fb59a;
    color: #062b23;
    border: 1px solid rgba(255, 255, 255, 50);
}

/* Temporizador de apagado: acento violeta al estar activo. */
QPushButton#sleepButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #2e2e2e, stop:1 #1c1c1c);
    color: #e6edf3;
    border: 1px solid rgba(255, 255, 255, 14);
    border-radius: 11px;
    min-width: 26px;
    max-width: 26px;
    min-height: 26px;
    max-height: 26px;
    padding: 0;
    font-size: 9pt;
}
QPushButton#sleepButton:hover {
    background: rgba(167, 139, 250, 10);
    border: 1px solid rgba(167, 139, 250, 110);
}
QPushButton#sleepButton:checked {
    background-color: #8b7ae0;
    color: #171233;
    border: 1px solid rgba(255, 255, 255, 50);
}

/* Silencio: acento azulado discreto, sin usar el dorado de "favorito". */
QPushButton#muteButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #2e2e2e, stop:1 #1c1c1c);
    color: #e6edf3;
    border: 1px solid rgba(255, 255, 255, 14);
    border-radius: 11px;
    min-width: 26px;
    max-width: 26px;
    min-height: 26px;
    max-height: 26px;
    font-size: 9pt;
    padding: 0;
}
QPushButton#muteButton:hover {
    background: rgba(91, 155, 213, 10);
    border: 1px solid rgba(91, 155, 213, 110);
}
QPushButton#muteButton:checked {
    background-color: #4a7fb5;
    color: #0d1b2a;
    border: 1px solid rgba(255, 255, 255, 50);
}
QPushButton#recordButton {
    background-color: #242424;
    color: #e6edf3;
    border: 1px solid rgba(255, 255, 255, 10);
    border-radius: 11px;
    min-width: 26px;
    max-width: 26px;
    min-height: 26px;
    max-height: 26px;
    font-size: 9pt;
    padding: 0;
}
QPushButton#recordButton:hover {
    background: rgba(218, 54, 51, 14);
    border: 1px solid rgba(218, 54, 51, 80);
}
QPushButton#recordButton:checked {
    background-color: #da3633;
    color: white;
    border: 1px solid rgba(255, 255, 255, 40);
}

/* ---------- Genéricos ---------- */
QPushButton {
    background-color: #242424;
    color: #e6edf3;
    border: 1px solid #2a2a2a;
    border-radius: 6px;
    padding: 6px 14px;
}
QPushButton:hover {
    background-color: #2a2a2a;
}
QPushButton:focus {
    border: 1px solid #e8c360;
}
QSlider::groove:horizontal {
    height: 4px;
    background: #2a2a2a;
    border-radius: 2px;
}
QSlider::sub-page:horizontal {
    /* Tramo ya "recorrido" del volumen, coloreado con el acento -- antes
       el carril era gris plano de punta a punta y solo el mando marcaba
       el nivel; así se ve de un vistazo cuánto volumen hay sin fijarse en
       la posición exacta del mando. */
    background: #c9a227;
    border-radius: 2px;
}
QSlider::add-page:horizontal {
    background: #2a2a2a;
    border-radius: 2px;
}
QSlider::handle:horizontal {
    background: #c9a227;
    width: 12px;
    margin: -5px 0;
    border-radius: 6px;
}
/* Sliders verticales del ecualizador (ver ui/equalizer_dialog.py) -- sin
   esta sección, Qt los pinta con el estilo nativo del sistema en vez del
   tema oscuro, y desentonan de golpe con el resto del diálogo. */
QSlider::groove:vertical {
    width: 4px;
    background: #2a2a2a;
    border-radius: 2px;
}
QSlider::sub-page:vertical {
    background: #c9a227;
    border-radius: 2px;
}
QSlider::add-page:vertical {
    background: #2a2a2a;
    border-radius: 2px;
}
QSlider::handle:vertical {
    background: #c9a227;
    height: 12px;
    margin: 0 -5px;
    border-radius: 6px;
}
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 3px 1px 3px 0;
}
QScrollBar::handle:vertical {
    background: rgba(255, 255, 255, 22);
    border-radius: 4px;
    min-height: 32px;
}
QScrollBar::handle:vertical:hover {
    background: rgba(255, 255, 255, 38);
}
QScrollBar::handle:vertical:pressed {
    background: #c9a227;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
    background: none;
    border: none;
}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    /* Sin esto, Qt rellena el carril (la zona por la que se desliza el
       mando) con su patrón de rejilla por defecto en vez de un color
       plano — es justo lo que se veía como "no sólido". */
    background: transparent;
    border: none;
}
QScrollBar:horizontal {
    background: transparent;
    height: 8px;
    margin: 0 3px 1px 3px;
}
QScrollBar::handle:horizontal {
    background: rgba(255, 255, 255, 22);
    border-radius: 4px;
    min-width: 32px;
}
QScrollBar::handle:horizontal:hover {
    background: rgba(255, 255, 255, 38);
}
QScrollBar::handle:horizontal:pressed {
    background: #c9a227;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
    background: none;
    border: none;
}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
    border: none;
}
QSplitter#mainSplitter::handle {
    background-color: #2a3b55;
    width: 1px;
}
QSplitter#mainSplitter::handle:hover {
    background-color: #c9a227;
}
QFrame#ctrlSeparator {
    background-color: rgba(255, 255, 255, 26);
}
QStatusBar {
    background-color: #050d17;
    color: #6e7787;
    border-bottom-left-radius: 12px;
    border-bottom-right-radius: 12px;
}
QMenuBar {
    background-color: #060606;
    color: #b9c2ce;
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
    padding: 4px 4px 4px 6px;
}
QMenuBar::item:selected {
    background-color: #242424;
}
QMenu {
    background-color: #181818;
    color: #e6edf3;
    border: 1px solid rgba(255, 255, 255, 14);
    border-radius: 10px;
    padding: 4px;
}
QMenu::item {
    padding: 9px 14px;
    border-radius: 7px;
    margin: 1px 3px;
}
QMenu::item:selected {
    background-color: #c9a227;
    color: #0a0a0a;
    border-radius: 7px;
}

/* ---------- Barra de título propia ---------- */
QWidget#titleBar {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #11243a, stop:1 #08131f);
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 8);
}
QLabel#titleBrand {
    color: #c9a227;
    font-weight: 800;
    font-size: 12pt;
    letter-spacing: 0.3px;
    background: transparent;
}
QLabel#titleVersion {
    color: #8b949e;
    font-size: 7.5pt;
    font-weight: 700;
    letter-spacing: 0.7px;
    background: transparent;
}
QMenuBar#appMenuBar {
    background: transparent;
    border: none;
    padding: 0;
}
QMenuBar#appMenuBar::item {
    background: transparent;
    color: #b9c2ce;
    padding: 6px 12px;
    border-radius: 7px;
}
QMenuBar#appMenuBar::item:selected {
    background-color: rgba(255, 255, 255, 9);
    color: #e6edf3;
}

/* ---------- Controles de ventana (minimizar / maximizar / cerrar) ---------- */
QToolButton#winCtrlButton {
    background: transparent;
    border: none;
    color: #d8dee8;
    font-size: 13pt;
    font-weight: 600;
    border-radius: 8px;
    min-width: 34px;
    max-width: 34px;
    min-height: 28px;
    max-height: 28px;
}
QToolButton#winCtrlButton:hover {
    background-color: rgba(255, 255, 255, 10);
    color: #ffffff;
}
QToolButton#winCloseButton {
    background: transparent;
    border: none;
    color: #d8dee8;
    font-size: 14pt;
    font-weight: 600;
    border-radius: 8px;
    min-width: 34px;
    max-width: 34px;
    min-height: 28px;
    max-height: 28px;
}
QToolButton#winCloseButton:hover {
    background-color: #e81123;
    color: white;
}
QLineEdit, QComboBox {
    background-color: #181818;
    border: 1px solid #2a2a2a;
    border-radius: 9px;
    padding: 6px 10px;
    color: #e6edf3;
}
/* Lista desplegable de QComboBox: sin esto, Qt la pinta con la paleta
   nativa del sistema (fondo claro, texto oscuro/apenas visible) en vez del
   tema oscuro -- afectaba a TODOS los combos de la app (filtro de
   categoría, selectores de Configuración, el de "Gestionar canales
   personalizados"...), no solo a uno. */
QComboBox QAbstractItemView {
    background-color: #181818;
    color: #e6edf3;
    border: 1px solid #2a2a2a;
    border-radius: 8px;
    padding: 4px;
    outline: none;
    selection-background-color: #c9a227;
    selection-color: #0a0a0a;
}
QComboBox QAbstractItemView::item {
    padding: 6px 10px;
    min-height: 22px;
}
QComboBox QAbstractItemView::item:hover {
    background-color: #2a2a2a;
}

/* Botón principal ("Guardar", "Importar", "Aceptar"...) en los diálogos de
   Configuración / Añadir canal / Importar lista: antes todos los botones
   del cuadro de diálogo eran iguales entre sí y no se distinguían de los
   controles de canal; con esto la acción principal queda al mismo nivel
   visual que "reproducir" o "favorito" en el resto de la app. */
QPushButton#primaryButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #e0bb4a, stop:1 #b3891c);
    color: #0a0a0a;
    border: 1px solid rgba(255, 255, 255, 50);
    font-weight: 600;
}
QPushButton#primaryButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #f0cd6e, stop:1 #c9a227);
}

/* Pestañas (panel de Descargas: "Vídeo (URL)" / "Torrents"). Sin esto,
   QTabWidget usa el estilo nativo de Windows para la barra de pestañas —
   fondo claro con texto claro encima, prácticamente en blanco sobre el
   resto de la interfaz oscura. */
QTabWidget::pane {
    border: 1px solid rgba(255, 255, 255, 12);
    border-radius: 10px;
    background-color: #121212;
    top: -1px;
}
QTabBar::tab {
    background-color: #181818;
    color: #8b949e;
    padding: 9px 20px;
    border: 1px solid rgba(255, 255, 255, 10);
    border-bottom: none;
    border-top-left-radius: 9px;
    border-top-right-radius: 9px;
    margin-right: 2px;
}
QTabBar::tab:hover {
    background-color: rgba(255, 255, 255, 7);
    color: #e6edf3;
}
QTabBar::tab:selected {
    background-color: #121212;
    color: #f4d476;
    font-weight: 700;
    border-top: 2px solid #c9a227;
}

/* ---------- Diálogos (Configuración / Añadir canal / Importar lista) ----------
   Antes eran un QFormLayout plano sin ninguna jerarquía visual — ahora los
   campos relacionados van agrupados en paneles con el mismo lenguaje visual
   (degradado sutil + borde translúcido) que ya usa la barra de reproducción,
   en vez de quedar todos al mismo nivel. */
QFrame#dialogPanel {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #1c2c40, stop:1 #121e2e);
    border: 1px solid rgba(255, 255, 255, 16);
    border-top: 1px solid rgba(255, 255, 255, 24);
    border-radius: 14px;
}
QLabel#dialogTitle {
    color: #ffffff;
    font-size: 16pt;
    font-weight: 800;
}
QLabel#dialogSubtitle {
    color: #bcc9da;
    font-size: 8.5pt;
}
QLabel#dialogSectionLabel {
    color: #c9a227;
    font-weight: 700;
    font-size: 8pt;
    letter-spacing: 1.5px;
}

/* ---------- Portada de Inicio ---------- */
QScrollArea#homeScroll, QScrollArea#homeScroll > QWidget > QWidget {
    background: transparent;
    border: none;
}
QLabel#homeGreeting {
    color: #ffffff;
    font-size: 22pt;
    font-weight: 800;
    letter-spacing: -0.3px;
}
QLabel#homeHealthSummary {
    color: #a6b5c7;
    font-size: 9pt;
}
QLabel#homeHealthSummary[uiVariant="success"] { color: #42c985; }
QLabel#homeHealthSummary[uiVariant="danger"] { color: #f26f6c; }
QPushButton#homeQuickButton {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #e0bb4a, stop:1 #b3891c);
    color: #0a0a0a;
    border: 1px solid rgba(255, 255, 255, 60);
    border-radius: 22px;
    font-weight: 700;
    padding: 11px 22px;
}
QPushButton#homeQuickButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #f0cd6e, stop:1 #c9a227);
    border: 1px solid rgba(255, 255, 255, 80);
}
QPushButton#homeQuickButtonAlt {
    background-color: rgba(255, 255, 255, 6);
    color: #e6edf3;
    border: 1px solid rgba(255, 255, 255, 16);
    border-radius: 22px;
    font-weight: 700;
    padding: 11px 22px;
}
QPushButton#homeQuickButtonAlt:hover {
    background-color: rgba(255, 255, 255, 12);
    border: 1px solid rgba(255, 255, 255, 32);
}

/* ---------- Lenguaje compartido: vistas secundarias y diálogos ---------- */
QWidget#downloadPanel {
    background: transparent;
}
QTabWidget#mediaTabs::pane {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #13243a, stop:1 #0c1827);
    border: 1px solid #2a3b55;
    border-radius: 14px;
    top: -1px;
    padding: 8px;
}
QTabWidget#mediaTabs QTabBar::tab {
    background: transparent;
    color: #8fa1b8;
    border: none;
    border-bottom: 2px solid transparent;
    border-radius: 7px;
    margin: 0 2px;
    padding: 9px 13px;
    font-weight: 650;
}
QTabWidget#mediaTabs QTabBar::tab:hover {
    background: rgba(255, 255, 255, 8);
    color: #f2efe6;
}
QTabWidget#mediaTabs QTabBar::tab:selected {
    background: rgba(201, 162, 39, 20);
    color: #f4d476;
    border-bottom-color: #c9a227;
}
QDialog {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #12243a, stop:1 #091522);
}
QDialog QLabel#dialogTitle {
    color: #f2efe6;
    font-size: 17pt;
    font-weight: 800;
}
QDialog QLabel#dialogSubtitle {
    color: #8fa1b8;
    font-size: 9pt;
}
QDialog QLineEdit, QDialog QPlainTextEdit, QDialog QTextEdit {
    background-color: #0d1b2a;
    color: #f2efe6;
    border: 1px solid #2a3b55;
    border-radius: 9px;
    padding: 8px 10px;
    selection-background-color: #c9a227;
    selection-color: #0d1b2a;
}
QDialog QLineEdit:focus, QDialog QPlainTextEdit:focus, QDialog QTextEdit:focus {
    border-color: #c9a227;
    background-color: #12243a;
}
QDialog QComboBox, QDialog QSpinBox, QDialog QDateTimeEdit {
    background-color: #0d1b2a;
    color: #f2efe6;
    border: 1px solid #2a3b55;
    border-radius: 9px;
    padding: 7px 10px;
}
QDialog QListWidget, QDialog QTableWidget {
    background-color: #0d1b2a;
    alternate-background-color: #12243a;
    color: #f2efe6;
    border: 1px solid #2a3b55;
    border-radius: 10px;
    outline: none;
}
QDialog QListWidget::item, QDialog QTableWidget::item {
    padding: 7px;
    border-radius: 6px;
}
QDialog QListWidget::item:selected, QDialog QTableWidget::item:selected {
    background-color: rgba(201, 162, 39, 48);
    color: #f4d476;
}
QDialog QCheckBox, QDialog QRadioButton {
    color: #dbe5f1;
    spacing: 8px;
}
QDialog QGroupBox {
    color: #c9a227;
    border: 1px solid #2a3b55;
    border-radius: 10px;
    margin-top: 12px;
    padding: 12px 10px 10px 10px;
    font-weight: 750;
}
QDialog QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 5px;
}
"""
