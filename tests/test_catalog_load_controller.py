from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from ui.catalog_load_controller import CatalogLoadController
from ui.epg_controller import EpgController


def test_cancel_background_diagnostics_cancels_and_returns_the_running_worker():
    worker = Mock()
    window = Mock(_background_diagnostics_worker=worker)

    result = CatalogLoadController(window).cancel_background_diagnostics()

    worker.cancel.assert_called_once_with()
    assert result is worker


def test_cancel_background_diagnostics_is_a_noop_when_nothing_ever_started():
    # _background_diagnostics_worker is only ever set once diagnostics
    # actually start (see _maybe_start_background_diagnostics) -- closing
    # the app before that happens must not crash on a missing attribute.
    window = SimpleNamespace()

    result = CatalogLoadController(window).cancel_background_diagnostics()

    assert result is None


class _SyncWorker:
    """FetchWorker de prueba: ejecuta la función al arrancar y emite done."""

    def __init__(self, func, *args):
        self._func = func
        self._args = args
        self._slots = []
        self.done = SimpleNamespace(connect=self._slots.append)

    def start(self):
        result = self._func(*self._args)
        for slot in self._slots:
            slot(result)


def test_background_diagnostics_updates_health_without_repopulating(monkeypatch):
    recorded = [{
        "kind": "tv", "url": "https://tv.test", "status": "stable",
        "checked_at": "2026-09-01T10:00:00+00:00", "latency_ms": 20,
    }]
    monkeypatch.setattr("ui.catalog_load_controller.record_results", lambda _results: recorded)
    monkeypatch.setattr("ui.catalog_load_controller.FetchWorker", _SyncWorker)
    lists = Mock()
    window = Mock(
        _is_closing=False,
        _background_health_results=[{"kind": "tv", "url": "https://tv.test"}],
        lists=lists,
    )

    CatalogLoadController(window)._on_background_diagnostics_completed(False)

    lists.update_stream_health.assert_called_once_with(recorded)
    lists.populate_tv_list.assert_not_called()
    lists.populate_radio_list.assert_not_called()
    lists.filter_current_list.assert_called_once_with()
    window.home.refresh_home_health.assert_called_once_with()


def test_no_call_site_bypasses_home_controller_for_home_refreshes():
    """_refresh_home_now_playing()/refresh_home_health() live on
    ui.home_controller.HomeController (window.home), not on MainWindow
    itself (see the comment in ui/main_window.py). A call written as
    ``win._refresh_home_now_playing()``/``win._refresh_home_health()``
    instead of going through ``win.home`` raises AttributeError on a real
    MainWindow -- silently, since Qt just logs the traceback from the slot
    and keeps running, so nothing else here would catch it. Guard the two
    call sites (ui/playback_controller.py, ui/catalog_load_controller.py)
    statically instead of trying to mock the whole MainWindow.
    """
    root = Path(__file__).resolve().parent.parent
    for relative in ("ui/playback_controller.py", "ui/catalog_load_controller.py"):
        source = (root / relative).read_text(encoding="utf-8")
        assert "win._refresh_home_now_playing(" not in source, relative
        assert "win._refresh_home_health(" not in source, relative


def test_epg_loaded_updates_subtitles_without_repopulating():
    """La guía EPG termina de cargar -- ver EpgController._on_loaded().
    Con catálogos grandes, repoblar la lista de TV entera solo para
    refrescar el "Ahora: ..." de cada fila (como hacía antes) recreaba
    todos los QListWidgetItem, reordenaba y volvía a encolar el logo de
    cada canal -- justo lo que ya se evita para el diagnóstico de salud
    (test_background_diagnostics_updates_health_without_repopulating).
    """
    lists = Mock()
    window = Mock(_is_closing=False, tv_channels_data=[object()], lists=lists)

    EpgController(window)._on_loaded({"canal": []})

    lists.update_epg_subtitles.assert_called_once_with()
    lists.populate_tv_list.assert_not_called()


def _channel(tvg_id):
    return SimpleNamespace(tvg_id=tvg_id, name=tvg_id or "sin id")


