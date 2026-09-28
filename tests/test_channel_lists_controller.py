"""
Cobertura de ui/channel_lists_controller.py: poblar y refrescar las listas
de TV, radio, favoritos e historial, ordenar el catálogo, marcar lo que
suena y los favoritos, los filtros de carpeta/categoría y la búsqueda.

La ventana es un SimpleNamespace con las mismas listas que MainWindow: TV y
radio son ChannelListView sobre ChannelListModel reales, favoritos e
historial son QListWidget reales -- igual que en producción (ver
MainWindow._make_list). Lo que toca disco (canales personalizados,
historial de diagnósticos, guardar favoritos) y la guía EPG se sustituyen.

No se prueban las ramas QListWidget de populate_tv_list/populate_radio_list,
sort_catalog, update_stream_health, update_epg_subtitles y
filter_current_list para TV/radio: en la app esas dos listas son siempre
ChannelListView, así que esas ramas no se ejecutan.
"""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QComboBox, QLineEdit, QListWidget

from core import favorites as real_favorites
from ui import channel_lists_controller as clm
from ui.channel_lists_controller import ChannelListsController
from ui.channel_model import ChannelListModel, ChannelListView
from ui.widgets import (
    ROLE_CUSTOM, ROLE_DATA, ROLE_FAV, ROLE_HEALTH, ROLE_LOGO, ROLE_LOGO_REQUESTED,
    ROLE_PLAYING,
)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _channel(name, group="", tvg_id="", url=None, logo=""):
    return SimpleNamespace(
        name=name, url=url or f"https://tv.test/{name}", logo=logo, tvg_id=tvg_id,
        group=group, alternate_urls=[f"https://respaldo.test/{name}"],
    )


def _station(name, bitrate=0, tags="", url=None):
    return SimpleNamespace(
        name=name, url=url or f"https://radio.test/{name}", favicon=f"https://ico/{name}",
        bitrate=bitrate, tags=tags, alternate_urls=[],
    )


@pytest.fixture
def disk(monkeypatch):
    """Lo que el controlador lee/escribe fuera de la ventana."""
    state = SimpleNamespace(
        custom_tv=[], custom_radio=[], health=[], health_error=None, now_playing={},
    )

    class FakeHealthStore:
        def list(self):
            if state.health_error:
                raise state.health_error
            return list(state.health)

    def get_now_next(_guide, tvg_id):
        title = state.now_playing.get(tvg_id)
        return (SimpleNamespace(title=title) if title else None), None

    monkeypatch.setattr(clm, "tv_channels", SimpleNamespace(
        load_custom_channels=lambda: [SimpleNamespace(name=n) for n in state.custom_tv]))
    monkeypatch.setattr(clm, "radio_stations", SimpleNamespace(
        load_custom_stations=lambda: [SimpleNamespace(name=n) for n in state.custom_radio]))
    monkeypatch.setattr(clm, "StreamHealthStore", FakeHealthStore)
    monkeypatch.setattr(clm, "epg_module", SimpleNamespace(get_now_next=get_now_next))
    state.reorder = Mock(side_effect=lambda favs: favs)
    monkeypatch.setattr(clm, "fav_store", SimpleNamespace(
        get_folders=real_favorites.get_folders,
        is_favorite=real_favorites.is_favorite,
        reorder=state.reorder,
    ))
    return state


