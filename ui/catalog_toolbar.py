"""Barra superior del catálogo (título de sección, guía, alternar vista,
filtros y buscador). Extraído de ui/main_window.py.
"""
from functools import partial

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QPushButton,
    QSizePolicy, QToolButton, QVBoxLayout,
)

from core import config as cfg
from ui import icons as app_icons
from ui import palette
from ui.nav_sections import NAV_HOME, SECTION_TITLES
from ui.widgets import ChannelGridDelegate


def build_top_bar(win) -> QVBoxLayout:
    # Dos filas: la primera da contexto a la sección y la segunda se
    # dedica enteramente a explorar. Es la misma jerarquía que el
    # lateral de Pencil y evita que el buscador pierda anchura ante los
    # filtros en ventanas normales.
    bar = QVBoxLayout()
    bar.setSpacing(10)
    title_row = QHBoxLayout()
    title_row.setSpacing(10)
    filters_row = QVBoxLayout()
    filters_row.setSpacing(8)
    filter_options_row = QHBoxLayout()
    filter_options_row.setSpacing(8)

    win.section_title = QLabel(SECTION_TITLES[NAV_HOME])
    win.section_title.setObjectName("sectionTitle")
    # Sin mínimo protegido, un QHBoxLayout bajo presión de espacio lo
    # encoge a él antes que a group_filter/search_box (que sí tienen
    # min/max explícitos) -- por eso "Televisión" salía cortado en
    # ventanas estrechas. 110px cubre el título más largo ("Televisión")
    # con el tamaño de fuente actual; si aun así falta sitio, se elide
    # con "…" en vez de recortarse sin avisar.
    win.section_title.setMinimumWidth(90)
    win.section_title.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
    title_row.addWidget(win.section_title)

    win.catalog_count_label = QLabel()
    win.catalog_count_label.setObjectName("catalogCount")
    win.catalog_count_label.setMaximumWidth(110)
    win.catalog_count_label.hide()
    title_row.addWidget(win.catalog_count_label)
    title_row.addStretch(1)

    win.epg_btn = QPushButton("Guía")
    win.epg_btn.setToolTip("Ver parrilla de programación")
    win.epg_btn.clicked.connect(win.epg.open_dialog)
    title_row.addWidget(win.epg_btn)

    # Alternar lista/cuadrícula para los dos catálogos principales --
    # visibilidad controlada junto al resto en _on_nav_changed().
    win.tv_view_toggle = QToolButton()
    win.tv_view_toggle.setObjectName("catalogViewToggle")
    win.tv_view_toggle.setCheckable(True)
    win.tv_view_toggle.setCursor(Qt.PointingHandCursor)
    win.tv_view_toggle.setIconSize(QSize(18, 18))
    # Iconos dibujados a mano (ver ui/icons.py), no texto: el carácter
    # "⊞" que se usaba antes con setText() no está garantizado en Segoe
    # UI y salía en blanco -- solo se veía el fondo dorado/de acento del
    # estado :checked, sin ningún icono encima (reportado con captura).
    win.tv_view_toggle.setIcon(app_icons.icon_grid_view(palette.TEXT_DIM))
    win.tv_view_toggle.setToolTip("Ver catálogo en cuadrícula")
    win.tv_view_toggle.setFixedSize(30, 30)
    win.tv_view_toggle.toggled.connect(partial(toggle_grid_view, win))
    title_row.addWidget(win.tv_view_toggle)

    # Filtro por estado de salud del stream (TV y Radio). Filtra con los
    # resultados ya guardados del diagnóstico (core/stream_health_store),
    # sin tocar la red: elegir una opción es instantáneo. El userData de
    # cada opción es la clave que entiende matches_health_filter().
    win.health_filter = QComboBox()
    win.health_filter.setObjectName("groupFilter")
    for etiqueta, clave in (
        ("Estado: todos", "all"),
        ("Estables", "stable"),
        ("Con incidencias", "issues"),
        ("Diagnóstico antiguo", "stale"),
        ("Sin diagnosticar", "unchecked"),
    ):
        win.health_filter.addItem(etiqueta, clave)
    win.health_filter.setToolTip(
        "Filtrar por el último diagnóstico guardado "
        "(Archivo > Diagnosticar canales y emisoras…)"
    )
    win.health_filter.currentIndexChanged.connect(win.lists.filter_current_list)
    win.health_filter.setMinimumWidth(88)
    win.health_filter.setMaximumWidth(140)
    filter_options_row.addWidget(win.health_filter)

    win.group_filter = QComboBox()
    win.group_filter.setObjectName("groupFilter")
    win.group_filter.addItem("Todas las categorías")
    win.group_filter.currentTextChanged.connect(win.lists.filter_current_list)
    # Antes con setFixedWidth(200): a la anchura mínima de ventana que
    # permite la app (900px), el título + 200 + 240 del buscador no
    # cabían en la columna de contenido, y al ser anchos fijos Qt no
    # podía encogerlos — se salían del panel sin más, cortando la
    # esquina redondeada del buscador. Con mínimo/máximo, encogen antes
    # de desbordar.
    win.group_filter.setMinimumWidth(100)
    win.group_filter.setMaximumWidth(175)
    filter_options_row.addWidget(win.group_filter)

    win.catalog_sort = QComboBox()
    win.catalog_sort.setObjectName("groupFilter")
    win.catalog_sort.addItem("Orden original", "source")
    win.catalog_sort.addItem("Nombre A–Z", "name")
    win.catalog_sort.addItem("Favoritos primero", "favorites")
    win.catalog_sort.setToolTip("Ordenar el catálogo")
    win.catalog_sort.setMinimumWidth(98)
    win.catalog_sort.setMaximumWidth(140)
    win.catalog_sort.currentIndexChanged.connect(lambda _idx: on_catalog_sort_changed(win))
    filter_options_row.addWidget(win.catalog_sort)

    win.search_box = QLineEdit()
    win.search_box.setObjectName("searchBox")
    win.search_box.setPlaceholderText("Buscar canal o emisora…")
    win.search_box.setMinimumWidth(100)
    win.search_box.setMaximumWidth(16777215)
    # Antirrebote: filtrar en cada tecla (aunque cada pasada ya vaya
    # protegida con setUpdatesEnabled, ver ChannelListsController.
    # filter_current_list) sigue siendo trabajo de más si el usuario
    # escribe varias letras seguidas rápido -- con esto se espera a
    # que pare de teclear 150ms antes de filtrar, sin cambiar nada
    # para quien escribe despacio (nunca se nota el retraso).
    win._search_debounce = QTimer(win)
    win._search_debounce.setSingleShot(True)
    win._search_debounce.setInterval(150)
    win._search_debounce.timeout.connect(win.lists.filter_current_list)
    win.search_box.textChanged.connect(lambda _texto: win._search_debounce.start())
    # En la captura, los cuatro controles en una sola fila se cortaban
    # al reducir el catálogo. La búsqueda va en su propia fila y los
    # filtros debajo; las tres opciones inferiores ya caben incluso en
    # el ancho mínimo del panel central.
    filters_row.addWidget(win.search_box)
    filters_row.addLayout(filter_options_row)

    bar.addLayout(title_row)
    bar.addLayout(filters_row)
    return bar