def test_epg_load_requests_only_the_guide_of_the_loaded_channels(monkeypatch):
    created = []

    class FakeWorker:
        def __init__(self, func, *args):
            self.args = args
            self.done = Mock()
            created.append(self)

        def start(self):
            pass

    monkeypatch.setattr("ui.epg_controller.FetchWorker", FakeWorker)
    window = Mock(
        settings={"epg_url": "https://guia.test/epg.xml"},
        tv_channels_data=[_channel("La1.es@SD"), _channel(""), _channel("Antena 3.es")],
        _epg_worker=None,
    )

    EpgController(window).load()

    url, force, wanted = created[0].args
    assert url == "https://guia.test/epg.xml"
    assert force is False
    assert wanted == {"la1", "antena3"}


def test_epg_load_waits_for_the_channels_instead_of_downloading_everything(monkeypatch):
    worker_class = Mock()
    monkeypatch.setattr("ui.epg_controller.FetchWorker", worker_class)
    window = Mock(settings={"epg_url": "https://guia.test/epg.xml"}, tv_channels_data=[])

    EpgController(window).load()

    worker_class.assert_not_called()


def _epg_window(channels, running_worker=None, url="https://guia.test/epg.xml"):
    return Mock(
        settings={"epg_url": url},
        tv_channels_data=channels,
        _epg_worker=running_worker,
    )


def _fake_epg_worker(monkeypatch):
    created = []

    class FakeWorker:
        def __init__(self, func, *args):
            self.args = args
            self.done = Mock()
            self.cancel = Mock()
            self._running = False
            created.append(self)

        def start(self):
            self._running = True

        def isRunning(self):
            return self._running

    monkeypatch.setattr("ui.epg_controller.FetchWorker", FakeWorker)
    return created


def test_epg_load_skips_an_identical_request_while_one_runs(monkeypatch):
    created = _fake_epg_worker(monkeypatch)
    window = _epg_window([_channel("La1.es")])
    controller = EpgController(window)

    controller.load()
    window._epg_worker = created[0]
    controller.load()

    assert len(created) == 1
    created[0].cancel.assert_not_called()


def test_epg_load_replaces_a_running_download_when_the_channels_changed(monkeypatch):
    created = _fake_epg_worker(monkeypatch)
    window = _epg_window([_channel("La1.es")])
    controller = EpgController(window)
    controller.load()
    window._epg_worker = created[0]
    window.tv_channels_data = [_channel("La1.es"), _channel("Antena 3.es")]

    controller.load()

    created[0].cancel.assert_called_once_with()
    assert len(created) == 2
    assert created[1].args[2] == {"la1", "antena3"}


def test_epg_load_replaces_a_running_download_when_the_url_changed(monkeypatch):
    created = _fake_epg_worker(monkeypatch)
    window = _epg_window([_channel("La1.es")])
    controller = EpgController(window)
    controller.load()
    window._epg_worker = created[0]
    window.settings = {"epg_url": "https://otra-guia.test/epg.xml"}

    controller.load()

    created[0].cancel.assert_called_once_with()
    assert created[1].args[0] == "https://otra-guia.test/epg.xml"


def test_epg_result_of_a_replaced_download_is_ignored(monkeypatch):
    created = _fake_epg_worker(monkeypatch)
    window = _epg_window([_channel("La1.es")])
    controller = EpgController(window)
    controller.load()
    first_callback = created[0].done.connect.call_args.args[0]
    window._epg_worker = created[0]
    window.tv_channels_data = [_channel("Antena 3.es")]
    controller.load()

    first_callback({"la1": []})

    assert window.playback.update_epg_display.call_count == 0


def test_tv_channels_loaded_starts_the_epg_once_channels_are_known(monkeypatch):
    monkeypatch.setattr("ui.catalog_load_controller.tv_channels.filter_hidden", lambda c: c)
    monkeypatch.setattr("ui.catalog_load_controller.tv_channels.load_custom_channels", lambda: [])
    monkeypatch.setattr("ui.catalog_load_controller.tv_channels.dedupe_channels", lambda c: c)
    window = Mock(
        _is_closing=False,
        settings={"epg_url": "https://guia.test/epg.xml", "automatic_stream_diagnostics": False},
    )

    CatalogLoadController(window)._on_tv_channels_loaded([_channel("La1.es")])

    window.epg.load.assert_called_once_with()