@pytest.fixture
def win(qapp):
    tv_model, radio_model = ChannelListModel(), ChannelListModel()
    tv_list, radio_list = ChannelListView(), ChannelListView()
    tv_list.setModel(tv_model)
    radio_list.setModel(radio_model)
    health_filter = QComboBox()
    for label, key in (("Todos", "all"), ("Estables", "stable"), ("Con problemas", "issues"),
                       ("Sin comprobar", "unchecked"), ("Antiguos", "stale")):
        health_filter.addItem(label, key)
    w = SimpleNamespace(
        tv_list=tv_list, radio_list=radio_list, tv_model=tv_model, radio_model=radio_model,
        fav_list=QListWidget(), hist_list=QListWidget(), home_fav_list=QListWidget(),
        group_filter=QComboBox(), health_filter=health_filter, search_box=QLineEdit(),
        stack=Mock(), logo_loader=Mock(), library_sidebar=Mock(), groups_sidebar=None,
        favorites=[], history=[], settings={}, epg_guide={"x": []},
        tv_channels_data=[], current_type=None, current_name=None,
        _playback_failed=False, _active_list=None, _active_row=-1, _tv_sidebar_groups=None,
    )
    yield w
    for widget in (tv_list, radio_list, w.fav_list, w.hist_list, w.home_fav_list, w.group_filter,
                   health_filter, w.search_box):
        widget.deleteLater()


@pytest.fixture
def ctrl(win, disk):
    return ChannelListsController(win)


def _entries(view):
    return [view.model().entry_at(r) for r in range(view.count())]


def _names(view):
    return [(item.data(ROLE_DATA) or {}).get("name") for item in _items(view)]


def _items(view):
    return [view.item(r) for r in range(view.count())]


def _visible_names(widget):
    if isinstance(widget, ChannelListView):
        return _names(widget)
    return [widget.item(r).data(ROLE_DATA)["name"]
            for r in range(widget.count()) if not widget.item(r).isHidden()]


# --------------------------------------------------------------------------
# Poblado de TV y radio
# --------------------------------------------------------------------------

def test_populate_tv_list_builds_rows_with_state(ctrl, win, disk):
    disk.custom_tv = ["Mi canal"]
    disk.now_playing = {"la1": "Telediario", "c4": "Cine"}
    disk.health = [{"kind": "tv", "url": "https://tv.test/La 1", "status": "stable",
                    "checked_at": "2026-09-27T10:00:00", "latency_ms": 120}]
    win.favorites = [{"type": "tv", "name": "La 1"}]
    win.current_type, win.current_name = "tv", "Mi canal"

    ctrl.populate_tv_list([
        _channel("La 1", group="Generalistas", tvg_id="la1"),
        _channel("Cuatro", tvg_id="c4"),
        _channel("Mi canal", group="Locales"),
    ])

    la1, cuatro, mio = _entries(win.tv_list)
    assert la1[ROLE_DATA]["subtitle"] == "Generalistas · Ahora: Telediario"
    assert la1[ROLE_DATA]["alternate_urls"] == ["https://respaldo.test/La 1"]
    assert la1[ROLE_FAV] and not la1[ROLE_CUSTOM] and not la1[ROLE_PLAYING]
    assert la1[ROLE_HEALTH] == "stable"
    assert la1[ROLE_DATA]["health_checked_at"] == "2026-09-27T10:00:00"
    assert la1[Qt.ToolTipRole] == "Último diagnóstico: 2026-09-27T10:00:00 · 120 ms"
    assert cuatro[ROLE_DATA]["subtitle"] == "Ahora: Cine"
    assert cuatro[ROLE_HEALTH] is None and cuatro[Qt.ToolTipRole] == ""
    assert "health_checked_at" not in cuatro[ROLE_DATA]
    assert mio[ROLE_DATA]["subtitle"] == "Locales"
    assert mio[ROLE_CUSTOM] and mio[ROLE_PLAYING]


def test_populate_tv_list_without_guide_shows_only_group(ctrl, win, disk):
    win.epg_guide = {}
    disk.now_playing = {"la1": "Telediario"}

    ctrl.populate_tv_list([_channel("La 1", group="Generalistas", tvg_id="la1")])

    assert _entries(win.tv_list)[0][ROLE_DATA]["subtitle"] == "Generalistas"


def test_populate_tv_list_survives_unreadable_health_history(ctrl, win, disk):
    disk.health_error = OSError("bloqueado")

    ctrl.populate_tv_list([_channel("La 1")])

    assert _entries(win.tv_list)[0][ROLE_HEALTH] is None


