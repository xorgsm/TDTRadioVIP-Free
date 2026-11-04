"""Constantes de las secciones de navegación (Inicio/TV/Radio/Favoritos/
Historial/Descargas). Extraídas de ui/main_window.py para que los módulos
que las necesitan (ui/nav_top.py, ui/catalog_toolbar.py, controladores)
puedan importarlas a nivel de módulo sin crear un ciclo con main_window.
"""
from ui import palette

NAV_HOME, NAV_TV, NAV_RADIO, NAV_FAV, NAV_HIST, NAV_DOWNLOAD = range(6)
# Alto de la barra de navegación superior (ver ui.nav_top.build_nav_top).
# 60, no 56: con el padding/margin real de QToolButton#navButton en
# ui/style.py (padding 9px arriba/abajo + margin 2px arriba/abajo + 24px
# min-height = 46px) y los 6+6px de márgenes verticales del layout, 56px
# deja solo 44px disponibles -- los botones se recortarían 2px. 60px deja
# 48px, con margen de sobra.
NAV_TOP_HEIGHT = 60
# Títulos cortos a propósito: "Televisión (TDT)" y "Radio online" se
# comían casi todo el ancho disponible en la barra superior (título +
# botón Guía + filtro de categoría + buscador en una sola fila), dejando
# el propio título cortado en ventanas no muy anchas. La aclaración "TDT"
# y "online" ya la da el icono/tooltip de la barra de navegación superior,
# no hace falta repetirla aquí.
SECTION_TITLES = {
    NAV_HOME: "Inicio",
    NAV_TV: "Televisión",
    NAV_RADIO: "Radio",
    NAV_FAV: "Favoritos",
    NAV_HIST: "Historial",
    NAV_DOWNLOAD: "Descargas",
}
# Color de identidad de cada sección: bloque de la pestaña activa, icono en
# reposo y título. Se define aquí, a nivel de módulo, para que tanto
# build_nav_top() como _on_nav_changed() lean del mismo sitio.
SECTION_COLORS = {
    NAV_HOME: palette.ACCENT_HOME,
    NAV_TV: palette.ACCENT_INFO,
    NAV_RADIO: palette.ACCENT_CATEGORY_ORANGE,
    NAV_FAV: palette.ACCENT_FAVORITE,
    NAV_HIST: palette.ACCENT_HISTORY,
    NAV_DOWNLOAD: palette.ACCENT_DOWNLOAD,
}
# Deben coincidir con las claves de SECTION_IDENTS en ui/style/builder.py.
SECTION_VARIANTS = {
    NAV_HOME: "home",
    NAV_TV: "tv",
    NAV_RADIO: "radio",
    NAV_FAV: "favorite",
    NAV_HIST: "history",
    NAV_DOWNLOAD: "download",
}