def test_tv_channels_loaded_skips_the_epg_when_none_is_configured(monkeypatch):
    monkeypatch.setattr("ui.catalog_load_controller.tv_channels.filter_hidden", lambda c: c)
    monkeypatch.setattr("ui.catalog_load_controller.tv_channels.load_custom_channels", lambda: [])
    monkeypatch.setattr("ui.catalog_load_controller.tv_channels.dedupe_channels", lambda c: c)
    window = Mock(
        _is_closing=False,
        settings={"epg_url": "", "automatic_stream_diagnostics": False},
    )

    CatalogLoadController(window)._on_tv_channels_loaded([_channel("La1.es")])

    window.epg.load.assert_not_called()


def _tv_window(running_worker=None):
    return Mock(
        _is_closing=False,
        settings={"tv_playlist_url": "https://lista.test/es.m3u"},
        _tv_worker=running_worker,
    )


def _fake_tv_worker(monkeypatch):
    created = []

    class FakeWorker:
        def __init__(self, func, *args):
            self.args = args
            self.done = Mock()
            self.cancel = Mock()
            self._running = False
            created.append(self)

        def start(self):
            self._running = True

        def isRunning(self):
            return self._running

    monkeypatch.setattr("ui.catalog_load_controller.FetchWorker", FakeWorker)
    return created


def test_a_forced_refresh_is_ignored_while_another_one_is_still_downloading(monkeypatch):
    created = _fake_tv_worker(monkeypatch)
    window = _tv_window()
    controller = CatalogLoadController(window)
    controller.load_tv_channels(force=True)
    window._tv_worker = created[0]

    controller.load_tv_channels(force=True)
    controller.load_tv_channels(force=True)

    assert len(created) == 1
    created[0].cancel.assert_not_called()


def test_a_forced_refresh_replaces_a_cache_only_load_in_progress(monkeypatch):
    created = _fake_tv_worker(monkeypatch)
    window = _tv_window()
    controller = CatalogLoadController(window)
    controller.load_tv_channels(force=False)
    window._tv_worker = created[0]

    controller.load_tv_channels(force=True)

    created[0].cancel.assert_called_once_with()
    assert len(created) == 2
    assert created[1].args[1] is True


def test_a_new_refresh_is_accepted_once_the_previous_one_finished(monkeypatch):
    created = _fake_tv_worker(monkeypatch)
    window = _tv_window()
    controller = CatalogLoadController(window)
    controller.load_tv_channels(force=True)
    created[0]._running = False
    window._tv_worker = created[0]

    controller.load_tv_channels(force=True)

    assert len(created) == 2


def test_tv_channels_loaded_reads_the_custom_channels_once_for_the_whole_populate(monkeypatch):
    reads = []
    custom = [SimpleNamespace(name="Mi canal", tvg_id="", group="", url="u", logo="", alternate_urls=[])]
    monkeypatch.setattr("ui.catalog_load_controller.tv_channels.filter_hidden", lambda c: c)
    monkeypatch.setattr(
        "ui.catalog_load_controller.tv_channels.load_custom_channels",
        lambda: reads.append(1) or custom,
    )
    monkeypatch.setattr("ui.catalog_load_controller.tv_channels.dedupe_channels", lambda c: c)
    window = Mock(_is_closing=False, settings={"epg_url": "", "automatic_stream_diagnostics": False})

    CatalogLoadController(window)._on_tv_channels_loaded([_channel("La1.es")])

    assert reads == [1]
    window.lists.populate_tv_list.assert_called_once()
    assert window.lists.populate_tv_list.call_args.kwargs["custom_names"] == {"Mi canal"}


def test_main_window_defers_the_initial_catalog_loads_until_the_window_is_shown():
    """Los catálogos arrancan con un temporizador de 0 ms (tras ``show()``) y
    no dentro del constructor: así la ventana aparece antes y la carga no
    la retrasa."""
    from ui.main_window import MainWindow

    root = Path(__file__).resolve().parent.parent
    init_source = (root / "ui" / "main_window.py").read_text(encoding="utf-8")
    constructor = init_source.split("def __init__", 1)[1].split("\n    def ", 1)[0]
    assert "self.catalog.load_tv_channels()" not in constructor
    assert "QTimer.singleShot(0, self._start_initial_loads)" in constructor

    window = Mock(_is_closing=False)
    MainWindow._start_initial_loads(window)
    window.catalog.load_tv_channels.assert_called_once_with()
    window.catalog.load_radio_stations.assert_called_once_with()
    window.lists.refresh_favorites_tab.assert_called_once_with()
    window.lists.refresh_history_tab.assert_called_once_with()


