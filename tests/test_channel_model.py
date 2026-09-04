from PySide6.QtWidgets import QApplication

from ui.channel_model import ChannelListModel, ChannelListView
from ui.widgets import ROLE_DATA, ROLE_FAV, ROLE_HEALTH


def _app():
    return QApplication.instance() or QApplication([])


def _entry(name, group="General", health=None):
    return {
        ROLE_DATA: {"type": "tv", "name": name, "url": f"https://{name}.test", "group": group},
        ROLE_FAV: False,
        ROLE_HEALTH: health,
    }


def test_channel_model_filters_without_destroying_catalog_entries():
    _app()
    model = ChannelListModel()
    entries = [_entry("Uno"), _entry("Dos"), _entry("Tres")]
    model.set_entries(entries)

    model.set_filter(lambda entry: entry[ROLE_DATA]["name"] != "Dos")

    assert model.rowCount() == 2
    assert model.data(model.index(0, 0), ROLE_DATA)["name"] == "Uno"
    assert len(model.entries()) == 3
    assert model.row_for_entry(entries[1]) == -1


def test_channel_model_sort_keeps_roles_and_view_adapter_compatible():
    _app()
    model = ChannelListModel()
    first, second = _entry("Zulu"), _entry("Alfa")
    first[ROLE_FAV] = True
    model.set_entries([first, second])
    view = ChannelListView()
    view.setModel(model)

    model.sort_entries(lambda entry: entry[ROLE_DATA]["name"])

    assert model.data(model.index(0, 0), ROLE_DATA)["name"] == "Alfa"
    assert view.count() == 2
    item = view.item(1)
    assert item.data(ROLE_DATA)["name"] == "Zulu"
    item.setData(ROLE_HEALTH, "slow")
    assert model.data(model.index(1, 0), ROLE_HEALTH) == "slow"
