"""
Composición de la hoja de estilos final.

`build_style` parte de la plantilla QSS base y le añade los bloques que
dependen del color de acento y del tema (oscuro/claro).
"""

import re

from ui import palette
from ui.style.colors import (
    ACCENT_PRESETS,
    DEFAULT_ACCENT,
    LIGHT_THEME_COLORS,
    accent_shades,
)
from ui.style.qss_base import DARK_STYLE
from ui.style.vivid import vivid_block


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
        "#7c6cff": shades["base"],
        "#e0bb4a": shades["light"],
        "#a095ff": shades["lighter"],
        "#f0cd6e": shades["lighter"],
        "#c4bcff": shades["lighter"],
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
QLabel[uiVariant="success"] {{ color: {palette.SUCCESS}; }}
QLabel[uiVariant="secondary"] {{ color: {palette.TEXT_SECONDARY}; }}
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
QWidget#navTopBar {{
    background-color: {palette.BG_PANEL};
    border-bottom: 1px solid {palette.BORDER};
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
/* El fondo/borde/foco de cada tarjeta de carrusel los pone
   ui.carousel._card_stylesheet() por instancia (degradado determinista
   derivado del nombre del canal -- ver spec v8 §6.3), así que aquí solo
   queda la regla que sigue siendo global: los QLabel hijos transparentes
   para que se vea el degradado del QFrame padre. */
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
QPushButton[uiVariant="success"], QToolButton[uiVariant="success"] {{
    background-color: {shades['soft']};
    color: {palette.SUCCESS};
    border: 1px solid {palette.SUCCESS};
    border-radius: 10px;
}}
QPushButton[uiVariant="success"]:hover, QToolButton[uiVariant="success"]:hover {{
    background-color: {palette.SUCCESS};
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
    # valores deben reflejar SECTION_COLORS de ui/nav_sections.py -- no se
    # importan desde aquí para evitar un ciclo de imports (nav_sections ya
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

    style += vivid_block(shades, theme, nav_variant_colors)

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


