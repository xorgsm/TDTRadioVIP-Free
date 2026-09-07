"""
Controlador de la guía de programación (EPG) de TDT & Radio VIP: cargarla
en segundo plano, abrir su diálogo y sintonizar un canal elegido ahí.

Extraído de ui/main_window.py por el mismo motivo que
ui.playback_controller.PlaybackController y el resto de controladores —
ver el docstring de PlaybackController para la explicación completa del
porqué del patrón (estado en MainWindow, comportamiento aquí).

Coder By X@R
"""
from PySide6.QtWidgets import QMessageBox

from core import epg as epg_module
from ui.epg_dialog import EpgDialog
from ui.fetch_worker import FetchWorker


class EpgController:
    """Carga, diálogo y sintonía de la guía de programación (XMLTV)."""

    def __init__(self, window):
        self.win = window

    def load(self):
        win = self.win
        worker = FetchWorker(epg_module.fetch_epg, win.settings["epg_url"], False)
        worker.done.connect(self._on_loaded)
        win._epg_worker = worker
        worker.start()

    def _on_loaded(self, guide):
        win = self.win
        if getattr(win, "_is_closing", False):
            return
        guide = guide or {}
        # Guías públicas como EPG_dobleM traen TODOS los canales de España
        # (miles de claves, cientos de miles de programas) aunque el usuario
        # solo tenga unos pocos en su lista -- guardar eso entero en
        # win.epg_guide inflaba la RAM residente muy por encima de lo que la
        # app llega a usar nunca. Se recorta a los canales que de verdad
        # están en tv_channels_data; si esa lista aún no se ha poblado (caso
        # raro, ver el comentario de abajo) se deja la guía completa por
        # esta vez en vez de perder datos.
        if win.tv_channels_data:
            claves_propias = {
                epg_module.channel_key(getattr(ch, "tvg_id", ""))
                for ch in win.tv_channels_data
                if getattr(ch, "tvg_id", "")
            }
            guide = {clave: progs for clave, progs in guide.items() if clave in claves_propias}
        win.epg_guide = guide
        win.playback.update_epg_display()
        # La lista de canales de TV normalmente ya se pobló antes de que
        # esta guía terminara de descargarse (_load_tv_channels() se lanza
        # al arrancar, y esta carga va aparte, ver MainWindow.__init__) --
        # sin actualizar aquí, el mini-EPG de cada fila ("Ahora: ...", ver
        # ChannelListsController._epg_now_text) se quedaría vacío hasta el
        # próximo "Actualizar canales" aunque la guía ya esté disponible.
        # update_epg_subtitles() en vez de populate_tv_list(): repoblar
        # entera solo para cambiar un texto recreaba todas las filas,
        # volvía a ordenar y volvía a encolar el logo de cada canal -- ver
        # el docstring de update_epg_subtitles para el porqué importaba con
        # catálogos grandes.
        if win.tv_channels_data:
            win.lists.update_epg_subtitles()

    def open_dialog(self):
        win = self.win
        if not win.epg_guide:
            QMessageBox.information(
                win, "Sin guía de programación",
                "Todavía no hay datos de programación descargados.\n\n"
                "Configura una URL de EPG (XMLTV) en Configuración si no lo "
                "has hecho, o espera unos segundos a que termine de cargar."
            )
            return
        dialog = EpgDialog(win.tv_channels_data, win.epg_guide, win)
        dialog.channel_chosen.connect(self.tune_to_tvg_id)
        dialog.exec()

    def now_on_air_entries(self, limit: int = 12) -> list:
        """
        Para el panel "Ahora en antena" de la portada de Inicio: qué está
        emitiendo cada canal ahora mismo, según la guía ya cargada en
        memoria (win.epg_guide) -- sin ninguna llamada de red aquí, esa la
        hace load() aparte. Se limita a canales con tvg_id que la EPG
        conozca y que de verdad tengan un programa en curso; si no hay
        nada emitiéndose para ese canal ahora mismo, se omite en vez de
        enseñar una tarjeta vacía.
        """
        win = self.win
        if not win.epg_guide:
            return []
        entradas = []
        for ch in win.tv_channels_data:
            if not ch.tvg_id or epg_module.channel_key(ch.tvg_id) not in win.epg_guide:
                continue
            current, _ = epg_module.get_now_next(win.epg_guide, ch.tvg_id)
            if current is None:
                continue
            entradas.append({
                "type": "tv", "name": ch.name, "url": ch.url,
                "logo": ch.logo, "tvg_id": ch.tvg_id,
                "subtitle": current.title,
            })
            if len(entradas) >= limit:
                break
        return entradas

    def tune_to_tvg_id(self, tvg_id: str):
        # Import tardío (no a nivel de módulo): NAV_TV vive en
        # ui.main_window, que es quien construye este controlador -- un
        # import normal aquí arriba crearía un ciclo. En tiempo de
        # ejecución (el usuario eligiendo algo en la guía) el módulo ya
        # está totalmente cargado, así que no hay problema real.
        from ui.main_window import NAV_TV

        win = self.win
        for ch in win.tv_channels_data:
            if ch.tvg_id == tvg_id:
                win.playback.play("tv", ch.name, ch.url, ch.tvg_id, ch.logo)
                win.nav_group.button(NAV_TV).setChecked(True)
                win._on_nav_changed(NAV_TV)
                return