def test_populate_radio_list_builds_rows_with_state(ctrl, win, disk):
    disk.custom_radio = ["Mi radio"]
    disk.health = [{"kind": "radio", "url": "https://radio.test/RNE", "status": "down",
                    "checked_at": "2026-09-20T08:00:00", "latency_ms": 0}]
    win.favorites = [{"type": "radio", "name": "RNE"}]
    win.current_type, win.current_name = "radio", "RNE"

    ctrl.populate_radio_list([
        _station("RNE", bitrate=128), _station("Mi radio", tags="pop,rock"), _station("Muda"),
    ])

    rne, mia, muda = _entries(win.radio_list)
    assert rne[ROLE_DATA]["subtitle"] == "128 kbps"
    assert rne[ROLE_DATA]["logo"] == "https://ico/RNE"
    assert rne[ROLE_FAV] and rne[ROLE_PLAYING] and not rne[ROLE_CUSTOM]
    assert rne[ROLE_HEALTH] == "down"
    assert rne[Qt.ToolTipRole].startswith("Último diagnóstico: 2026-09-20T08:00:00")
    assert mia[ROLE_DATA]["subtitle"] == "pop,rock" and mia[ROLE_CUSTOM]
    assert muda[ROLE_DATA]["subtitle"] == ""


# --------------------------------------------------------------------------
# Actualizaciones parciales: diagnóstico y guía EPG
# --------------------------------------------------------------------------

def test_update_stream_health_touches_only_matching_rows(ctrl, win):
    ctrl.populate_tv_list([_channel("La 1"), _channel("Cuatro")])
    ctrl.populate_radio_list([_station("RNE")])

    ctrl.update_stream_health([
        {"kind": "tv", "url": "https://tv.test/Cuatro", "status": "stable",
         "checked_at": "2026-09-28T12:00:00", "latency_ms": 80},
        {"kind": "radio", "url": "https://tv.test/La 1", "status": "offline"},
    ])

    la1, cuatro = _entries(win.tv_list)
    assert la1[ROLE_HEALTH] is None
    assert cuatro[ROLE_HEALTH] == "stable"
    assert cuatro[ROLE_DATA]["health_checked_at"] == "2026-09-28T12:00:00"
    assert cuatro[Qt.ToolTipRole] == "Último diagnóstico: 2026-09-28T12:00:00 · 80 ms"
    assert _entries(win.radio_list)[0][ROLE_HEALTH] is None


def test_update_stream_health_with_no_results_does_nothing(ctrl, win):
    ctrl.populate_tv_list([_channel("La 1")])

    ctrl.update_stream_health([])

    assert _entries(win.tv_list)[0][ROLE_HEALTH] is None


def test_update_epg_subtitles_refreshes_now_playing(ctrl, win, disk):
    ctrl.populate_tv_list([
        _channel("La 1", group="Generalistas", tvg_id="la1"), _channel("Sin guía", group="Otros"),
    ])
    disk.now_playing = {"la1": "Informe semanal"}

    ctrl.update_epg_subtitles()

    la1, sin_guia = _entries(win.tv_list)
    assert la1[ROLE_DATA]["subtitle"] == "Generalistas · Ahora: Informe semanal"
    assert sin_guia[ROLE_DATA]["subtitle"] == "Otros"


# --------------------------------------------------------------------------
# Orden del catálogo
# --------------------------------------------------------------------------

CANALES = ["Telecinco", "antena 3", "La 1", "Cuatro"]


def test_sort_catalog_source_order_keeps_feed_order(ctrl, win):
    ctrl.populate_tv_list([_channel(n) for n in CANALES])

    assert _names(win.tv_list) == CANALES


def test_sort_catalog_by_name_is_case_insensitive(ctrl, win):
    win.settings["catalog_sort_tv"] = "name"

    ctrl.populate_tv_list([_channel(n) for n in CANALES])

    assert _names(win.tv_list) == ["antena 3", "Cuatro", "La 1", "Telecinco"]