def test_deferred_initial_loads_do_nothing_if_the_window_is_already_closing():
    from ui.main_window import MainWindow

    window = Mock(_is_closing=True)

    MainWindow._start_initial_loads(window)

    window.catalog.load_tv_channels.assert_not_called()


def test_a_reload_right_after_the_result_was_delivered_is_not_dropped(monkeypatch):
    """``done`` se entrega antes de que el hilo termine (``isRunning()`` sigue
    verdadero un instante): una recarga idéntica pedida justo entonces, p. ej.
    tras restaurar canales ocultos, no puede descartarse como duplicada."""
    created = _fake_tv_worker(monkeypatch)
    monkeypatch.setattr("ui.catalog_load_controller.tv_channels.filter_hidden", lambda c: c)
    monkeypatch.setattr("ui.catalog_load_controller.tv_channels.load_custom_channels", lambda: [])
    monkeypatch.setattr("ui.catalog_load_controller.tv_channels.dedupe_channels", lambda c: c)
    window = _tv_window()
    window.settings["epg_url"] = ""
    window.settings["automatic_stream_diagnostics"] = False
    controller = CatalogLoadController(window)
    controller.load_tv_channels(force=False)
    window._tv_worker = created[0]
    first_callback = created[0].done.connect.call_args.args[0]

    first_callback([_channel("La1.es")])  # resultado entregado; el hilo aún "corre"
    controller.load_tv_channels(force=False)

    assert len(created) == 2


def test_a_different_url_replaces_the_download_in_progress(monkeypatch):
    created = _fake_tv_worker(monkeypatch)
    window = _tv_window()
    controller = CatalogLoadController(window)
    controller.load_tv_channels(force=True)
    window._tv_worker = created[0]
    window.settings["tv_playlist_url"] = "https://otra.test/fr.m3u"

    controller.load_tv_channels(force=True)

    created[0].cancel.assert_called_once_with()
    assert created[1].args[0] == "https://otra.test/fr.m3u"


def test_a_cache_only_request_is_ignored_while_a_forced_download_runs(monkeypatch):
    created = _fake_tv_worker(monkeypatch)
    window = _tv_window()
    controller = CatalogLoadController(window)
    controller.load_tv_channels(force=True)
    window._tv_worker = created[0]

    controller.load_tv_channels(force=False)

    assert len(created) == 1


# --- Revalidación en segundo plano y repoblado solo si cambió ---------------

def _patch_tv_data(monkeypatch, custom=()):
    monkeypatch.setattr("ui.catalog_load_controller.tv_channels.filter_hidden", lambda c: c)
    monkeypatch.setattr("ui.catalog_load_controller.tv_channels.load_custom_channels", lambda: list(custom))
    monkeypatch.setattr("ui.catalog_load_controller.tv_channels.dedupe_channels", lambda c: c)


def _loaded_window():
    window = _tv_window()
    window.settings["epg_url"] = ""
    window.settings["automatic_stream_diagnostics"] = False
    window.tv_channels_data = []
    return window


def _deliver(controller, window, created, channels):
    """Simula que el último worker lanzado entrega ``channels``."""
    callback = created[-1].done.connect.call_args.args[0]
    callback(channels)
    return callback


def test_a_stale_cache_is_shown_first_and_then_revalidated_from_the_network(monkeypatch):
    created = _fake_tv_worker(monkeypatch)
    _patch_tv_data(monkeypatch)
    monkeypatch.setattr("ui.catalog_load_controller.tv_channels.cache_is_stale", lambda url, **kw: True)
    window = _loaded_window()
    controller = CatalogLoadController(window)
    controller.load_tv_channels(force=False)

    _deliver(controller, window, created, [_channel("La1.es")])

    assert len(created) == 2
    assert created[1].args[1] is True  # force: red
    window.lists.populate_tv_list.assert_called_once()  # la caché ya se mostró


