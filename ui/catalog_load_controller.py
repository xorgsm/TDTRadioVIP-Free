"""
Controlador de carga de catálogo de TDT & Radio VIP: descarga (en segundo
plano) los canales de TV y las emisoras de radio, y dispara el diagnóstico
automático de salud de streams cuando ambas listas ya están disponibles.

Extraído de ui/main_window.py por el mismo motivo que
ui.playback_controller.PlaybackController y el resto de controladores —
ver el docstring de PlaybackController para la explicación completa del
porqué del patrón (estado en MainWindow, comportamiento aquí).

Coder By X@R
"""
from ui.fetch_worker import FetchWorker
from core import channels as tv_channels
from core import radio as radio_stations
from core.stream_health_store import record_results, select_stale_entries
from ui.stream_diagnostics_dialog import StreamDiagnosticsWorker


class CatalogLoadController:
    """Carga de canales de TV/radio y diagnóstico automático de streams."""

    def __init__(self, window):
        self.win = window
        self._tv_generation = 0
        self._radio_generation = 0

    def load_tv_channels(self, force: bool = False):
        win = self.win
        if win._is_closing:
            return
        previous = getattr(win, "_tv_worker", None)
        if previous is not None and previous.isRunning():
            previous.cancel()
        self._tv_generation += 1
        generation = self._tv_generation
        win.statusBar().showMessage("Cargando canales de TV…")
        url = win.settings.get("tv_playlist_url") or tv_channels.playlist_url_for(
            win.settings.get("tv_country_code", "ES")
        )
        worker = FetchWorker(tv_channels.fetch_tv_channels, url, force)
        worker.done.connect(lambda channels, token=generation: self._on_tv_channels_loaded(channels, token))
        win._tv_worker = worker
        worker.start()

    def _on_tv_channels_loaded(self, channels, generation=None):
        win = self.win
        if win._is_closing or (generation is not None and generation != self._tv_generation):
            return
        channels = channels or []
        # filter_hidden(): canales de la lista pública que el usuario pidió
        # ocultar desde Archivo > Gestionar canales personalizados (ver
        # core.channels.hide_channels) -- se aplica solo a la lista pública,
        # no a la personalizada, porque no tendría sentido ocultar algo que
        # el usuario añadió él mismo a mano.
        channels = tv_channels.filter_hidden(channels)
        custom = tv_channels.load_custom_channels()
        # dedupe_channels(): la lista del país (o la URL personalizada de
        # Configuración) y la lista de canales importados a mano pueden
        # perfectamente compartir canales -- "La 1"/"La 2" suelen venir en
        # cualquier lista española, así que si además se importó una
        # lista propia con esos mismos canales, salían duplicados en
        # pantalla (uno de cada fuente) aunque cada lista por separado ya
        # viniera limpia.
        win.tv_channels_data = tv_channels.dedupe_channels(channels + custom)
        win.lists.refresh_group_filter()
        win.lists.populate_tv_list(win.tv_channels_data)
        win.lists.filter_current_list()  # ver _on_radio_stations_loaded
        self.update_catalog_count()
        win.statusBar().showMessage(f"{len(win.tv_channels_data)} canales de TV cargados.", 5000)
        self._maybe_start_background_diagnostics()

    def load_radio_stations(self, force: bool = False):
        win = self.win
        if win._is_closing:
            return
        previous = getattr(win, "_radio_worker", None)
        if previous is not None and previous.isRunning():
            previous.cancel()
        self._radio_generation += 1
        generation = self._radio_generation
        win.statusBar().showMessage("Cargando emisoras de radio…")
        worker = FetchWorker(
            radio_stations.fetch_radio_stations, win.settings.get("radio_country_code", "ES"), 250, force
        )
        worker.done.connect(lambda stations, token=generation: self._on_radio_stations_loaded(stations, token))
        win._radio_worker = worker
        worker.start()

    def _on_radio_stations_loaded(self, stations, generation=None):
        win = self.win
        if win._is_closing or (generation is not None and generation != self._radio_generation):
            return
        stations = stations or []
        stations = radio_stations.filter_hidden(stations)  # ver _on_tv_channels_loaded
        custom = radio_stations.load_custom_stations()
        win.radio_stations_data = stations + custom
        win.lists.populate_radio_list(win.radio_stations_data)
        # Repoblar deja todas las filas visibles: si había un filtro activo
        # (búsqueda, categoría o estado de salud), se reaplica.
        win.lists.filter_current_list()
        self.update_catalog_count()
        win.statusBar().showMessage(f"{len(win.radio_stations_data)} emisoras de radio cargadas.", 5000)
        self._maybe_start_background_diagnostics()

    def _maybe_start_background_diagnostics(self):
        win = self.win
        if (
            win._background_diagnostics_started
            or not win.settings.get("automatic_stream_diagnostics", True)
            or not win.tv_channels_data
            or not win.radio_stations_data
        ):
            return
        entries = [
            {"kind": "tv", "name": channel.name, "url": channel.url}
            for channel in win.tv_channels_data if channel.url
        ] + [
            {"kind": "radio", "name": station.name, "url": station.url}
            for station in win.radio_stations_data if station.url
        ]
        stale = select_stale_entries(
            entries,
            limit=int(win.settings.get("automatic_stream_diagnostics_limit", 20)),
        )
        if not stale:
            win._background_diagnostics_started = True
            return
        win._background_diagnostics_started = True
        win._background_health_results = []
        worker = StreamDiagnosticsWorker(stale, win)
        worker.result_ready.connect(win._background_health_results.append)
        worker.completed.connect(self._on_background_diagnostics_completed)
        win._background_diagnostics_worker = worker
        worker.start()

    def _on_background_diagnostics_completed(self, cancelled):
        win = self.win
        if cancelled or win._is_closing:
            return
        try:
            recorded = record_results(win._background_health_results)
            win.home.refresh_home_health()
            # El diagnóstico solo cambia ROLE_HEALTH y la fecha asociada.
            # No se borran/recrean miles de filas (ni se reencolan sus logos)
            # mientras el usuario puede estar reproduciendo un stream.
            win.lists.update_stream_health(recorded)
            win.lists.filter_current_list()
            win.statusBar().showMessage(
                f"Diagnóstico automático: {len(win._background_health_results)} streams revisados.",
                5000,
            )
        except OSError:
            pass

    def update_catalog_count(self) -> None:
        """Muestra el total del catálogo solo durante la exploración."""
        # Import tardío (no a nivel de módulo): NAV_TV/NAV_RADIO viven en
        # ui.main_window, que es quien construye este controlador -- un
        # import normal aquí arriba crearía un ciclo. En tiempo de
        # ejecución (llamado desde la propia ventana ya construida) no hay
        # problema real, igual que en EpgController.tune_to_tvg_id().
        from ui.main_window import NAV_RADIO, NAV_TV

        win = self.win
        if not hasattr(win, "catalog_count_label"):
            return
        if win._current_nav_id == NAV_TV:
            win.catalog_count_label.setText(f"{len(win.tv_channels_data)} CANALES")
        elif win._current_nav_id == NAV_RADIO:
            win.catalog_count_label.setText(f"{len(win.radio_stations_data)} EMISORAS")
        else:
            win.catalog_count_label.hide()
            return
        win.catalog_count_label.show()
