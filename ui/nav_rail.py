"""Riel lateral de navegación (Inicio/TV/Radio/Favoritos/Historial/
Descargas + toggle de biblioteca). Extraído de ui/main_window.py.
"""
from functools import partial

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QButtonGroup, QLabel, QToolButton, QVBoxLayout, QWidget

from ui import icons as app_icons
from ui import palette
from ui.nav_sections import (
    NAV_DOWNLOAD, NAV_FAV, NAV_HIST, NAV_HOME, NAV_RADIO, NAV_RAIL_WIDTH,
    NAV_TV, SECTION_COLORS, SECTION_VARIANTS,
)
from ui.visual import set_variant


def build_nav_rail(win) -> QWidget:
    rail = QWidget()
    rail.setObjectName("navRail")
    # Pensado como una columna de catálogo legible, no un riel de
    # iconos crípticos. Los textos hacen que las áreas sean reconocibles
    # de un vistazo y siguen conservando los iconos como anclas visuales.
    rail.setFixedWidth(NAV_RAIL_WIDTH)
    layout = QVBoxLayout(rail)
    layout.setContentsMargins(12, 24, 12, 14)
    layout.setSpacing(5)

    # La marca y la versión ya no se repiten aquí -- viven una sola vez,
    # más grandes, en la barra de título (ui.title_bar.build_title_bar,
    # titleBrand/titleVersion). EXPLORAR pasa a ser lo primero que se ve del riel.
    nav_caption = QLabel("EXPLORAR")
    nav_caption.setObjectName("navCaption")
    layout.addWidget(nav_caption)

    win.nav_group = QButtonGroup(win)
    win.nav_group.setExclusive(True)

    # Cada icono conserva el color de su sección como señal secundaria;
    # el estado activo usa una superficie común para no convertir toda
    # la navegación en un bloque de color distinto en cada pantalla.
    nav_icon_builders = {
        NAV_HOME: (app_icons.icon_home, SECTION_COLORS[NAV_HOME]),
        NAV_TV: (app_icons.icon_tv, SECTION_COLORS[NAV_TV]),
        NAV_RADIO: (app_icons.icon_radio, SECTION_COLORS[NAV_RADIO]),
        NAV_FAV: (app_icons.icon_favorite, SECTION_COLORS[NAV_FAV]),
        NAV_HIST: (app_icons.icon_history, SECTION_COLORS[NAV_HIST]),
        NAV_DOWNLOAD: (app_icons.icon_download, SECTION_COLORS[NAV_DOWNLOAD]),
    }
    nav_defs = [
        (NAV_HOME, "Inicio"),
        (NAV_TV, "Televisión"),
        (NAV_RADIO, "Radio"),
        (NAV_FAV, "Favoritos"),
        (NAV_HIST, "Historial"),
    ]
    # Nunca se construye en la versión free -- no hay import de
    # ui.download_panel que lo respalde (ver comentario junto a
    # self.download_panel más arriba), así que ni siquiera puede
    # activarse en tiempo de ejecución como en la edición con licencia.
    if not win.es_version_free:
        nav_defs.append((NAV_DOWNLOAD, "Descargas"))
    for nav_id, tooltip in nav_defs:
        btn = QToolButton()
        btn.setObjectName("navButton")
        set_variant(btn, SECTION_VARIANTS[nav_id])
        btn.setToolTip(tooltip)
        btn.setText(tooltip)
        btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        btn.setCheckable(True)
        btn.setCursor(Qt.PointingHandCursor)
        builder, inactive_color = nav_icon_builders[nav_id]
        btn.setIconSize(QSize(22, 22))
        btn.setIcon(builder(inactive_color, size=24))
        btn.toggled.connect(
            lambda _checked, b=btn, f=builder, c=inactive_color: b.setIcon(
                f(c, size=24)
            )
        )
        win.nav_group.addButton(btn, nav_id)
        layout.addWidget(btn)
        # El botón de descargas solo aparece con licencia activada de
        # verdad. En la versión free ni siquiera se construye (ver
        # nav_defs más arriba), así que este condicional solo puede
        # afectar a la edición con licencia sin activar todavía.
        if nav_id == NAV_DOWNLOAD and not win.activated:
            btn.setVisible(False)

    win.nav_group.button(NAV_HOME).setChecked(True)
    win.nav_group.idClicked.connect(win._on_nav_changed)

    layout.addStretch(1)

    win.library_toggle_btn = QToolButton()
    win.library_toggle_btn.setObjectName("navButton")
    win.library_toggle_btn.setToolTip("Mostrar/ocultar biblioteca")
    win.library_toggle_btn.setText("Biblioteca")
    win.library_toggle_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    win.library_toggle_btn.setCheckable(True)
    win.library_toggle_btn.setChecked(False)
    win.library_toggle_btn.setCursor(Qt.PointingHandCursor)
    win.library_toggle_btn.setIconSize(QSize(26, 26))
    win.library_toggle_btn.setIcon(app_icons.icon_library(palette.TEXT_MUTED))
    win.library_toggle_btn.toggled.connect(partial(toggle_library_sidebar, win))
    layout.addWidget(win.library_toggle_btn)

    return rail


def toggle_library_sidebar(win, visible: bool) -> None:
    win.library_sidebar.setVisible(visible)
    win.library_toggle_btn.setIcon(
        app_icons.icon_library(palette.ACCENT if visible else palette.TEXT_MUTED)
    )


def open_favorites_folder(win, folder) -> None:
    """
    Salta a la pestaña de Favoritos y, si se indica una carpeta, la deja
    seleccionada en el filtro -- llamado desde el panel de biblioteca al
    pinchar una "playlist". folder=None significa "todos los favoritos,
    sin filtrar por carpeta".
    """
    win.nav_group.button(NAV_FAV).click()
    if folder:
        idx = win.group_filter.findText(folder)
        if idx >= 0:
            win.group_filter.setCurrentIndex(idx)
    else:
        win.group_filter.setCurrentIndex(0)


def on_groups_sidebar_changed(win, groups) -> None:
    """
    Callback de GroupsSidebar cuando cambia la selección de grupos.
    `groups` es un set de nombres de grupo, o None si no hay filtro
    (se eligió "(Todos)" o se deseleccionó todo).
    """
    win._tv_sidebar_groups = groups
    win.lists.filter_current_list()