def test_sort_catalog_favorites_first_then_by_name(ctrl, win):
    win.settings["catalog_sort_radio"] = "favorites"
    win.favorites = [{"type": "radio", "name": "Telecinco"}, {"type": "radio", "name": "La 1"}]

    ctrl.populate_radio_list([_station(n) for n in CANALES])

    assert _names(win.radio_list) == ["La 1", "Telecinco", "antena 3", "Cuatro"]


def test_sort_catalog_ignores_non_catalog_lists(ctrl, win):
    win.settings["catalog_sort_tv"] = "name"
    win.fav_list.addItem("x")

    ctrl.sort_catalog(win.fav_list)

    assert win.fav_list.count() == 1


# --------------------------------------------------------------------------
# Favoritos e historial
# --------------------------------------------------------------------------

def test_refresh_favorites_tab_uses_folder_as_group(ctrl, win, disk):
    disk.custom_radio = ["Mi radio"]
    win.favorites = [
        {"type": "tv", "name": "La 1", "url": "u1", "folder": "Noticias"},
        {"type": "radio", "name": "Mi radio", "url": "u2"},
    ]
    win.current_type, win.current_name = "tv", "La 1"

    ctrl.refresh_favorites_tab()

    la1, mia = win.fav_list.item(0), win.fav_list.item(1)
    assert la1.data(ROLE_DATA)["group"] == "Noticias"
    assert la1.data(ROLE_FAV) and la1.data(ROLE_PLAYING) and not la1.data(ROLE_CUSTOM)
    assert mia.data(ROLE_DATA)["group"] == "" and mia.data(ROLE_CUSTOM)
    assert "group" not in win.favorites[0]           # no toca los favoritos guardados
    win.library_sidebar.refresh.assert_called_once()


def test_refresh_history_tab_shows_timestamp_and_favorite(ctrl, win, disk):
    disk.custom_tv = ["Mi canal"]
    win.favorites = [{"type": "tv", "name": "La 1"}]
    win.history = [
        {"type": "tv", "name": "La 1", "url": "u1", "timestamp": "28/09 10:00"},
        {"type": "tv", "name": "Mi canal", "url": "u2", "timestamp": "27/09 22:15"},
    ]

    ctrl.refresh_history_tab()

    la1, mio = win.hist_list.item(0), win.hist_list.item(1)
    assert la1.data(ROLE_DATA)["subtitle"] == "28/09 10:00"
    assert la1.data(ROLE_FAV) and not mio.data(ROLE_FAV)
    assert mio.data(ROLE_CUSTOM)
    win.library_sidebar.refresh.assert_called_once()


def test_refresh_tabs_without_sidebar(ctrl, win):
    win.library_sidebar = None
    win.favorites = [{"type": "tv", "name": "La 1"}]

    ctrl.refresh_favorites_tab()
    ctrl.refresh_history_tab()

    assert win.fav_list.count() == 1


def test_persist_favorites_order_follows_dragged_rows(ctrl, win, disk):
    a = {"type": "tv", "name": "A", "folder": "X"}
    b = {"type": "radio", "name": "B"}
    c = {"type": "tv", "name": "C"}
    win.favorites = [a, b, c]
    ctrl.refresh_favorites_tab()
    arrastrada = win.fav_list.takeItem(2)            # el usuario sube C arriba del todo
    win.fav_list.insertItem(0, arrastrada)
    win.fav_list.takeItem(2)                          # y B desaparece de la vista (no debería)

    ctrl.persist_favorites_order()

    disk.reorder.assert_called_once()
    assert win.favorites == [c, a, b]                 # B no se pierde: va al final
    assert win.favorites[1] is a                      # se guardan los originales, sin "group"


# --------------------------------------------------------------------------
# Marcar lo que suena y los favoritos en todas las listas
# --------------------------------------------------------------------------

