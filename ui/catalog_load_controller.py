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
from typing import NamedTuple

from PySide6.QtCore import QTimer

from ui.fetch_worker import FetchWorker
from core import channels as tv_channels
from core import radio as radio_stations
from core.stream_health_store import record_results, select_stale_entries
from ui.nav_sections import NAV_RADIO, NAV_TV
from ui.stream_diagnostics_dialog import StreamDiagnosticsWorker

# El diagnóstico automático es solo un "chequeo de salud" oportunista, no
# algo que el usuario esté esperando -- no tiene sentido que compita por CPU
# con la carga inicial del catálogo y de la guía EPG (ver core/epg.py), que
# sí se nota en la interfaz. Arranca con menos concurrencia que el diálogo
# manual "Comprobar catálogo ahora" (12 workers) y con un pequeño retraso
# tras tener ambas listas, para dejar que el arranque termine primero.
_AUTO_DIAGNOSTICS_MAX_WORKERS = 3
_AUTO_DIAGNOSTICS_START_DELAY_MS = 8000


class MergedCatalog(NamedTuple):
    """Catálogo ya combinado en el worker (pública filtrada + personalizada)."""
    items: list
    custom_names: frozenset


def _merge_tv_catalog(channels) -> MergedCatalog:
    # filter_hidden(): canales de la lista pública que el usuario pidió
    # ocultar desde Archivo > Gestionar canales personalizados (ver
    # core.channels.hide_channels) -- se aplica solo a la lista pública,
    # no a la personalizada, porque no tendría sentido ocultar algo que
    # el usuario añadió él mismo a mano.
    channels = tv_channels.filter_hidden(channels or [])
    custom = tv_channels.load_custom_channels()
    # dedupe_channels(): la lista del país (o la URL personalizada de
    # Configuración) y la lista de canales importados a mano pueden
    # perfectamente compartir canales -- "La 1"/"La 2" suelen venir en
    # cualquier lista española, así que si además se importó una
    # lista propia con esos mismos canales, salían duplicados en
    # pantalla (uno de cada fuente) aunque cada lista por separado ya
    # viniera limpia.
    return MergedCatalog(
        tv_channels.dedupe_channels(channels + custom),
        frozenset(channel.name for channel in custom),
    )


def _load_tv_catalog(url, force) -> MergedCatalog:
    """Descarga y combina la lista de TV fuera del hilo de la interfaz."""
    return _merge_tv_catalog(tv_channels.fetch_tv_channels(url, force))


def _merge_radio_catalog(stations) -> MergedCatalog:
    stations = radio_stations.filter_hidden(stations or [])  # ver _merge_tv_catalog
    return MergedCatalog(stations + radio_stations.load_custom_stations(), frozenset())


def _load_radio_catalog(country, limit, force) -> MergedCatalog:
    """Descarga y combina las emisoras fuera del hilo de la interfaz."""
    return _merge_radio_catalog(radio_stations.fetch_radio_stations(country, limit, force))