def on_catalog_sort_changed(win) -> None:
    current = win.stack.currentWidget() if hasattr(win, "stack") else None
    if current not in (getattr(win, "tv_list", None), getattr(win, "radio_list", None)):
        return
    kind = "tv" if current is win.tv_list else "radio"
    win.settings[f"catalog_sort_{kind}"] = win.catalog_sort.currentData() or "source"
    cfg.save_settings(win.settings)
    win.lists.sort_catalog(current)


def toggle_grid_view(win, checked: bool) -> None:
    """
    Alterna TV y Radio entre filas y cuadrícula de tarjetas. Favoritos
    e historial conservan el modo lista porque contienen tipos mezclados
    y, en el caso de favoritos, admiten reordenación mediante arrastre.
    """
    for catalog in (win.tv_list, win.radio_list):
        if checked:
            catalog.setItemDelegate(win.grid_delegate)
            catalog.setViewMode(QListWidget.IconMode)
            catalog.setFlow(QListWidget.LeftToRight)
            catalog.setResizeMode(QListWidget.Adjust)
            catalog.setMovement(QListWidget.Static)
            catalog.setSpacing(4)
            catalog.setGridSize(QSize(
                ChannelGridDelegate.CARD_SIZE,
                ChannelGridDelegate.CARD_SIZE,
            ))
        else:
            catalog.setItemDelegate(win.delegate)
            catalog.setViewMode(QListWidget.ListMode)
            catalog.setFlow(QListWidget.TopToBottom)
            catalog.setMovement(QListWidget.Static)
            catalog.setSpacing(0)
            catalog.setGridSize(QSize())

    if checked:
        # BG_ROOT (oscuro) cuando está marcado, porque :checked pone de
        # fondo el color de acento claro -- mismo criterio que ya usan
        # los botones del riel de navegación (ver nav_icon_builders).
        win.tv_view_toggle.setIcon(app_icons.icon_list_view(palette.BG_ROOT))
        win.tv_view_toggle.setToolTip("Ver catálogo en lista")
    else:
        win.tv_view_toggle.setIcon(app_icons.icon_grid_view(palette.TEXT_DIM))
        win.tv_view_toggle.setToolTip("Ver catálogo en cuadrícula")

    win.settings["catalog_grid_view"] = bool(checked)
    cfg.save_settings(win.settings)
    win.tv_list.viewport().update()
    win.radio_list.viewport().update()