def _load_all_lists(ctrl, win):
    ctrl.populate_tv_list([_channel("La 1"), _channel("Cuatro")])
    ctrl.populate_radio_list([_station("RNE")])
    win.favorites = [{"type": "tv", "name": "La 1"}, {"type": "tv", "name": "Cuatro"}]
    ctrl.refresh_favorites_tab()
    win.history = [{"type": "tv", "name": "Cuatro", "url": "u"}]
    ctrl.refresh_history_tab()


def _playing_flags(win):
    return {
        "tv": [bool(e[ROLE_PLAYING]) for e in _entries(win.tv_list)],
        "radio": [bool(e[ROLE_PLAYING]) for e in _entries(win.radio_list)],
        "fav": [bool(win.fav_list.item(r).data(ROLE_PLAYING)) for r in range(win.fav_list.count())],
        "hist": [bool(win.hist_list.item(r).data(ROLE_PLAYING)) for r in range(win.hist_list.count())],
    }


def test_mark_playing_everywhere_follows_current_channel(ctrl, win):
    _load_all_lists(ctrl, win)
    win.current_type, win.current_name = "tv", "Cuatro"

    ctrl.mark_playing_everywhere()

    assert _playing_flags(win) == {
        "tv": [False, True], "radio": [False], "fav": [False, True], "hist": [True],
    }


def test_mark_playing_everywhere_clears_marks_when_playback_failed(ctrl, win):
    _load_all_lists(ctrl, win)
    win.current_type, win.current_name = "tv", "Cuatro"
    ctrl.mark_playing_everywhere()
    win._playback_failed = True

    ctrl.mark_playing_everywhere()

    assert not any(any(flags) for flags in _playing_flags(win).values())


def test_mark_favorites_everywhere_after_toggling(ctrl, win):
    _load_all_lists(ctrl, win)
    win.favorites = [{"type": "radio", "name": "RNE"}]

    ctrl.mark_favorites_everywhere()

    assert [bool(e[ROLE_FAV]) for e in _entries(win.tv_list)] == [False, False]
    assert [bool(e[ROLE_FAV]) for e in _entries(win.radio_list)] == [True]
    assert win.hist_list.item(0).data(ROLE_FAV) is False


# --------------------------------------------------------------------------
# Desplegables de carpeta / categoría
# --------------------------------------------------------------------------

def _combo_items(combo):
    return [combo.itemText(i) for i in range(combo.count())]


def test_refresh_folder_filter_lists_folders_and_keeps_selection(ctrl, win):
    win.favorites = [{"name": "A", "folder": "Noticias"}, {"name": "B", "folder": "Deportes"},
                     {"name": "C"}]
    ctrl.refresh_folder_filter()
    win.group_filter.setCurrentText("Noticias")
    emitted = []
    win.group_filter.currentTextChanged.connect(emitted.append)

    ctrl.refresh_folder_filter()

    assert _combo_items(win.group_filter) == [
        "Todas las carpetas", "Sin carpeta", "Deportes", "Noticias"]
    assert win.group_filter.currentText() == "Noticias"
    assert emitted == []                              # sin señales durante el refresco


def test_refresh_folder_filter_without_folders_falls_back_to_all(ctrl, win):
    win.group_filter.addItem("Noticias")
    win.group_filter.setCurrentText("Noticias")

    ctrl.refresh_folder_filter()

    assert _combo_items(win.group_filter) == ["Todas las carpetas"]
    assert win.group_filter.currentIndex() == 0


def test_refresh_group_filter_fills_combo_and_sidebar_counts(ctrl, win):
    win.tv_channels_data = [_channel("A", group="Noticias"), _channel("B", group="Deportes"),
                            _channel("C", group="Noticias"), _channel("D")]
    win.groups_sidebar = Mock(current_selection=Mock(return_value={"Noticias"}))

    ctrl.refresh_group_filter()

    assert _combo_items(win.group_filter) == ["Todas las categorías", "Deportes", "Noticias"]
    win.groups_sidebar.set_groups.assert_called_once_with({"Noticias": 2, "Deportes": 1})
    assert win._tv_sidebar_groups == {"Noticias"}


