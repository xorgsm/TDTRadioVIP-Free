"""
Controlador de listas de TDT & Radio VIP: poblar y refrescar las listas de
TV, radio, favoritos e historial, el filtro de categoría/carpeta y la
búsqueda por texto.

Extraído de ui/main_window.py por el mismo motivo que
ui.playback_controller.PlaybackController y ui.window_chrome.WindowChrome —
ver el docstring de PlaybackController para la explicación completa del
porqué del patrón (estado en MainWindow, comportamiento aquí). Antes esta
lógica de "pintar filas en las listas" vivía mezclada, en la misma clase,
con la reproducción, el cromado de ventana y el resto de secciones.

Coder By X@R
"""
from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QListWidget, QListWidgetItem

from core import channels as tv_channels
from core import epg as epg_module
from core import favorites as fav_store
from core import radio as radio_stations
from core.stream_health_store import StreamHealthStore, is_health_stale, matches_health_filter
from ui.channel_model import ChannelListView
from ui.widgets import (
    ROLE_CUSTOM, ROLE_DATA, ROLE_FAV, ROLE_HEALTH, ROLE_LOGO, ROLE_LOGO_REQUESTED,
    ROLE_PLAYING, ChannelDelegate,
)


def _health_tooltip(health: dict | None) -> str:
    """Tooltip de una fila de TV/Radio con su último diagnóstico, o "" si
    nunca se ha diagnosticado."""
    if not health:
        return ""
    return (
        f"Último diagnóstico: {health.get('checked_at', 'desconocido')} · "
        f"{health.get('latency_ms', 0)} ms"
    )


