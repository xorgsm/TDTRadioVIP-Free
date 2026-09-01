from pathlib import Path
from unittest.mock import Mock

from ui.catalog_load_controller import CatalogLoadController
from ui.channel_lists_controller import ChannelListsController
from ui.widgets import ROLE_DATA, ROLE_HEALTH


class FakeItem:
    def __init__(self, url):
        self.values = {ROLE_DATA: {"url": url}}
        self.tooltip = ""

    def data(self, role):
        return self.values.get(role)

    def setData(self, role, value):
        self.values[role] = value

    def setToolTip(self, value):
        self.tooltip = value


class FakeList:
    def __init__(self, *urls):
        self.items = [FakeItem(url) for url in urls]
        self.updates = []

    def count(self):
        return len(self.items)

    def item(self, index):
        return self.items[index]

    def setUpdatesEnabled(self, enabled):
        self.updates.append(enabled)


def test_background_diagnostics_updates_health_without_repopulating(monkeypatch):
    recorded = [{
        "kind": "tv", "url": "https://tv.test", "status": "stable",
        "checked_at": "2026-09-01T10:00:00+00:00", "latency_ms": 20,
    }]
    monkeypatch.setattr("ui.catalog_load_controller.record_results", lambda _results: recorded)
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


def test_health_update_changes_matching_items_in_place():
    tv_list = FakeList("https://one.test", "https://two.test")
    radio_list = FakeList("https://radio.test")
    controller = ChannelListsController(Mock(tv_list=tv_list, radio_list=radio_list))

    controller.update_stream_health([{
        "kind": "tv", "url": "https://two.test", "status": "slow",
        "checked_at": "2026-09-01T10:00:00+00:00", "latency_ms": 1800,
    }])

    assert tv_list.items[0].data(ROLE_HEALTH) is None
    assert tv_list.items[1].data(ROLE_HEALTH) == "slow"
    assert tv_list.items[1].data(ROLE_DATA)["health_checked_at"] == "2026-09-01T10:00:00+00:00"
    assert "1800 ms" in tv_list.items[1].tooltip
    assert tv_list.updates == [False, True]
    assert radio_list.updates == [False, True]