class CatalogLoadController:
    """Carga de canales de TV/radio y diagnóstico automático de streams."""

    def __init__(self, window):
        self.win = window
        self._tv_generation = 0
        self._radio_generation = 0
        self._tv_request = None
        self._radio_request = None
        self._tv_custom_names = frozenset()
        self._tv_revalidated_urls = set()

    def load_tv_channels(self, force: bool = False):
        win = self.win
        if win._is_closing:
            return
        url = win.settings.get("tv_playlist_url") or tv_channels.playlist_url_for(
            win.settings.get("tv_country_code", "ES")
        )
        previous = getattr(win, "_tv_worker", None)
        if previous is not None and previous.isRunning():
            # cancel() no interrumpe la descarga en curso: cada pulsación
            # extra de «Actualizar» sumaba otra descarga simultánea. Si ya se
            # está pidiendo esta misma lista a la red (o solo se pide la
            # caché), no hay nada nuevo que lanzar.
            previous_url, previous_force = self._tv_request or (None, False)
            if url == previous_url and (previous_force or not force):
                return
            previous.cancel()
        self._tv_request = (url, force)
        self._tv_generation += 1
        generation = self._tv_generation
        win.statusBar().showMessage("Cargando canales de TV…")
        worker = FetchWorker(_load_tv_catalog, url, force)
        worker.done.connect(lambda channels, token=generation: self._on_tv_channels_loaded(channels, token))
        win._tv_worker = worker
        worker.start()

    def _on_tv_channels_loaded(self, channels, generation=None):
        win = self.win
        if win._is_closing or (generation is not None and generation != self._tv_generation):
            return
        # Resultado entregado: ya no hay petición pendiente aunque el hilo
        # siga cerrándose (isRunning() aún verdadero), y una recarga idéntica
        # pedida ahora -- p. ej. al restaurar ocultos -- no es un duplicado.
        request, self._tv_request = self._tv_request, None
        # El worker entrega el catálogo ya combinado; una lista suelta (otros
        # llamadores) se combina aquí.
        catalog = channels if isinstance(channels, MergedCatalog) else _merge_tv_catalog(channels)
        merged, custom_names = catalog
        # Una revalidación en segundo plano que no trae cambios no debe
        # reconstruir la lista entera (miles de filas) ni perder el scroll.
        unchanged = merged == win.tv_channels_data and custom_names == self._tv_custom_names
        self._tv_custom_names = custom_names
        if not unchanged:
            win.tv_channels_data = merged
            win.lists.refresh_group_filter()
            win.lists.populate_tv_list(win.tv_channels_data, custom_names=custom_names)
            win.lists.filter_current_list()  # ver _on_radio_stations_loaded
            self.update_catalog_count()
        win.statusBar().showMessage(f"{len(win.tv_channels_data)} canales de TV cargados.", 5000)
        if win.settings.get("epg_url"):
            win.epg.load()
        self._maybe_start_background_diagnostics()
        self._revalidate_stale_tv_cache(request)

    def _revalidate_stale_tv_cache(self, request) -> None:
        """Tras mostrar una lista leída de la caché, la contrasta con la red.

        Solo una vez por URL y sesión, y solo si lo que se acaba de cargar
        vino de la caché (una descarga de red ya es la versión fresca).
        """
        if request is None:
            return
        url, forced = request
        if forced or url in self._tv_revalidated_urls or not tv_channels.cache_is_stale(url, missing=False):
            return
        self._tv_revalidated_urls.add(url)
        self.load_tv_channels(force=True)

    def load_radio_stations(self, force: bool = False):
        win = self.win
        if win._is_closing:
            return
        country = win.settings.get("radio_country_code", "ES")
        previous = getattr(win, "_radio_worker", None)
        if previous is not None and previous.isRunning():
            # cancel() no corta la descarga en curso: una petición idéntica
            # solo apilaría otra (mismo criterio que load_tv_channels).
            previous_country, previous_force = self._radio_request or (None, False)
            if country == previous_country and (previous_force or not force):
                return
            previous.cancel()
        self._radio_request = (country, force)
        self._radio_generation += 1
        generation = self._radio_generation
        win.statusBar().showMessage("Cargando emisoras de radio…")
        worker = FetchWorker(_load_radio_catalog, country, 250, force)
        worker.done.connect(lambda stations, token=generation: self._on_radio_stations_loaded(stations, token))
        win._radio_worker = worker
        worker.start()

    def _on_radio_stations_loaded(self, stations, generation=None):
        win = self.win
        if win._is_closing or (generation is not None and generation != self._radio_generation):
            return
        self._radio_request = None
        catalog = stations if isinstance(stations, MergedCatalog) else _merge_radio_catalog(stations)
        # Una recarga sin cambios no reconstruye la lista entera.
        if catalog.items != win.radio_stations_data:
            win.radio_stations_data = catalog.items
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
        # Se marca "started" ya aquí (no dentro de _start_background_diagnostics)
        # para que una segunda llamada a este método mientras el QTimer todavía
        # está en cuenta atrás -- p. ej. TV termina de cargar después que
        # Radio -- no programe un segundo arranque.
        win._background_diagnostics_started = True
        QTimer.singleShot(_AUTO_DIAGNOSTICS_START_DELAY_MS, self._start_background_diagnostics)

    def _start_background_diagnostics(self):
        win = self.win
        if win._is_closing:
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
            return
        win._background_health_results = []
        worker = StreamDiagnosticsWorker(stale, win, max_workers=_AUTO_DIAGNOSTICS_MAX_WORKERS)
        worker.results_ready.connect(
            lambda results, _completed, _total: win._background_health_results.extend(results)
        )
        worker.completed.connect(self._on_background_diagnostics_completed)
        win._background_diagnostics_worker = worker
        worker.start()

    def cancel_background_diagnostics(self):
        """
        Cancela el diagnóstico automático en curso (si lo hay) y devuelve su
        worker para que MainWindow.closeEvent() pueda esperarlo
        cooperativamente junto al resto de FetchWorker activos -- antes se
        dejaba corriendo mientras la ventana se destruía, el mismo patrón
        que ya causó la carrera de Torrents/Soulseek (ver CHANGELOG).

        _background_diagnostics_worker solo existe una vez que
        _maybe_start_background_diagnostics() arrancó uno de verdad, así
        que cerrar la app antes de eso no debe reventar por atributo
        ausente.
        """
        worker = getattr(self.win, "_background_diagnostics_worker", None)
        if worker is not None:
            worker.cancel()
        return worker

    def _on_background_diagnostics_completed(self, cancelled):
        win = self.win
        if cancelled or win._is_closing:
            return
        # record_results relee y reescribe todo el almacén de salud: en un worker.
        worker = FetchWorker(record_results, list(win._background_health_results))
        worker.done.connect(self._on_background_health_persisted)
        win._background_health_store_worker = worker
        worker.start()

    def _on_background_health_persisted(self, recorded):
        win = self.win
        if win._is_closing or recorded is None:
            return
        try:
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
