"""
Cambio de sección de la barra de navegación superior (Inicio/TV/Radio/
Favoritos/Historial/Descargas): persiste y restaura los filtros de catálogo por
sección, actualiza la visibilidad de los controles de la barra superior,
y anima la transición de página.

Extraído de ui/main_window.py por el mismo motivo que el resto de
controladores (ver ui/playback_controller.py).

Coder By X@R
"""
from PySide6.QtCore import QEasingCurve, QPropertyAnimation
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget

from core import config as cfg
from ui.nav_sections import (
    NAV_DOWNLOAD, NAV_FAV, NAV_HOME, NAV_RADIO, NAV_TV, SECTION_TITLES,
    SECTION_VARIANTS,
)
from ui.visual import set_variant


class NavigationController:
    """Cambio de sección de MainWindow (win.navigation)."""

    def __init__(self, window):
        self.win = window

    def on_nav_changed(self, nav_id: int):
        win = self.win
        if nav_id == NAV_DOWNLOAD:
            if win.es_version_free:
                return
            win._ensure_download_panel()
        previous_nav = win._current_nav_id
        if previous_nav in (NAV_TV, NAV_RADIO):
            kind = "tv" if previous_nav == NAV_TV else "radio"
            filters = dict(win.settings.get("catalog_filters") or {})
            # El filtro de categoría de TV ahora lo lleva GroupsSidebar (panel
            # lateral), no el desplegable group_filter -- se guarda como una
            # lista de nombres de grupo (antes era un único string de
            # group_filter.currentText(), de ahí el nombre de la clave).
            if previous_nav == NAV_TV and win._tv_sidebar_groups:
                group_state = sorted(win._tv_sidebar_groups)
            else:
                group_state = []
            filters[kind] = {
                "search": win.search_box.text(),
                "group": group_state,
                "health": win.health_filter.currentData() or "all",
            }
            win.settings["catalog_filters"] = filters
            cfg.save_settings(win.settings)

        win._current_nav_id = nav_id
        win.stack.setCurrentIndex(nav_id)
        win.section_title.setText(SECTION_TITLES[nav_id])
        win.section_title.setStyleSheet("")
        set_variant(win.section_title, SECTION_VARIANTS[nav_id])
        win.catalog.update_catalog_count()
        win.epg_btn.setVisible(nav_id == NAV_TV)
        win.tv_view_toggle.setVisible(nav_id in (NAV_TV, NAV_RADIO))
        # group_filter ya no se usa para TV -- lo sustituye groups_sidebar
        # (panel lateral con contador por grupo). Sigue siendo el filtro de
        # carpeta en Favoritos.
        win.group_filter.setVisible(nav_id == NAV_FAV)
        win.groups_sidebar.setVisible(nav_id == NAV_TV)
        win.catalog_sort.setVisible(nav_id in (NAV_TV, NAV_RADIO))
        win.health_filter.setVisible(nav_id in (NAV_TV, NAV_RADIO))
        if nav_id == NAV_TV:
            win.lists.refresh_group_filter()
            sort_key = win.settings.get("catalog_sort_tv", "source")
            win.catalog_sort.blockSignals(True)
            win.catalog_sort.setCurrentIndex(max(0, win.catalog_sort.findData(sort_key)))
            win.catalog_sort.blockSignals(False)
        elif nav_id == NAV_FAV:
            win.lists.refresh_folder_filter()
        elif nav_id == NAV_RADIO:
            sort_key = win.settings.get("catalog_sort_radio", "source")
            win.catalog_sort.blockSignals(True)
            win.catalog_sort.setCurrentIndex(max(0, win.catalog_sort.findData(sort_key)))
            win.catalog_sort.blockSignals(False)
        elif nav_id == NAV_HOME:
            win.home.refresh_home_page()
        win.search_box.setVisible(nav_id not in (NAV_DOWNLOAD, NAV_HOME))
        if nav_id in (NAV_TV, NAV_RADIO):
            kind = "tv" if nav_id == NAV_TV else "radio"
            state = (win.settings.get("catalog_filters") or {}).get(kind, {})
            win.search_box.blockSignals(True)
            win.search_box.setText(state.get("search", ""))
            win.search_box.blockSignals(False)
            health_index = win.health_filter.findData(state.get("health", "all"))
            win.health_filter.blockSignals(True)
            win.health_filter.setCurrentIndex(max(0, health_index))
            win.health_filter.blockSignals(False)
            if nav_id == NAV_TV and state.get("group"):
                # state["group"] es una lista de nombres de grupo (ver el
                # guardado más arriba); refresh_group_filter() ya pobló
                # groups_sidebar justo antes, así que aquí solo hace falta
                # restaurar qué filas quedan seleccionadas.
                win._tv_sidebar_groups = set(state["group"])
                win.groups_sidebar.select_groups(win._tv_sidebar_groups)
        else:
            win.search_box.clear()
        if nav_id not in (NAV_DOWNLOAD, NAV_HOME):
            win.lists.filter_current_list()
        if nav_id == NAV_TV:
            win.lists.load_visible_logos(win.tv_list)
        elif nav_id == NAV_RADIO:
            win.lists.load_visible_logos(win.radio_list)
        elif nav_id == NAV_FAV:
            win.lists.load_visible_logos(win.fav_list)
        self.animate_page(win.stack.currentWidget())

    def animate_page(self, widget: QWidget):
        win = self.win
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", win)
        anim.setDuration(220)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.finished.connect(lambda: widget.setGraphicsEffect(None))
        anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
        win._fade_anim = anim