def test_a_fresh_cache_is_not_revalidated(monkeypatch):
    created = _fake_tv_worker(monkeypatch)
    _patch_tv_data(monkeypatch)
    monkeypatch.setattr("ui.catalog_load_controller.tv_channels.cache_is_stale", lambda url, **kw: False)
    window = _loaded_window()
    controller = CatalogLoadController(window)
    controller.load_tv_channels(force=False)

    _deliver(controller, window, created, [_channel("La1.es")])

    assert len(created) == 1


def test_a_network_result_never_triggers_another_revalidation(monkeypatch):
    created = _fake_tv_worker(monkeypatch)
    _patch_tv_data(monkeypatch)
    monkeypatch.setattr("ui.catalog_load_controller.tv_channels.cache_is_stale", lambda url, **kw: True)
    window = _loaded_window()
    controller = CatalogLoadController(window)
    controller.load_tv_channels(force=True)

    _deliver(controller, window, created, [_channel("La1.es")])

    assert len(created) == 1


def test_an_unchanged_result_does_not_repopulate_the_list(monkeypatch):
    created = _fake_tv_worker(monkeypatch)
    _patch_tv_data(monkeypatch)
    monkeypatch.setattr("ui.catalog_load_controller.tv_channels.cache_is_stale", lambda url, **kw: False)
    window = _loaded_window()
    controller = CatalogLoadController(window)
    same = [_channel("La1.es")]
    controller.load_tv_channels(force=False)
    _deliver(controller, window, created, same)
    window.tv_channels_data = same  # lo que quedó en pantalla
    controller.load_tv_channels(force=True)

    _deliver(controller, window, created, list(same))

    window.lists.populate_tv_list.assert_called_once()
    window.statusBar.return_value.showMessage.assert_called()


def test_a_changed_result_repopulates_the_list(monkeypatch):
    created = _fake_tv_worker(monkeypatch)
    _patch_tv_data(monkeypatch)
    monkeypatch.setattr("ui.catalog_load_controller.tv_channels.cache_is_stale", lambda url, **kw: False)
    window = _loaded_window()
    controller = CatalogLoadController(window)
    controller.load_tv_channels(force=False)
    _deliver(controller, window, created, [_channel("La1.es")])
    window.tv_channels_data = [_channel("La1.es")]
    controller.load_tv_channels(force=True)

    _deliver(controller, window, created, [_channel("La1.es"), _channel("Antena 3.es")])

    assert window.lists.populate_tv_list.call_count == 2


def test_a_change_in_the_custom_channels_alone_repopulates_the_list(monkeypatch):
    """La lista fusionada es idéntica (el canal propio ya estaba en la pública
    con la misma URL); solo cambia qué nombres son propios, y eso se pinta
    (ROLE_CUSTOM) -- debe repoblar."""
    from core.channels import Channel

    created = _fake_tv_worker(monkeypatch)
    custom = []
    monkeypatch.setattr("ui.catalog_load_controller.tv_channels.filter_hidden", lambda c: c)
    monkeypatch.setattr("ui.catalog_load_controller.tv_channels.load_custom_channels", lambda: list(custom))
    monkeypatch.setattr("ui.catalog_load_controller.tv_channels.cache_is_stale", lambda url, **kw: False)
    window = _loaded_window()
    controller = CatalogLoadController(window)
    controller.load_tv_channels(force=False)
    _deliver(controller, window, created, [Channel("La 1", "https://tv.test/la1")])
    window.tv_channels_data = [Channel("La 1", "https://tv.test/la1")]
    custom.append(Channel("La 1", "https://tv.test/la1"))
    controller.load_tv_channels(force=True)

    _deliver(controller, window, created, [Channel("La 1", "https://tv.test/la1")])

    assert window.lists.populate_tv_list.call_count == 2


def test_no_second_download_is_started_when_the_first_one_found_no_cache(monkeypatch):
    """Sin caché y con la red caída, la primera carga ya intentó descargar:
    «caché ausente» no es «caché vieja» y no justifica repetir el intento."""
    created = _fake_tv_worker(monkeypatch)
    _patch_tv_data(monkeypatch)
    monkeypatch.setattr(
        "ui.catalog_load_controller.tv_channels.cache_is_stale",
        lambda url, max_age=None, *, missing=True: missing,
    )
    window = _loaded_window()
    controller = CatalogLoadController(window)
    controller.load_tv_channels(force=False)

    _deliver(controller, window, created, [])

    assert len(created) == 1