# --------------------------------------------------------------------------
# Búsqueda y filtros
# --------------------------------------------------------------------------

def _show(win, widget):
    win.stack.currentWidget.return_value = widget


def _set_health(win, key):
    win.health_filter.setCurrentIndex(win.health_filter.findData(key))


def _load_tv_with_health(ctrl, win, disk):
    disk.health = [
        {"kind": "tv", "url": "https://tv.test/La 1", "status": "stable",
         "checked_at": "2999-01-01T00:00:00"},
        {"kind": "tv", "url": "https://tv.test/La 2", "status": "down",
         "checked_at": "2000-01-01T00:00:00"},
    ]
    ctrl.populate_tv_list([
        _channel("La 1", group="Generalistas"), _channel("La 2", group="Cultura"),
        _channel("Cuatro", group="Generalistas"),
    ])
    _show(win, win.tv_list)


def test_filter_tv_by_text_is_case_insensitive(ctrl, win, disk):
    _load_tv_with_health(ctrl, win, disk)
    win.search_box.setText("  la ")

    ctrl.filter_current_list()

    assert _visible_names(win.tv_list) == ["La 1", "La 2"]


def test_filter_tv_by_sidebar_groups(ctrl, win, disk):
    _load_tv_with_health(ctrl, win, disk)
    win._tv_sidebar_groups = {"Generalistas"}

    ctrl.filter_current_list()

    assert _visible_names(win.tv_list) == ["La 1", "Cuatro"]


@pytest.mark.parametrize(("key", "expected"), [
    ("stable", ["La 1"]),
    ("issues", ["La 2"]),
    ("unchecked", ["Cuatro"]),
    ("stale", ["La 2", "Cuatro"]),
    ("all", ["La 1", "La 2", "Cuatro"]),
])
def test_filter_tv_by_health(ctrl, win, disk, key, expected):
    _load_tv_with_health(ctrl, win, disk)
    _set_health(win, key)

    ctrl.filter_current_list()

    assert _visible_names(win.tv_list) == expected


def test_filter_radio_ignores_folder_combo(ctrl, win):
    ctrl.populate_radio_list([_station("RNE"), _station("Cadena SER")])
    win.group_filter.addItem("Noticias")
    win.group_filter.setCurrentText("Noticias")
    _show(win, win.radio_list)
    win.search_box.setText("rne")

    ctrl.filter_current_list()

    assert _visible_names(win.radio_list) == ["RNE"]


def _load_favorites_with_folders(ctrl, win):
    win.favorites = [
        {"type": "tv", "name": "La 1", "folder": "Noticias"},
        {"type": "tv", "name": "Cuatro"},
        {"type": "radio", "name": "RNE", "folder": "Noticias"},
    ]
    ctrl.refresh_favorites_tab()
    ctrl.refresh_folder_filter()
    _show(win, win.fav_list)


@pytest.mark.parametrize(("folder", "expected"), [
    ("Todas las carpetas", ["La 1", "Cuatro", "RNE"]),
    ("Sin carpeta", ["Cuatro"]),
    ("Noticias", ["La 1", "RNE"]),
])
def test_filter_favorites_by_folder(ctrl, win, folder, expected):
    _load_favorites_with_folders(ctrl, win)
    win.group_filter.setCurrentText(folder)

    ctrl.filter_current_list()

    assert _visible_names(win.fav_list) == expected


def test_filter_favorites_ignores_health_filter(ctrl, win):
    """Las filas de favoritos no llevan diagnóstico: el filtro de salud no
    puede vaciar la pestaña."""
    _load_favorites_with_folders(ctrl, win)
    _set_health(win, "stable")

    ctrl.filter_current_list()

    assert _visible_names(win.fav_list) == ["La 1", "Cuatro", "RNE"]


