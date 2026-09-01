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
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QListWidget, QListWidgetItem

from core import channels as tv_channels
from core import epg as epg_module
from core import favorites as fav_store
from core import radio as radio_stations
from core.stream_health_store import StreamHealthStore, is_health_stale, matches_health_filter
from ui.widgets import (
    ROLE_CUSTOM, ROLE_DATA, ROLE_FAV, ROLE_HEALTH, ROLE_LOGO, ROLE_PLAYING, ChannelDelegate,
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
        health_by_stream = self._health_by_stream()
        # setUpdatesEnabled(False): con listas grandes (importar un M3U de
        # varios miles de canales, o simplemente un país con muchos canales)
        # cada addItem() por separado repintaba y recalculaba el layout de
        # la lista una a una -- con miles de canales eso es lo que se veía
        # como "se pone lento y se cuelga la app" (reportado). Cortando los
        # repintados hasta que la lista entera está poblada, Qt hace un
        # único repintado al final en vez de miles.
        win.tv_list.setUpdatesEnabled(False)
        pending_logos = []
        try:
            win.tv_list.clear()
            for ch in channels_list:
                item = QListWidgetItem()
                # Subtítulo combinado: categoría + mini-EPG ("Ahora: ...")
                # cuando hay guía cargada, uno solo de los dos si falta el
                # otro (ver ChannelDelegate.paint, que ahora prioriza
                # "subtitle" sobre "group" para decidir qué texto pintar --
                # el punto de color de la categoría se sigue dibujando por
                # separado a partir de "group", no cambia).
                epg_now = self._epg_now_text(ch.tvg_id)
                if ch.group and epg_now:
                    subtitle = f"{ch.group} · {epg_now}"
                else:
                    subtitle = epg_now or ch.group
                item.setData(ROLE_DATA, {
                    "type": "tv", "name": ch.name, "url": ch.url,
                    "logo": ch.logo, "tvg_id": ch.tvg_id, "group": ch.group,
                    "subtitle": subtitle, "alternate_urls": ch.alternate_urls,
                })
                item.setData(ROLE_FAV, fav_store.is_favorite(win.favorites, "tv", ch.name))
                item.setData(ROLE_PLAYING, win.current_type == "tv" and win.current_name == ch.name)
                item.setData(ROLE_CUSTOM, ch.name in custom_names)
                health = health_by_stream.get(("tv", ch.url))
                item.setData(ROLE_HEALTH, health.get("status") if health else None)
                data = item.data(ROLE_DATA)
                data["health_checked_at"] = health.get("checked_at", "") if health else ""
                item.setData(ROLE_DATA, data)
                if health:
                    item.setToolTip(
                        f"Último diagnóstico: {health.get('checked_at', 'desconocido')} · "
                        f"{health.get('latency_ms', 0)} ms"
                    )
                win.tv_list.addItem(item)
                if ch.logo:
                    pending_logos.append((ch.logo, item))
        finally:
            win.tv_list.setUpdatesEnabled(True)
        self.sort_catalog(win.tv_list)
        # Ver _queue_logo_batch: incluso con el logo ya en caché en disco,
        # pedirlo implica leer el archivo y decodificarlo -- con catálogos
        # de decenas de miles de canales, hacer eso de golpe para todos en
        # el mismo bucle era lo que congelaba la app ("no responde").
        self._queue_logo_batch(pending_logos, win.tv_list)

    def populate_radio_list(self, stations_list):
        win = self.win
        custom_names = {s.name for s in radio_stations.load_custom_stations()}
        health_by_stream = self._health_by_stream()
        win.radio_list.setUpdatesEnabled(False)  # ver comentario en populate_tv_list
        pending_logos = []
        try:
            win.radio_list.clear()
            for st in stations_list:
                item = QListWidgetItem()
                subtitle = f"{st.bitrate} kbps" if st.bitrate else (st.tags or "")
                item.setData(ROLE_DATA, {
                    "type": "radio", "name": st.name, "url": st.url,
                    "logo": st.favicon, "subtitle": subtitle,
                    "alternate_urls": st.alternate_urls,
                })
                item.setData(ROLE_FAV, fav_store.is_favorite(win.favorites, "radio", st.name))
                item.setData(ROLE_PLAYING, win.current_type == "radio" and win.current_name == st.name)
                item.setData(ROLE_CUSTOM, st.name in custom_names)
                health = health_by_stream.get(("radio", st.url))
                item.setData(ROLE_HEALTH, health.get("status") if health else None)
                data = item.data(ROLE_DATA)
                data["health_checked_at"] = health.get("checked_at", "") if health else ""
                item.setData(ROLE_DATA, data)
                if health:
                    item.setToolTip(
                        f"Último diagnóstico: {health.get('checked_at', 'desconocido')} · "
                        f"{health.get('latency_ms', 0)} ms"
                    )
                win.radio_list.addItem(item)
                if st.favicon:
                    pending_logos.append((st.favicon, item))
        finally:
            win.radio_list.setUpdatesEnabled(True)
        self.sort_catalog(win.radio_list)
        self._queue_logo_batch(pending_logos, win.radio_list)

    def update_stream_health(self, health_entries) -> None:
        """Actualiza solo las filas afectadas por un diagnóstico terminado."""
        health_by_stream = {
            (entry.get("kind"), entry.get("url")): entry
            for entry in health_entries
        }
        if not health_by_stream:
            return

        for kind, list_widget in (("tv", self.win.tv_list), ("radio", self.win.radio_list)):
            list_widget.setUpdatesEnabled(False)
            try:
                for index in range(list_widget.count()):
                    item = list_widget.item(index)
                    data = item.data(ROLE_DATA) or {}
                    health = health_by_stream.get((kind, data.get("url")))
                    if health is None:
                        continue
                    item.setData(ROLE_HEALTH, health.get("status"))
                    data["health_checked_at"] = health.get("checked_at", "")
                    item.setData(ROLE_DATA, data)
                    item.setToolTip(
                        f"Último diagnóstico: {health.get('checked_at', 'desconocido')} · "
                        f"{health.get('latency_ms', 0)} ms"
                    )
            finally:
                list_widget.setUpdatesEnabled(True)

    def _queue_logo_batch(self, pending, list_widget, batch_size=150):
        """
        Pide los logos en tandas pequeñas con QTimer.singleShot(0, ...) en
        vez de las miles que hicieran falta de golpe, todas dentro del
        mismo bucle que puebla la lista. Aunque el logo ya esté en la
        caché de disco, cargarlo implica leer el archivo, decodificarlo y
        redondearle la esquina (rounded_pixmap) -- con un catálogo de
        decenas de miles de canales, hacer eso uno detrás de otro sin
        ceder nunca el hilo de la interfaz es lo que la congela del todo
        ("no responde"). Troceado en tandas, Qt puede seguir pintando y
        atendiendo la ventana entre tanda y tanda: los logos tardan un
        poco más en verse todos, pero la interfaz no se bloquea mientras
        tanto.

        Los QListWidgetItem de `pending` pueden dejar de existir antes de
        que le toque el turno a su tanda (el usuario cambia de sección,
        se repuebla la lista, etc.) -- request_logo() accede a ellos, así
        que cada uno se protege por separado en vez de dejar que un solo
        ítem ya borrado interrumpa el resto de la tanda.
        """
        if not pending:
            return
        lote, resto = pending[:batch_size], pending[batch_size:]
        for url, item in lote:
            try:
                self.request_logo(url, item, list_widget)
            except RuntimeError:
                continue  # el ítem ya no existe (lista repoblada mientras esperaba turno)
        if resto:
            QTimer.singleShot(0, lambda: self._queue_logo_batch(resto, list_widget, batch_size))

    def sort_catalog(self, list_widget: QListWidget):
        """Ordena TV/Radio conservando cada QListWidgetItem y su logo."""
        win = self.win
        if list_widget not in (win.tv_list, win.radio_list):
            return
        kind = "tv" if list_widget is win.tv_list else "radio"
        mode = win.settings.get(f"catalog_sort_{kind}", "source")
        if mode == "source":
            source = win.tv_channels_data if kind == "tv" else win.radio_stations_data
            source_order = {
                (entry.name.strip().casefold(), entry.url): index
                for index, entry in enumerate(source)
            }

            def key(item):
                data = item.data(ROLE_DATA) or {}
                return source_order.get(
                    (data.get("name", "").strip().casefold(), data.get("url", "")),
                    len(source_order),
                )
        elif mode == "favorites":
            def key(item):
                data = item.data(ROLE_DATA) or {}
                return (not bool(item.data(ROLE_FAV)), data.get("name", "").casefold())
        else:
            def key(item):
                return (item.data(ROLE_DATA) or {}).get("name", "").casefold()

        active_item = None
        if win._active_list is list_widget and 0 <= win._active_row < list_widget.count():
            active_item = list_widget.item(win._active_row)
        # setUpdatesEnabled(False): igual que en populate_tv_list/
        # populate_radio_list, pero aquí era todavía más grave -- sin esto,
        # cada una de las N llamadas a takeItem()/addItem() de abajo
        # repinta y recalcula el layout de la lista visible (con el
        # delegado personalizado de por medio), así que ordenar un
        # catálogo de varios cientos/miles de canales costaba, de facto, N
        # repintados completos en vez de uno solo al final. Con listas
        # grandes esto por sí solo explicaba minutos de "no responde" en
        # cada arranque/cambio de sección.
        list_widget.setUpdatesEnabled(False)
        try:
            # takeItem(0) por cada canal (como hacía esto antes) es
            # engañoso: aunque el bucle sea "solo" N vueltas, QListWidget
            # guarda las filas en un array por dentro, así que quitar
            # SIEMPRE la primera implica desplazar todas las que quedan
            # detrás una posición -- son N desplazamientos en la primera
            # vuelta, N-1 en la segunda... O(N²) en total. Con 500 canales
            # (250.000 desplazamientos) no se notaba; con 3.500 (más de 12
            # millones) sí, y es justo el motivo de que se pusiera "super
            # lenta" al pasar de una lista a la otra. Quitando siempre la
            # ÚLTIMA fila en su lugar no hace falta desplazar nada (es O(1)
            # por vuelta, O(N) en total) -- el resultado sale en orden
            # inverso, así que se da la vuelta una vez al final con
            # reverse(), que es barato.
            items = []
            while list_widget.count():
                items.append(list_widget.takeItem(list_widget.count() - 1))
            items.reverse()
            items.sort(key=key)
            for item in items:
                list_widget.addItem(item)
        finally:
            list_widget.setUpdatesEnabled(True)
        if active_item is not None:
            win._active_row = list_widget.row(active_item)

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
            self.request_logo(fav.get("logo", ""), item, win.fav_list)

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
        for i in range(win.fav_list.count()):
            data = win.fav_list.item(i).data(ROLE_DATA) or {}
            clave = (data.get("type"), data.get("name"))
            original = next(
                (f for f in win.favorites if (f.get("type"), f.get("name")) == clave), None
            )
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
        # home_recent_carousel / home_recommended_carousel no entran en este
        # bucle: son CarouselCard (ui/carousel.py), no QListWidgetItem con
        # ROLE_PLAYING -- no llevan indicador de "sonando ahora" propio, se
        # limitan a repoblarse cada vez que se entra en Inicio.
        for lst in (win.tv_list, win.radio_list, win.fav_list, win.hist_list, win.home_fav_list):
            for i in range(lst.count()):
                item = lst.item(i)
                data = item.data(ROLE_DATA) or {}
                is_current = data.get("type") == win.current_type and data.get("name") == win.current_name
                item.setData(ROLE_PLAYING, is_current and not win._playback_failed)
            lst.viewport().update()

    def mark_favorites_everywhere(self):
        win = self.win
        for lst in (win.tv_list, win.radio_list, win.hist_list):
            for i in range(lst.count()):
                item = lst.item(i)
                data = item.data(ROLE_DATA) or {}
                item.setData(ROLE_FAV, fav_store.is_favorite(win.favorites, data.get("type"), data.get("name")))
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
        # esa sección (ver MainWindow._on_nav_changed).
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
        if not isinstance(current_widget, QListWidget):
            return

        text = win.search_box.text().strip().lower()
        group = win.group_filter.currentText()
        # Filtro por estado de salud: solo aplica a TV y Radio, las únicas
        # listas cuyas filas llevan ROLE_HEALTH (ver populate_tv_list /
        # populate_radio_list).
        health_key = win.health_filter.currentData() or "all"
        aplica_salud = current_widget in (win.tv_list, win.radio_list)

        # setUpdatesEnabled(False): esto se ejecuta en CADA pulsación de
        # tecla en el buscador (search_box.textChanged está conectado
        # directo a este método). Sin cortar los repintados, cada
        # setHidden() de abajo puede disparar un recálculo del layout
        # visible de la lista -- con un catálogo de varios cientos de
        # canales eso convertía cada tecla pulsada en cientos de
        # relayouts, lo que se sentía como la app "lenta por dentro" al
        # usarla (no solo al arrancar). Mismo patrón que populate_tv_list/
        # sort_catalog.
        current_widget.setUpdatesEnabled(False)
        try:
            for i in range(current_widget.count()):
                item = current_widget.item(i)
                data = item.data(ROLE_DATA) or {}
                matches_text = text in data.get("name", "").lower()
                if current_widget is win.tv_list:
                    # El filtro de categoría de TV lo lleva GroupsSidebar (panel
                    # lateral), no el desplegable group_filter -- ver
                    # MainWindow._on_groups_sidebar_changed / refresh_group_filter().
                    sidebar_groups = getattr(win, "_tv_sidebar_groups", None)
                    matches_group = sidebar_groups is None or data.get("group") in sidebar_groups
                elif current_widget is win.fav_list:
                    if group == "Todas las carpetas":
                        matches_group = True
                    elif group == "Sin carpeta":
                        matches_group = not data.get("group")
                    else:
                        matches_group = data.get("group") == group
                else:
                    matches_group = True
                if aplica_salud and health_key == "stale":
                    matches_health = is_health_stale(data.get("health_checked_at"))
                else:
                    matches_health = not aplica_salud or matches_health_filter(
                        item.data(ROLE_HEALTH), health_key
                    )
                item.setHidden(not (matches_text and matches_group and matches_health))
        finally:
            current_widget.setUpdatesEnabled(True)