class ChannelListsController:
    """Poblado, refresco, filtro y búsqueda de las listas de canales."""

    def __init__(self, window):
        self.win = window

    # ---------- Logos ----------

    def request_logo(self, url: str, item: QListWidgetItem, list_widget: QListWidget):
        if not url:
            return

        def _on_ready(pixmap):
            item.setData(ROLE_LOGO, pixmap)
            # No se repinta toda la lista por cada logo: con catálogos de
            # miles de entradas eso convertía una cola de red controlada en
            # miles de repintados completos. Las filas fuera de pantalla se
            # redibujan solas al hacer scroll, así que solo actualizamos la
            # parte visible que acaba de recibir su imagen.
            rect = list_widget.visualItemRect(item)
            if rect.isValid() and rect.intersects(list_widget.viewport().rect()):
                list_widget.viewport().update(rect)

        self.win.logo_loader.load(url, _on_ready, size=ChannelDelegate.LOGO_SIZE)

    def load_visible_logos(self, list_widget: QListWidget) -> None:
        """Solicita solo los logos de las filas actualmente visibles."""
        if not list_widget.isVisible() or not list_widget.count():
            return

        if isinstance(list_widget, ChannelListView):
            visible = self._visible_row_range(list_widget)
        else:
            visible = self._visible_row_range_by_corners(list_widget)
        if visible is None:
            return
        first, last = visible
        for row in range(first, last + 1):
            item = list_widget.item(row)
            data = item.data(ROLE_DATA) or {}
            url = data.get("logo", "")
            if not url or item.data(ROLE_LOGO_REQUESTED):
                continue
            item.setData(ROLE_LOGO_REQUESTED, True)
            self.request_logo(url, item, list_widget)

    @staticmethod
    def _visible_row_range(view: ChannelListView) -> tuple[int, int] | None:
        """Primera y última fila que se ven en un catálogo de TV/radio.

        No se miran las esquinas con indexAt(): en cuadrícula caen en el
        margen entre tarjetas o tras la última columna, y en una lista más
        corta que la pantalla la esquina inferior cae en el hueco tras la
        última fila -- en esos casos no se pedía ningún logo. Las filas de
        ChannelListView van en orden de arriba abajo en ambos modos (y el
        modelo no tiene filas ocultas: las filtradas ni existen), así que
        basta una búsqueda binaria sobre su rectángulo en pantalla.
        """
        model = view.model()
        count = view.count()
        height = view.viewport().height()

        def rect(row):
            return view.visualRect(model.index(row, 0))

        lo, hi = 0, count               # primera fila cuyo borde inferior asoma
        while lo < hi:
            mid = (lo + hi) // 2
            if rect(mid).bottom() < 0:
                lo = mid + 1
            else:
                hi = mid
        first = lo
        lo, hi = first, count           # primera fila que empieza por debajo
        while lo < hi:
            mid = (lo + hi) // 2
            if rect(mid).top() < height:
                lo = mid + 1
            else:
                hi = mid
        last = lo - 1
        return (first, last) if first <= last else None

    @staticmethod
    def _visible_row_range_by_corners(list_widget: QListWidget) -> tuple[int, int] | None:
        """Lo mismo para favoritos/historial (QListWidget, siempre en modo
        lista, con filas ocultas por el filtro): las esquinas bastan, salvo
        que la inferior caiga en el hueco tras la última fila (lista más
        corta que la pantalla) -- entonces la última visible es la última."""
        top = list_widget.indexAt(QPoint(0, 0))
        if not top.isValid():
            return None
        bottom = list_widget.indexAt(
            QPoint(
                max(0, list_widget.viewport().width() - 1),
                max(0, list_widget.viewport().height() - 1),
            )
        )
        last = bottom.row() if bottom.isValid() else list_widget.count() - 1
        return max(0, top.row()), min(list_widget.count() - 1, last)

    def _epg_now_text(self, tvg_id: str) -> str:
        """
        "Ahora: <programa>" para el mini-EPG de cada fila de la lista de TV,
        o "" si no hay guía cargada todavía, el canal no trae tvg_id, o no
        hay programación en curso para él en este momento. Usa la guía ya
        en memoria (win.epg_guide) -- sin red aquí, esa la hace
        EpgController.load() aparte.
        """
        win = self.win
        if not win.epg_guide or not tvg_id:
            return ""
        current, _ = epg_module.get_now_next(win.epg_guide, tvg_id)
        return f"Ahora: {current.title}" if current else ""

    @staticmethod
    def _health_by_stream() -> dict[tuple[str, str], dict]:
        """Lee una vez el historial persistente para poblar ambas listas."""
        try:
            return {
                (entry["kind"], entry["url"]): entry
                for entry in StreamHealthStore().list()
            }
        except OSError:
            return {}

    # ---------- Poblado de listas ----------

    def populate_tv_list(self, channels_list):
        win = self.win
        custom_names = {c.name for c in tv_channels.load_custom_channels()}
        favorite_keys = {(f.get("type"), f.get("name")) for f in win.favorites}
        health_by_stream = self._health_by_stream()
        entries = []
        for ch in channels_list:
            # Subtítulo combinado: categoría + mini-EPG ("Ahora: ...") cuando
            # hay guía cargada, uno solo de los dos si falta el otro (ver
            # ChannelDelegate.paint, que prioriza "subtitle" sobre "group";
            # el punto de color de la categoría sale de "group").
            epg_now = self._epg_now_text(ch.tvg_id)
            subtitle = f"{ch.group} · {epg_now}" if ch.group and epg_now else (epg_now or ch.group)
            data = {
                "type": "tv", "name": ch.name, "url": ch.url,
                "logo": ch.logo, "tvg_id": ch.tvg_id, "group": ch.group,
                "subtitle": subtitle, "alternate_urls": ch.alternate_urls,
            }
            health = health_by_stream.get(("tv", ch.url))
            if health:
                data["health_checked_at"] = health.get("checked_at", "")
            entries.append({
                ROLE_DATA: data,
                ROLE_FAV: ("tv", ch.name) in favorite_keys,
                ROLE_PLAYING: win.current_type == "tv" and win.current_name == ch.name,
                ROLE_CUSTOM: ch.name in custom_names,
                ROLE_HEALTH: health.get("status") if health else None,
                Qt.ToolTipRole: _health_tooltip(health),
            })
        win.tv_list.model().set_entries(entries)
        self.sort_catalog(win.tv_list)
        self.load_visible_logos(win.tv_list)

    def populate_radio_list(self, stations_list):
        win = self.win
        custom_names = {s.name for s in radio_stations.load_custom_stations()}
        favorite_keys = {(f.get("type"), f.get("name")) for f in win.favorites}
        health_by_stream = self._health_by_stream()
        entries = []
        for st in stations_list:
            subtitle = f"{st.bitrate} kbps" if st.bitrate else (st.tags or "")
            data = {
                "type": "radio", "name": st.name, "url": st.url,
                "logo": st.favicon, "subtitle": subtitle,
                "alternate_urls": st.alternate_urls,
            }
            health = health_by_stream.get(("radio", st.url))
            if health:
                data["health_checked_at"] = health.get("checked_at", "")
            entries.append({
                ROLE_DATA: data,
                ROLE_FAV: ("radio", st.name) in favorite_keys,
                ROLE_PLAYING: win.current_type == "radio" and win.current_name == st.name,
                ROLE_CUSTOM: st.name in custom_names,
                ROLE_HEALTH: health.get("status") if health else None,
                Qt.ToolTipRole: _health_tooltip(health),
            })
        win.radio_list.model().set_entries(entries)
        self.sort_catalog(win.radio_list)
        self.load_visible_logos(win.radio_list)

    def update_stream_health(self, health_entries) -> None:
        """Actualiza solo las filas afectadas por un diagnóstico terminado."""
        health_by_stream = {
            (entry.get("kind"), entry.get("url")): entry
            for entry in health_entries
        }
        if not health_by_stream:
            return

        for kind, list_widget in (("tv", self.win.tv_list), ("radio", self.win.radio_list)):
            def update_entry(item, entry_kind=kind):
                data = item.get(ROLE_DATA) or {}
                health = health_by_stream.get((entry_kind, data.get("url")))
                if health is None:
                    return False
                item[ROLE_HEALTH] = health.get("status")
                data["health_checked_at"] = health.get("checked_at", "")
                item[ROLE_DATA] = data
                item[Qt.ToolTipRole] = _health_tooltip(health)
                return True

            list_widget.model().update_entries(update_entry)

    def update_epg_subtitles(self) -> None:
        """Actualiza el "Ahora: <programa>" de cada fila de TV cuando la
        guía EPG termina de cargar, sin repoblar la lista entera (ver
        EpgController._on_loaded). Repoblar (como se hacía antes) recreaba
        todos los QListWidgetItem, volvía a ordenar la lista entera y
        volvía a encolar el logo de cada canal -- con catálogos de varios
        cientos de canales, esa reconstrucción completa apilada justo
        detrás del poblado inicial (load_tv_channels/load_radio_stations/
        epg.load() se lanzan casi a la vez al arrancar, ver
        MainWindow.__init__) era la que se notaba como lentitud/bloqueo al
        cargar. Mismo patrón que update_stream_health(): solo se toca el
        dato que de verdad cambió (aquí, el subtítulo) en las filas ya
        existentes.
        """
        def update_entry(item):
            data = item.get(ROLE_DATA) or {}
            epg_now = self._epg_now_text(data.get("tvg_id", ""))
            group = data.get("group") or ""
            subtitle = f"{group} · {epg_now}" if group and epg_now else (epg_now or group)
            if data.get("subtitle") == subtitle:
                return False
            data["subtitle"] = subtitle
            item[ROLE_DATA] = data
            return True

        self.win.tv_list.model().update_entries(update_entry)

    def sort_catalog(self, list_widget: QListWidget):
        """Ordena el catálogo de TV/Radio según el ajuste catalog_sort_*.

        Reordena las entradas del modelo sin recrearlas, así que cada fila
        conserva su logo ya cargado. El canal activo no necesita reajuste:
        PlaybackController._active_row_now() lo busca en el momento de usarlo.
        """
        win = self.win
        if list_widget not in (win.tv_list, win.radio_list):
            return
        kind = "tv" if list_widget is win.tv_list else "radio"
        mode = win.settings.get(f"catalog_sort_{kind}", "source")
        if mode == "source":
            # populate_* ya añade las entradas en el mismo orden que los
            # datos fuente: no hay nada que reordenar en el caso
            # predeterminado de la aplicación.
            return
        if mode == "favorites":
            def key(entry):
                data = entry.get(ROLE_DATA) or {}
                return (not bool(entry.get(ROLE_FAV)), data.get("name", "").casefold())
        else:
            def key(entry):
                return (entry.get(ROLE_DATA) or {}).get("name", "").casefold()
        list_widget.model().sort_entries(key)
        self.load_visible_logos(list_widget)

    def refresh_favorites_tab(self):
        win = self.win
        win.fav_list.clear()
        custom_tv = {c.name for c in tv_channels.load_custom_channels()}
        custom_radio = {s.name for s in radio_stations.load_custom_stations()}
        for fav in win.favorites:
            item = QListWidgetItem()
            data = dict(fav)
            # Reutiliza el mismo mecanismo visual de "categoría" que ya
            # tienen las tarjetas de TV (punto de color + texto) para
            # mostrar la carpeta del favorito, en vez de inventar un
            # indicador nuevo.
            data["group"] = fav.get("folder", "")
            item.setData(ROLE_DATA, data)
            item.setData(ROLE_FAV, True)
            item.setData(ROLE_PLAYING, win.current_type == fav["type"] and win.current_name == fav["name"])
            is_custom = fav["name"] in (custom_tv if fav["type"] == "tv" else custom_radio)
            item.setData(ROLE_CUSTOM, is_custom)
            win.fav_list.addItem(item)

        self.load_visible_logos(win.fav_list)

        sidebar = getattr(win, "library_sidebar", None)
        if sidebar is not None:
            sidebar.refresh()

    def refresh_history_tab(self):
        win = self.win
        win.hist_list.clear()
        custom_tv = {c.name for c in tv_channels.load_custom_channels()}
        custom_radio = {s.name for s in radio_stations.load_custom_stations()}
        for entry in win.history:
            item = QListWidgetItem()
            data = dict(entry)
            data["subtitle"] = entry.get("timestamp", "")
            item.setData(ROLE_DATA, data)
            item.setData(ROLE_FAV, fav_store.is_favorite(win.favorites, entry["type"], entry["name"]))
            item.setData(ROLE_PLAYING, win.current_type == entry["type"] and win.current_name == entry["name"])
            is_custom = entry["name"] in (custom_tv if entry["type"] == "tv" else custom_radio)
            item.setData(ROLE_CUSTOM, is_custom)
            win.hist_list.addItem(item)

        sidebar = getattr(win, "library_sidebar", None)
        if sidebar is not None:
            sidebar.refresh()

    def persist_favorites_order(self):
        """
        Llamado tras arrastrar una fila en la pestaña de Favoritos
        (QListWidget.InternalMove, ver ui/main_window._make_list). Relee el
        orden visual actual de win.fav_list y lo guarda como el nuevo orden
        de win.favorites -- así el arrastre sobrevive a cerrar y reabrir la
        app, no es solo un reordenado visual de la sesión actual.
        """
        win = self.win
        vistos = set()
        nuevo_orden = []
        favorites_by_key = {
            (f.get("type"), f.get("name")): f
            for f in win.favorites
        }
        for i in range(win.fav_list.count()):
            data = win.fav_list.item(i).data(ROLE_DATA) or {}
            clave = (data.get("type"), data.get("name"))
            original = favorites_by_key.get(clave)
            if original is not None and clave not in vistos:
                nuevo_orden.append(original)
                vistos.add(clave)
        # Red de seguridad: cualquier favorito que por lo que sea no haya
        # aparecido en la lista visual (no debería pasar) se añade al
        # final en vez de perderse silenciosamente.
        for f in win.favorites:
            clave = (f.get("type"), f.get("name"))
            if clave not in vistos:
                nuevo_orden.append(f)
                vistos.add(clave)

        win.favorites = fav_store.reorder(nuevo_orden)

    def mark_playing_everywhere(self):
        win = self.win
        # Los 4 carruseles de Inicio (home_recent_carousel,
        # home_on_air_carousel, home_recommended_carousel,
        # home_fav_carousel) no entran en este bucle: son CarouselCard
        # (ui/carousel.py), no QListWidgetItem con ROLE_PLAYING -- no
        # llevan indicador de "sonando ahora" propio, se limitan a
        # repoblarse cada vez que se entra en Inicio.
        for lst in (win.tv_list, win.radio_list, win.fav_list, win.hist_list):
            if isinstance(lst, ChannelListView):
                def update_entry(item):
                    data = item.get(ROLE_DATA) or {}
                    is_playing = (
                        data.get("type") == win.current_type
                        and data.get("name") == win.current_name
                        and not win._playback_failed
                    )
                    if bool(item.get(ROLE_PLAYING)) == is_playing:
                        return False
                    item[ROLE_PLAYING] = is_playing
                    return True

                lst.model().update_entries(update_entry)
                continue
            for i in range(lst.count()):
                item = lst.item(i)
                data = item.data(ROLE_DATA) or {}
                is_current = data.get("type") == win.current_type and data.get("name") == win.current_name
                item.setData(ROLE_PLAYING, is_current and not win._playback_failed)
            lst.viewport().update()

    def mark_favorites_everywhere(self):
        win = self.win
        favorite_keys = {(f.get("type"), f.get("name")) for f in win.favorites}
        for lst in (win.tv_list, win.radio_list, win.hist_list):
            if isinstance(lst, ChannelListView):
                def update_entry(item):
                    data = item.get(ROLE_DATA) or {}
                    is_favorite = (data.get("type"), data.get("name")) in favorite_keys
                    if bool(item.get(ROLE_FAV)) == is_favorite:
                        return False
                    item[ROLE_FAV] = is_favorite
                    return True

                lst.model().update_entries(update_entry)
                continue
            for i in range(lst.count()):
                item = lst.item(i)
                data = item.data(ROLE_DATA) or {}
                item.setData(ROLE_FAV, (data.get("type"), data.get("name")) in favorite_keys)
            lst.viewport().update()

    # ---------- Filtros de categoría / carpeta ----------

    def refresh_folder_filter(self):
        win = self.win
        carpetas = fav_store.get_folders(win.favorites)
        current = win.group_filter.currentText()
        win.group_filter.blockSignals(True)
        win.group_filter.clear()
        win.group_filter.addItem("Todas las carpetas")
        if carpetas:
            win.group_filter.addItem("Sin carpeta")
            win.group_filter.addItems(carpetas)
        idx = win.group_filter.findText(current)
        win.group_filter.setCurrentIndex(idx if idx >= 0 else 0)
        win.group_filter.blockSignals(False)

    def refresh_group_filter(self):
        win = self.win
        groups = sorted({c.group for c in win.tv_channels_data if c.group})
        current = win.group_filter.currentText()
        win.group_filter.blockSignals(True)
        win.group_filter.clear()
        win.group_filter.addItem("Todas las categorías")
        win.group_filter.addItems(groups)
        idx = win.group_filter.findText(current)
        win.group_filter.setCurrentIndex(idx if idx >= 0 else 0)
        win.group_filter.blockSignals(False)

        # GroupsSidebar (panel lateral con contador por grupo, ver
        # ui/groups_sidebar.py) es ahora el filtro de categoría real para
        # TV -- group_filter de arriba se deja poblado pero oculto durante
        # esa sección (ver ui.navigation_controller.NavigationController.on_nav_changed).
        sidebar = getattr(win, "groups_sidebar", None)
        if sidebar is not None:
            counts = {}
            for c in win.tv_channels_data:
                if c.group:
                    counts[c.group] = counts.get(c.group, 0) + 1
            sidebar.set_groups(counts)
            # Releer la selección real tras el refresco: set_groups() puede
            # haber tenido que caer a "(Todos)" si algún grupo antes
            # marcado ya no existe (p.ej. se borró ese grupo) -- así
            # win._tv_sidebar_groups nunca queda desincronizado del panel.
            win._tv_sidebar_groups = sidebar.current_selection()

    # ---------- Filtro / búsqueda ----------

    def filter_current_list(self):
        win = self.win
        current_widget = win.stack.currentWidget()
        text = win.search_box.text().strip().lower()
        if isinstance(current_widget, ChannelListView):
            self._filter_catalog(current_widget, text)
        elif isinstance(current_widget, QListWidget):
            self._filter_library_list(current_widget, text)
        else:
            return
        self.load_visible_logos(current_widget)

    def _filter_catalog(self, view: ChannelListView, text: str) -> None:
        """TV/Radio: texto, estado de salud y, en TV, los grupos marcados en
        GroupsSidebar (el panel lateral lleva el filtro de categoría de TV,
        no el desplegable group_filter -- ver refresh_group_filter())."""
        win = self.win
        health_key = win.health_filter.currentData() or "all"
        sidebar_groups = getattr(win, "_tv_sidebar_groups", None) if view is win.tv_list else None

        def matches(entry):
            data = entry.get(ROLE_DATA) or {}
            if text not in data.get("name", "").lower():
                return False
            if sidebar_groups is not None and data.get("group") not in sidebar_groups:
                return False
            if health_key == "stale":
                return is_health_stale(data.get("health_checked_at"))
            return matches_health_filter(entry.get(ROLE_HEALTH), health_key)

        view.model().set_filter(matches)

    def _filter_library_list(self, list_widget: QListWidget, text: str) -> None:
        """Favoritos/historial: texto y, en favoritos, la carpeta elegida en
        group_filter. Sus filas no llevan diagnóstico, así que el filtro de
        salud no se aplica."""
        win = self.win
        folder = win.group_filter.currentText() if list_widget is win.fav_list else None
        # setUpdatesEnabled(False): esto se ejecuta en CADA pulsación de
        # tecla en el buscador (search_box.textChanged está conectado
        # directo a este método). Sin cortar los repintados, cada
        # setHidden() de abajo puede disparar un recálculo del layout
        # visible de la lista.
        list_widget.setUpdatesEnabled(False)
        try:
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                data = item.data(ROLE_DATA) or {}
                visible = text in data.get("name", "").lower()
                if folder == "Sin carpeta":
                    visible = visible and not data.get("group")
                elif folder not in (None, "Todas las carpetas"):
                    visible = visible and data.get("group") == folder
                item.setHidden(not visible)
        finally:
            list_widget.setUpdatesEnabled(True)