def test_filter_history_by_text_only(ctrl, win):
    win.history = [{"type": "tv", "name": "La 1", "url": "u"},
                   {"type": "radio", "name": "RNE", "url": "u"}]
    ctrl.refresh_history_tab()
    _show(win, win.hist_list)
    win.group_filter.addItem("Noticias")
    win.group_filter.setCurrentText("Noticias")
    win.search_box.setText("la")

    ctrl.filter_current_list()

    assert _visible_names(win.hist_list) == ["La 1"]


def test_filter_on_a_non_list_section_does_nothing(ctrl, win):
    _show(win, object())

    ctrl.filter_current_list()


# --------------------------------------------------------------------------
# Logos
# --------------------------------------------------------------------------

def test_load_visible_logos_requests_each_visible_logo_once(ctrl, win):
    """Catálogo más largo que la pantalla: solo se piden los logos de las
    filas visibles, y cada uno una sola vez."""
    ctrl.populate_tv_list([
        _channel("La 1", logo="https://logo/la1"), _channel("Sin logo"),
        _channel("Cuatro", logo="https://logo/c4"),
        *[_channel(f"Relleno {i}", logo=f"https://logo/r{i}") for i in range(200)],
    ])
    win.tv_list.resize(300, 400)
    win.tv_list.show()
    QApplication.processEvents()

    ctrl.load_visible_logos(win.tv_list)
    ctrl.load_visible_logos(win.tv_list)

    pedidos = [c.args[0] for c in win.logo_loader.load.call_args_list]
    assert pedidos[:3] == ["https://logo/la1", "https://logo/c4", "https://logo/r0"]
    assert len(pedidos) == len(set(pedidos)) < 200
    assert "https://logo/r199" not in pedidos
    assert _entries(win.tv_list)[0][ROLE_LOGO_REQUESTED] is True

    listo = win.logo_loader.load.call_args_list[0].args[1]
    listo("pixmap-la1")
    assert _entries(win.tv_list)[0][ROLE_LOGO] == "pixmap-la1"
    win.tv_list.hide()


@pytest.mark.parametrize("lista", ["tv", "fav"])
def test_load_visible_logos_on_a_list_shorter_than_the_screen(ctrl, win, lista):
    """Con menos filas de las que caben (pocos favoritos, una búsqueda con
    pocos resultados, un grupo pequeño) la esquina inferior no cae sobre
    ninguna fila: antes no se pedía ningún logo, y sin barra de
    desplazamiento no había otra ocasión de pedirlos."""
    if lista == "tv":
        ctrl.populate_tv_list([
            _channel("La 1", logo="https://logo/la1"), _channel("Cuatro", logo="https://logo/c4"),
        ])
        widget = win.tv_list
    else:
        win.favorites = [
            {"type": "tv", "name": "La 1", "logo": "https://logo/la1"},
            {"type": "tv", "name": "Cuatro", "logo": "https://logo/c4"},
        ]
        ctrl.refresh_favorites_tab()
        widget = win.fav_list
    widget.resize(300, 400)
    widget.show()
    QApplication.processEvents()

    ctrl.load_visible_logos(widget)

    pedidos = [c.args[0] for c in win.logo_loader.load.call_args_list]
    assert pedidos == ["https://logo/la1", "https://logo/c4"]
    widget.hide()


