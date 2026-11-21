"""Raíl lateral de navegación (rediseño v10): marca arriba, secciones,
"Mi biblioteca" y, al pie, la tarjeta de VPN, Ajustes, "Más" y la búsqueda
global. Deja sus widgets como atributos de `win` (nav_group,
library_toggle_btn, settings_btn, more_menu_btn, global_search_btn...), que
leen los controladores.

Alto: a 860 × 580 (mínimo de la ventana) el raíl solo tiene ~420 px. Cuando
el alto no da para las entradas con su relleno normal, el raíl pasa a
densidad compacta (botones más bajos, sin huecos); y si ni así cabe, la parte
de arriba (marca, secciones y biblioteca) se desplaza dentro de un
QScrollArea mientras el pie (VPN, Ajustes, Más, búsqueda) sigue fijo.
"""
from functools import partial

from PySide6.QtCore import QEvent, QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QScrollArea, QSizePolicy,
    QToolButton, QVBoxLayout, QWidget,
)

from ui import icons as app_icons
from ui import palette
from ui.more_menu import build_global_search_button, build_more_menu_button
from ui.nav_sections import (
    NAV_DOWNLOAD, NAV_FAV, NAV_GUIDE, NAV_HIST, NAV_HOME, NAV_RADIO, NAV_TV,
    SECTION_COLORS, SECTION_VARIANTS,
)
from ui.style.colors import readable_on_surface
from ui.visual import set_variant

RAIL_WIDTH = 208
RAIL_COMPACT_WIDTH = 64
# Por debajo de este ancho de ventana el raíl pasa a solo iconos.
RAIL_COMPACT_BELOW = 1000
# Separación entre entradas del layout (0: cada botón ya lleva 2 px de margen
# por arriba y por abajo; con siete secciones no sobra alto para más).
RAIL_SPACING = 0
# Huecos de la parte de arriba (tras la marca, antes de «Mi biblioteca»):
# alto normal y alto en densidad compacta.
RAIL_GAPS = ((10, 0), (14, 4))
# Densidad compacta: hoja de estilos propia del raíl, que manda sobre la de
# la aplicación (la de un widget gana a la heredada). Baja cada botón de 48 a
# 34 px sin bajar del mínimo de 24 px de contenido (icono de 22).
RAIL_DENSE_STYLE = """
QToolButton#navButton {
    padding-top: 3px;
    padding-bottom: 3px;
    margin: 0px;
}
"""


