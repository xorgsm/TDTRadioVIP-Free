"""Constantes de las secciones de navegación (Inicio/TV/Radio/Favoritos/
Historial/Descargas). Extraídas de ui/main_window.py para que los módulos
que las necesitan (ui/nav_top.py, ui/catalog_toolbar.py, controladores)
puedan importarlas a nivel de módulo sin crear un ciclo con main_window.
"""
from ui.style import ACCENT_PRESETS
from ui import palette

NAV_HOME, NAV_TV, NAV_RADIO, NAV_FAV, NAV_HIST, NAV_DOWNLOAD = range(6)
# Alto de la barra de navegación superior (ver ui.nav_top.build_nav_top).
# Mismo orden de magnitud que el icono de sección (24px) más el padding
# vertical del ritmo espacial documentado en DESIGN.md (8-18px).
NAV_TOP_HEIGHT = 56
# Títulos cortos a propósito: "Televisión (TDT)" y "Radio online" se
# comían casi todo el ancho disponible en la barra superior (título +
# botón Guía + filtro de categoría + buscador en una sola fila), dejando
# el propio título cortado en ventanas no muy anchas. La aclaración "TDT"
# y "online" ya la da el icono/tooltip del riel, no hace falta repetirla aquí.
SECTION_TITLES = {
    NAV_HOME: "Inicio",
    NAV_TV: "Televisión",
    NAV_RADIO: "Radio",
    NAV_FAV: "Favoritos",
    NAV_HIST: "Historial",
    NAV_DOWNLOAD: "Descargas",
}
# Mismo color por sección que ya usan los iconos de la barra de navegación
# superior, para poder pintar con él también el título de la sección activa
# (más acentos de color coherentes con lo que ya existía, no colores nuevos
# sueltos). Se define aquí, a nivel de módulo, para que tanto
# build_nav_top() como _on_nav_changed() lean del mismo sitio.
SECTION_COLORS = {
    NAV_HOME: ACCENT_PRESETS["Verde"],
    NAV_TV: palette.ACCENT_INFO,
    NAV_RADIO: palette.ACCENT_CATEGORY_ORANGE,
    NAV_FAV: palette.ACCENT,
    NAV_HIST: ACCENT_PRESETS["Violeta"],
    NAV_DOWNLOAD: ACCENT_PRESETS["Coral"],
}
SECTION_VARIANTS = {
    NAV_HOME: "success",
    NAV_TV: "tv",
    NAV_RADIO: "radio",
    NAV_FAV: "primary",
    NAV_HIST: "sleep",
    NAV_DOWNLOAD: "download",
}