def test_load_visible_logos_in_grid_mode_requests_only_visible_cards(ctrl, win):
    """En cuadrícula la esquina inferior derecha suele caer en el margen que
    sobra tras la última columna, también en mitad de un catálogo largo:
    no puede ni quedarse sin logos ni pedir los de todo el catálogo."""
    from PySide6.QtCore import QSize

    ctrl.populate_tv_list([_channel(f"C{i}", logo=f"https://logo/{i}") for i in range(300)])
    win.tv_list.setViewMode(ChannelListView.IconMode)
    win.tv_list.setGridSize(QSize(100, 100))
    win.tv_list.resize(350, 400)                  # 3 columnas y ~48 px de margen
    win.tv_list.show()
    QApplication.processEvents()

    ctrl.load_visible_logos(win.tv_list)

    pedidos = [c.args[0] for c in win.logo_loader.load.call_args_list]
    assert pedidos[:3] == ["https://logo/0", "https://logo/1", "https://logo/2"]
    assert 9 <= len(pedidos) <= 18                # 3-4 filas visibles de 3 tarjetas (+ parcial)
    win.tv_list.hide()


@pytest.mark.parametrize("grid", [False, True])
def test_load_visible_logos_after_scrolling_to_the_middle(ctrl, win, grid):
    from PySide6.QtCore import QSize

    ctrl.populate_tv_list([_channel(f"C{i}", logo=f"https://logo/{i}") for i in range(600)])
    if grid:
        win.tv_list.setViewMode(ChannelListView.IconMode)
        win.tv_list.setGridSize(QSize(100, 100))
    win.tv_list.resize(350, 400)
    win.tv_list.show()
    QApplication.processEvents()
    win.tv_list.scrollTo(win.tv_model.index(300, 0), ChannelListView.PositionAtTop)
    QApplication.processEvents()

    ctrl.load_visible_logos(win.tv_list)

    filas = sorted(int(c.args[0].rsplit("/", 1)[1]) for c in win.logo_loader.load.call_args_list)
    assert filas[0] == 300                                  # la fila llevada arriba
    assert filas == list(range(filas[0], filas[-1] + 1))   # un bloque seguido
    assert len(filas) <= 60                                 # solo lo que cabe en pantalla
    win.tv_list.hide()


def test_history_tab_requests_its_logos(ctrl, win):
    """La pestaña Historial no pedía sus logos al rellenarse (solo al
    desplazar la lista), así que con pocas entradas nunca se veían."""
    win.history = [
        {"type": "tv", "name": "La 1", "url": "u1", "logo": "https://logo/la1"},
        {"type": "radio", "name": "RNE", "url": "u2"},                 # entrada antigua sin logo
    ]
    win.hist_list.resize(300, 400)
    win.hist_list.show()
    QApplication.processEvents()

    ctrl.refresh_history_tab()

    pedidos = [c.args[0] for c in win.logo_loader.load.call_args_list]
    assert pedidos == ["https://logo/la1"]
    win.hist_list.hide()


def test_load_visible_logos_skips_hidden_or_empty_lists(ctrl, win):
    ctrl.populate_tv_list([_channel("La 1", logo="https://logo/la1")])

    ctrl.load_visible_logos(win.tv_list)          # lista no visible
    ctrl.load_visible_logos(win.radio_list)       # lista vacía

    win.logo_loader.load.assert_not_called()


def test_request_logo_without_url_does_nothing(ctrl, win):
    ctrl.request_logo("", Mock(), win.tv_list)

    win.logo_loader.load.assert_not_called()


def test_queue_logo_batch_splits_work_and_skips_deleted_items(ctrl, win, monkeypatch):
    programadas = []
    monkeypatch.setattr(clm, "QTimer", Mock(singleShot=lambda ms, fn: programadas.append(fn)))
    pedidos = []

    def request_logo(url, item, _list):
        if item == "borrado":
            raise RuntimeError("C++ object already deleted")
        pedidos.append(url)

    monkeypatch.setattr(ctrl, "request_logo", request_logo)
    pending = [("u1", "i1"), ("u2", "borrado"), ("u3", "i3")]

    ctrl._queue_logo_batch(pending, win.tv_list, batch_size=2)
    assert pedidos == ["u1"] and len(programadas) == 1

    programadas.pop()()
    assert pedidos == ["u1", "u3"] and programadas == []

    ctrl._queue_logo_batch([], win.tv_list)
    assert programadas == []