class VpnStatusCard(QFrame):
    """Tarjeta «VPN activa» del pie del raíl. Solo se ve con un túnel
    conectado; su única fuente es el sondeo de ui.vpn_status (¿algún perfil
    conectado?), que consulta fuera del hilo de la UI; el diálogo de VPN solo
    le pide que vuelva a mirar. Aquí no se importa nada de
    core.vpn_client: la edición Free no lo empaqueta."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("navVpnCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)
        head = self._head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.setSpacing(8)
        head.setAlignment(Qt.AlignLeft)
        self._dot = QFrame()
        self._dot.setObjectName("navVpnDot")
        self._dot.setFixedSize(8, 8)
        head.addWidget(self._dot)
        self._title = QLabel("VPN activa")
        self._title.setObjectName("navVpnTitle")
        head.addWidget(self._title)
        layout.addLayout(head)
        self._detail = QLabel()
        self._detail.setObjectName("navVpnDetail")
        # Un nombre de servidor largo no debe ensanchar el raíl (ancho fijo):
        # se recorta y el nombre completo queda en el tooltip.
        self._detail.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        layout.addWidget(self._detail)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setVisible(False)

    def set_status(self, connected: bool, label: str) -> None:
        self._detail.setText(label)
        self.setToolTip(f"VPN activa · {label}" if label else "VPN activa")
        self.setVisible(bool(connected))

    def set_compact(self, compact: bool) -> None:
        """A 64 px solo queda el punto verde; el servidor va en el tooltip."""
        self._title.setVisible(not compact)
        self._detail.setVisible(not compact)
        margin = 0 if compact else 10
        self.layout().setContentsMargins(margin, 8, margin, 8)
        self._head.setAlignment(Qt.AlignHCenter if compact else Qt.AlignLeft)


class NavRail(QWidget):
    """El raíl en sí: un QWidget con la tarjeta de VPN opcional, la parte de
    arriba desplazable (sections_scroll/sections) y el pie fijo."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("navRail")
        # Una subclase Python de QWidget no pinta el fondo/borde de la hoja
        # de estilos (QWidget#navRail) sin este atributo.
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.vpn_card = None
        self.sections_scroll = None
        self.sections = None
        self._dense = False
        # Alto que pide el raíl con densidad normal; None = hay que medirlo
        # (cambió el estilo, la tarjeta de VPN o el modo de iconos).
        self._normal_need = None
        self._applying_density = False
        # Posición en sections.layout() de cada hueco de RAIL_GAPS. Se guarda
        # el índice, no el QSpacerItem: el layout es su dueño en C++ y una
        # referencia de Python lo liberaría dos veces al destruir el raíl.
        self.gap_indexes = []
        # La densidad se decide fuera del evento que la provoca: cambiar la
        # hoja de estilos del raíl dentro de su propio StyleChange o de un
        # show() (mientras Qt repule los hijos) cuelga el proceso.
        self._density_timer = QTimer(self)
        self._density_timer.setSingleShot(True)
        self._density_timer.setInterval(0)
        self._density_timer.timeout.connect(self.update_density)

    def set_vpn_status(self, connected: bool, label: str) -> None:
        """Muestra u oculta «VPN activa». No hace nada si la edición no
        tiene VPN (Free, o con licencia sin activar)."""
        if self.vpn_card is not None:
            was_shown = not self.vpn_card.isHidden()
            self.vpn_card.set_status(connected, label)
            if was_shown == self.vpn_card.isHidden():
                self.invalidate_density()

    def is_dense(self) -> bool:
        return self._dense

    def invalidate_density(self) -> None:
        """Vuelve a medir el alto que pide el raíl y decide la densidad (en
        la siguiente vuelta del bucle de eventos)."""
        self._normal_need = None
        self._density_timer.start()

    def update_density(self) -> None:
        """Densidad compacta cuando el alto del raíl no da para todas sus
        entradas con el relleno normal."""
        if self.sections is None:
            return
        if self._normal_need is None:
            self._set_dense(False)
            self._normal_need = self._height_need()
        self._set_dense(self.height() < self._normal_need)
        # Geometría nueva ya, no en la siguiente LayoutRequest.
        self.sections.layout().activate()
        self.layout().activate()

    def _height_need(self) -> int:
        layout = self.layout()
        margins = layout.contentsMargins()
        heights = [self.sections.sizeHint().height()]
        for index in range(layout.count()):
            widget = layout.itemAt(index).widget()
            if widget is not None and widget is not self.sections_scroll and not widget.isHidden():
                heights.append(widget.sizeHint().height())
        spacing = layout.spacing() * (len(heights) - 1)
        return margins.top() + margins.bottom() + sum(heights) + spacing

    def _set_dense(self, dense: bool) -> None:
        if dense == self._dense:
            return
        self._dense = dense
        self._applying_density = True
        try:
            spacing = 0 if dense else RAIL_SPACING
            self.layout().setSpacing(spacing)
            self.sections.layout().setSpacing(spacing)
            for index, (normal, compact) in zip(self.gap_indexes, RAIL_GAPS):
                gap = self.sections.layout().itemAt(index).spacerItem()
                gap.changeSize(0, compact if dense else normal, QSizePolicy.Minimum, QSizePolicy.Fixed)
            self.sections.layout().invalidate()
            # setStyleSheet repule el raíl y sus hijos (y vacía la caché de
            # sizeHint de cada botón) en el acto.
            self.setStyleSheet(RAIL_DENSE_STYLE if dense else "")
        finally:
            self._applying_density = False

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._density_timer.start()

    def changeEvent(self, event):
        super().changeEvent(event)
        # Cambió la hoja de estilos o la fuente de fuera (la de la app o la
        # de la ventana): el alto normal medido ya no vale.
        if event.type() in (QEvent.StyleChange, QEvent.FontChange) and not self._applying_density:
            self.invalidate_density()


