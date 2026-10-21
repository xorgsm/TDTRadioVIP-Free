"""Barra de navegación superior (Inicio/TV/Radio/Favoritos/Historial/
Descargas + toggle de biblioteca). Sustituye a ui/nav_rail.py (raíl lateral
fijo de 180px) como parte del rediseño v8 -- ver
docs/superpowers/specs/2026-09-09-v8-ui-redesign-design.md §4.1.
"""
from functools import partial

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QButtonGroup, QHBoxLayout, QToolButton, QWidget

from ui import icons as app_icons
from ui import palette
from ui.more_menu import build_global_search_button, build_more_menu_button
from ui.nav_sections import (
    NAV_DOWNLOAD, NAV_FAV, NAV_HIST, NAV_HOME, NAV_RADIO, NAV_TOP_HEIGHT,
    NAV_TV, SECTION_COLORS, SECTION_VARIANTS,
)
from ui.visual import set_variant


def build_nav_top(win) -> QWidget:
    bar = QWidget()
    bar.setObjectName("navTopBar")
    bar.setFixedHeight(NAV_TOP_HEIGHT)
    layout = QHBoxLayout(bar)
    layout.setContentsMargins(18, 6, 12, 6)
    layout.setSpacing(6)

    win.nav_group = QButtonGroup()
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
    # self.download_panel en main_window.py), así que ni siquiera puede
    # activarse en tiempo de ejecución como en la edición con licencia.
    if not win.es_version_free:
        nav_defs.append((NAV_DOWNLOAD, "Descargas"))
    nav_buttons = []
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
        nav_buttons.append(btn)
        # El botón de descargas solo aparece con licencia activada de
        # verdad. En la versión free ni siquiera se construye (ver
        # nav_defs más arriba), así que este condicional solo puede
        # afectar a la edición con licencia sin activar todavía.
        if nav_id == NAV_DOWNLOAD and not win.activated:
            btn.setVisible(False)

    win.nav_group.button(NAV_HOME).setChecked(True)
    win.nav_group.idClicked.connect(win.navigation.on_nav_changed)

    layout.addStretch(1)

    # Búsqueda global y "Más ▾" (spec v8 §5.1/§5.2): sustituyen a la
    # entrada "Búsqueda global…" y a la barra de menú clásica
    # (Archivo/Configuración/Ayuda), retiradas -- ver ui.more_menu.
    win.global_search_btn = build_global_search_button(win)
    layout.addWidget(win.global_search_btn)

    win.more_menu_btn = build_more_menu_button(win)
    layout.addWidget(win.more_menu_btn)

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

    # Umbral de colapso a solo-iconos (spec v8 §5.4: "nunca a menú
    # hamburguesa"): el ancho real que necesitan estos botones con su
    # texto completo, medido con sizeHint() en vez de un píxel fijo a
    # ojo -- así el umbral se ajusta solo a la fuente/DPI reales de cada
    # máquina, igual que ya hace download_panel.py con QFontMetrics para
    # sus propios botones de ancho variable. global_search_btn no entra
    # en la lista a colapsar (siempre fue solo icono, sin texto que
    # quitar) pero sí cuenta para el ancho total, porque ocupa sitio en
    # la fila igualmente.
    todos_los_widgets = nav_buttons + [win.global_search_btn, win.more_menu_btn, win.library_toggle_btn]
    margenes = layout.contentsMargins()
    win._nav_top_full_width = (
        margenes.left() + margenes.right()
        + sum(w.sizeHint().width() for w in todos_los_widgets)
        + layout.spacing() * (len(todos_los_widgets) - 1)
    )
    win._nav_top_text_buttons = nav_buttons + [win.more_menu_btn, win.library_toggle_btn]

    return bar


def update_nav_top_compact(win, width: int) -> None:
    """Colapsa la barra superior a solo iconos (nunca a menú hamburguesa,
    spec v8 §5.4) cuando el ancho disponible ya no basta para las
    pestañas con su texto completo -- el umbral es el ancho real medido
    en build_nav_top(), no un valor fijo a ojo."""
    compact = width < win._nav_top_full_width
    style = Qt.ToolButtonIconOnly if compact else Qt.ToolButtonTextBesideIcon
    for btn in win._nav_top_text_buttons:
        btn.setToolButtonStyle(style)


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
