"""Comportamiento de las rutas optimizadas para catálogos grandes (500+)."""
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from ui import stream_diagnostics_dialog as sdd
from ui.channel_model import ChannelListModel
from ui.mosaic_view import MAX_TILES, _SelectorCanales


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _channels(count):
    return [SimpleNamespace(name=f"Canal {i}", url=f"https://tv.test/{i}") for i in range(count)]


def test_mosaic_selector_caps_selection_at_max_tiles(qapp):
    selector = _SelectorCanales(_channels(600), on_iniciar=lambda _sel: None)

    for item, _channel in selector._items[: MAX_TILES + 2]:
        item.setCheckState(Qt.Checked)

    assert len(selector.seleccionados()) == MAX_TILES
    assert selector.iniciar_btn.isEnabled()


def test_mosaic_selector_unchecking_reenables_a_slot(qapp):
    selector = _SelectorCanales(_channels(10), on_iniciar=lambda _sel: None)
    items = [item for item, _channel in selector._items]
    for item in items[:MAX_TILES]:
        item.setCheckState(Qt.Checked)

    items[0].setCheckState(Qt.Unchecked)
    items[MAX_TILES].setCheckState(Qt.Checked)

    assert [ch.name for ch in selector.seleccionados()] == [
        f"Canal {i}" for i in range(1, MAX_TILES + 1)
    ]


def test_diagnostics_worker_emits_results_in_batches(qapp, monkeypatch):
    entries = [{"kind": "tv", "name": f"c{i}", "url": f"https://tv.test/{i}"} for i in range(60)]

    def fake_diagnose(items, progress, _cancel, max_workers):
        for index, entry in enumerate(items, start=1):
            progress({**entry, "status": "ok"}, index, len(items))

    monkeypatch.setattr(sdd, "diagnose_catalog", fake_diagnose)
    worker = sdd.StreamDiagnosticsWorker(entries)
    batches = []
    worker.results_ready.connect(
        lambda results, completed, total: batches.append((len(results), completed, total)),
        Qt.DirectConnection,
    )

    worker.run()

    assert batches == [(25, 25, 60), (25, 50, 60), (10, 60, 60)]


def test_bulk_update_signals_one_range_per_contiguous_block(qapp):
    model = ChannelListModel()
    model.set_entries([{"name": f"c{i}"} for i in range(100)])
    ranges = []
    model.dataChanged.connect(lambda top, bottom, _roles: ranges.append((top.row(), bottom.row())))

    model.update_entries(lambda entry: int(entry["name"][1:]) not in (40, 41))

    assert ranges == [(0, 39), (42, 99)]


def test_radio_reload_with_same_catalog_does_not_repopulate():
    from unittest.mock import Mock

    from ui.catalog_load_controller import CatalogLoadController, MergedCatalog

    stations = [SimpleNamespace(name="Radio 1", url="https://radio.test/1")]
    window = Mock(_is_closing=False, radio_stations_data=list(stations), tv_channels_data=[])
    window.settings.get.return_value = False
    controller = CatalogLoadController(window)

    controller._on_radio_stations_loaded(MergedCatalog(list(stations), frozenset()))

    window.lists.populate_radio_list.assert_not_called()


def test_identical_radio_request_is_not_stacked(monkeypatch):
    from unittest.mock import Mock

    from ui import catalog_load_controller as clc

    started = []
    monkeypatch.setattr(
        clc, "FetchWorker",
        lambda *args: Mock(start=lambda: started.append(args), isRunning=lambda: True),
    )
    window = Mock(_is_closing=False, _radio_worker=None)
    window.settings.get.return_value = "ES"
    controller = clc.CatalogLoadController(window)

    controller.load_radio_stations()
    controller.load_radio_stations()

    assert len(started) == 1