def _add_gap(rail: NavRail, layout: QVBoxLayout) -> None:
    normal, _compact = RAIL_GAPS[len(rail.gap_indexes)]
    layout.addSpacing(normal)
    rail.gap_indexes.append(layout.count() - 1)


def build_nav_rail(win) -> NavRail:
    rail = NavRail()
    rail.setFixedWidth(RAIL_WIDTH)
    outer = QVBoxLayout(rail)
    outer.setContentsMargins(12, 16, 12, 12)
    outer.setSpacing(RAIL_SPACING)

    # Parte de arriba (marca, secciones y biblioteca): se desplaza si el alto
    # no da ni con densidad compacta; el pie de abajo nunca.
    sections = QWidget()
    sections.setObjectName("navRailSections")
    # Su ancho es el del raíl (fijo): un texto largo no lo ensancha ni saca
    # una barra horizontal.
    sections.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
    layout = QVBoxLayout(sections)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(RAIL_SPACING)
    scroll = QScrollArea()
    scroll.setObjectName("navRailScroll")
    scroll.setFrameShape(QFrame.NoFrame)
    # El ancho lo manda el raíl (64/208 px), no la barra ni el sizeHint del área.
    scroll.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Expanding)
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    scroll.viewport().setAutoFillBackground(False)
    scroll.setWidget(sections)
    outer.addWidget(scroll, 1)
    rail.sections_scroll = scroll
    rail.sections = sections

    brand = QLabel("TDT & Radio VIP")
    brand.setObjectName("navBrand")
    layout.addWidget(brand)
    _add_gap(rail, layout)
    win._nav_rail_brand = brand

    win.nav_group = QButtonGroup()
    win.nav_group.setExclusive(True)

    # Cada icono lleva el color de su sección; la activa se vuelve un bloque
    # de ese color, con el icono en tinta para que se lea encima.
    nav_icon_builders = {
        NAV_HOME: (app_icons.icon_home, readable_on_surface(SECTION_COLORS[NAV_HOME])),
        NAV_TV: (app_icons.icon_tv, readable_on_surface(SECTION_COLORS[NAV_TV])),
        NAV_RADIO: (app_icons.icon_radio, readable_on_surface(SECTION_COLORS[NAV_RADIO])),
        NAV_GUIDE: (app_icons.icon_guide, readable_on_surface(SECTION_COLORS[NAV_GUIDE])),
        NAV_FAV: (app_icons.icon_favorite, readable_on_surface(SECTION_COLORS[NAV_FAV])),
        NAV_HIST: (app_icons.icon_history, readable_on_surface(SECTION_COLORS[NAV_HIST])),
        NAV_DOWNLOAD: (app_icons.icon_download, readable_on_surface(SECTION_COLORS[NAV_DOWNLOAD])),
    }
    nav_defs = [
        (NAV_HOME, "Inicio"),
        (NAV_TV, "Televisión"),
        (NAV_RADIO, "Radio"),
        (NAV_GUIDE, "Guía"),
        (NAV_FAV, "Favoritos"),
        (NAV_HIST, "Historial"),
    ]
    # Nunca se construye en la versión free: no hay ui.download_panel que lo
    # respalde, así que ni siquiera puede activarse en tiempo de ejecución.
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
            lambda checked, b=btn, f=builder, c=inactive_color: b.setIcon(
                f(palette.INK if checked else c, size=24)
            )
        )
        win.nav_group.addButton(btn, nav_id)
        layout.addWidget(btn)
        nav_buttons.append(btn)
        # Descargas solo aparece con licencia activada de verdad.
        if nav_id == NAV_DOWNLOAD and not win.activated:
            btn.setVisible(False)

    win.nav_group.button(NAV_HOME).setChecked(True)
    win.nav_group.idClicked.connect(win.navigation.on_nav_changed)

    _add_gap(rail, layout)
    caption = QLabel("Mi biblioteca")
    caption.setObjectName("navCaption")
    layout.addWidget(caption)
    win._nav_rail_caption = caption

    win.library_toggle_btn = QToolButton()
    win.library_toggle_btn.setObjectName("navButton")
    win.library_toggle_btn.setToolTip("Mostrar/ocultar biblioteca")
    win.library_toggle_btn.setText("Biblioteca")
    win.library_toggle_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    win.library_toggle_btn.setCheckable(True)
    win.library_toggle_btn.setChecked(False)
    win.library_toggle_btn.setCursor(Qt.PointingHandCursor)
    win.library_toggle_btn.setIconSize(QSize(22, 22))
    win.library_toggle_btn.setIcon(app_icons.icon_library(palette.TEXT_MUTED))
    win.library_toggle_btn.toggled.connect(partial(toggle_library_sidebar, win))
    layout.addWidget(win.library_toggle_btn)

    layout.addStretch(1)

    # Desde aquí, el pie fijo, en el layout del propio raíl.
    layout = outer
    # «VPN activa», encima de Ajustes: solo en la edición con licencia
    # activada, que es la única con VPN (ver ui.more_menu, entrada «VPN…»).
    if win.activated and not win.es_version_free:
        rail.vpn_card = VpnStatusCard()
        layout.addWidget(rail.vpn_card)

    # Pie, apilado en vertical para que quepa también a 64 px: Ajustes,
    # "Más" (resto de opciones) y búsqueda global (Ctrl+K).
    win.settings_btn = QToolButton()
    win.settings_btn.setObjectName("navButton")
    win.settings_btn.setToolTip("Ajustes")
    win.settings_btn.setText("Ajustes")
    win.settings_btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
    win.settings_btn.setCursor(Qt.PointingHandCursor)
    win.settings_btn.setIconSize(QSize(22, 22))
    win.settings_btn.setIcon(app_icons.icon_settings(palette.TEXT_MUTED))
    win.settings_btn.clicked.connect(lambda: win.dialogs.open_settings())
    layout.addWidget(win.settings_btn)

    win.global_search_btn = build_global_search_button(win)
    win.more_menu_btn = build_more_menu_button(win)
    layout.addWidget(win.more_menu_btn)
    layout.addWidget(win.global_search_btn)

    win._nav_rail_text_buttons = nav_buttons + [win.more_menu_btn, win.library_toggle_btn, win.settings_btn]
    # Cada entrada ocupa todo el ancho útil: la sección activa es un bloque
    # parejo, no una píldora del ancho de su texto.
    for btn in win._nav_rail_text_buttons:
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    win._nav_rail = rail
    return rail


def update_nav_rail_compact(win, width: int) -> None:
    """Por debajo de RAIL_COMPACT_BELOW px de ventana, el raíl pasa a solo
    iconos y 64 px (nunca a menú hamburguesa, spec v8 §5.4)."""
    compact = width < RAIL_COMPACT_BELOW
    style = Qt.ToolButtonIconOnly if compact else Qt.ToolButtonTextBesideIcon
    for btn in win._nav_rail_text_buttons:
        btn.setToolButtonStyle(style)
    win._nav_rail_brand.setVisible(not compact)
    win._nav_rail_caption.setVisible(not compact)
    margin = 8 if compact else 12
    win._nav_rail.layout().setContentsMargins(margin, 16, margin, 12)
    if win._nav_rail.vpn_card is not None:
        win._nav_rail.vpn_card.set_compact(compact)
    win._nav_rail.setFixedWidth(RAIL_COMPACT_WIDTH if compact else RAIL_WIDTH)
    # Sin marca ni leyenda el raíl pide menos alto: se vuelve a medir.
    win._nav_rail.invalidate_density()


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
