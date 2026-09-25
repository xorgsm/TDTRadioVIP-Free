"""
Cobertura de ui/library_controller.py: importar listas M3U (archivo local
o URL), borrar con "Deshacer", borrado por lotes, ocultar y restaurar
canales de la lista pública.

La ventana es un MagicMock con las listas en memoria reales; core.channels,
core.radio y core.favorites escriben de verdad en un tmp_path. Los
diálogos modales de Qt se sustituyen: se prueba qué cambia en los datos,
no el dibujo.
"""
from unittest.mock import MagicMock, Mock

import pytest
import requests

from core import channels, favorites, radio
from ui import library_controller as lc_module
from ui.library_controller import LibraryController

M3U_ES = '#EXTM3U\n#EXTINF:-1 group-title="Música",Canción España\nhttps://stream.test/es\n'


@pytest.fixture
def profile_dir(tmp_path, monkeypatch):
    for modulo in (channels, radio, favorites):
        monkeypatch.setattr(modulo, "get_profile_data_dir", lambda: tmp_path)
    return tmp_path


@pytest.fixture
def ui_stubs(monkeypatch):
    monkeypatch.setattr(lc_module, "QMessageBox", Mock())
    toast = Mock()
    monkeypatch.setattr(lc_module, "show_toast", toast)
    return toast


@pytest.fixture
def win(profile_dir, ui_stubs):
    w = MagicMock()
    w._is_closing = False
    w.tv_channels_data = []
    w.radio_stations_data = []
    w.favorites = []
    w.current_type = None
    w.current_name = None
    return w


@pytest.fixture
def ctrl(win):
    return LibraryController(win)


# --------------------------------------------------------------------------
# Importar lista M3U: lectura y codificación
# --------------------------------------------------------------------------

@pytest.mark.parametrize("codificacion", ["utf-8", "utf-8-sig", "cp1252"])
def test_import_from_local_file_keeps_accents(tmp_path, codificacion):
    ruta = tmp_path / "lista.m3u"
    ruta.write_bytes(M3U_ES.encode(codificacion))

    lista = LibraryController._fetch_and_parse_playlist(str(ruta))

    assert [c.name for c in lista] == ["Canción España"]


def test_import_from_url_decodes_bytes_not_guessed_text(monkeypatch):
    respuesta = requests.models.Response()
    respuesta._content = M3U_ES.encode("utf-8")
    respuesta.status_code = 200
    respuesta.encoding = "ISO-8859-1"  # lo que requests supone para text/plain sin charset
    monkeypatch.setattr(lc_module.requests, "get", Mock(return_value=respuesta))

    lista = LibraryController._fetch_and_parse_playlist("https://listas.test/es.m3u")

    assert lista[0].name == "Canción España"


def test_import_source_errors_return_none(tmp_path, monkeypatch):
    monkeypatch.setattr(lc_module.requests, "get", Mock(side_effect=requests.ConnectionError()))

    assert LibraryController._fetch_and_parse_playlist("https://caida.test/x.m3u") is None
    assert LibraryController._fetch_and_parse_playlist(str(tmp_path / "no-existe.m3u")) is None


# --------------------------------------------------------------------------
# Importar lista M3U: qué se añade
# --------------------------------------------------------------------------

def test_import_tv_adds_only_new_channels_and_persists_them(ctrl, win):
    win.tv_channels_data = [channels.Channel("La 1", "https://ya")]
    parsed = channels.parse_m3u(
        "#EXTINF:-1,La 1\nhttps://x\n#EXTINF:-1,Antena 3\nhttps://a3\n"
    )

    ctrl._on_playlist_fetched(parsed, "tv")

    assert [c.name for c in win.tv_channels_data] == ["La 1", "Antena 3"]
    assert [c.name for c in channels.load_custom_channels()] == ["Antena 3"]
    assert "añadido 1 nuevos" in lc_module.QMessageBox.information.call_args.args[2]


def test_import_radio_converts_channels_to_stations(ctrl, win):
    parsed = channels.parse_m3u('#EXTINF:-1 tvg-logo="l.png" group-title="Pop",Los 40\nhttps://40\n')

    ctrl._on_playlist_fetched(parsed, "radio")

    guardadas = radio.load_custom_stations()
    assert [(s.name, s.url, s.favicon, s.tags) for s in guardadas] == [("Los 40", "https://40", "l.png", "Pop")]
    assert [s.name for s in win.radio_stations_data] == ["Los 40"]


@pytest.mark.parametrize("parsed, titulo", [(None, "No se pudo importar"), ([], "Lista vacía")])
def test_import_failure_or_empty_list_warns_and_changes_nothing(ctrl, win, parsed, titulo):
    ctrl._on_playlist_fetched(parsed, "tv")

    assert lc_module.QMessageBox.warning.call_args.args[1] == titulo
    assert channels.load_custom_channels() == []


def test_import_result_after_window_closed_is_ignored(ctrl, win):
    win._is_closing = True

    ctrl._on_playlist_fetched(channels.parse_m3u("#EXTINF:-1,X\nhttps://x\n"), "tv")

    assert channels.load_custom_channels() == []


# --------------------------------------------------------------------------
# Borrar con "Deshacer"
# --------------------------------------------------------------------------

def test_delete_custom_channel_then_undo_restores_it_and_its_favorite(ctrl, win, ui_stubs):
    canal = channels.Channel("Mi canal", "https://mio", logo="l.png")
    channels.add_custom_channel(canal)
    win.tv_channels_data = [canal]
    win.favorites = favorites.toggle_favorite("tv", "Mi canal", "https://mio")

    ctrl.delete_custom_entry({"type": "tv", "name": "Mi canal", "url": "https://mio"})

    assert channels.load_custom_channels() == []
    assert win.tv_channels_data == []
    assert not favorites.is_favorite(win.favorites, "tv", "Mi canal")

    deshacer = ui_stubs.call_args.kwargs["on_undo"]
    deshacer()

    assert [c.name for c in channels.load_custom_channels()] == ["Mi canal"]
    assert favorites.is_favorite(win.favorites, "tv", "Mi canal")


def test_deleting_the_playing_entry_stops_playback(ctrl, win):
    estacion = radio.Station(name="Mi radio", url="https://r")
    radio.add_custom_station(estacion)
    win.radio_stations_data = [estacion]
    win.current_type, win.current_name = "radio", "Mi radio"

    ctrl.delete_custom_entry({"type": "radio", "name": "Mi radio"})

    win.playback.stop_playback.assert_called_once()
    assert radio.load_custom_stations() == []


# --------------------------------------------------------------------------
# Lotes, ocultar y restaurar
# --------------------------------------------------------------------------

def test_batch_delete_removes_entries_and_favorites(ctrl, win):
    for nombre in ("A", "B", "C"):
        channels.add_custom_channel(channels.Channel(nombre, f"https://{nombre}"))
    win.tv_channels_data = channels.load_custom_channels()
    win.favorites = favorites.toggle_favorite("tv", "B", "https://B")

    assert ctrl._delete_custom_entries("tv", ["A", "B", "Z"]) == 2
    assert ctrl._delete_custom_entries("tv", []) == 0

    assert [c.name for c in channels.load_custom_channels()] == ["C"]
    assert [c.name for c in win.tv_channels_data] == ["C"]
    assert not favorites.is_favorite(win.favorites, "tv", "B")


def test_hide_public_channels_filters_them_and_stops_if_playing(ctrl, win):
    win.tv_channels_data = [channels.Channel("Pública", "https://p"), channels.Channel("Otra", "https://o")]
    win.current_type, win.current_name = "tv", "Pública"

    assert ctrl.hide_entries("tv", ["Pública"]) == 1

    assert channels.load_hidden_channel_names() == {"Pública"}
    assert [c.name for c in win.tv_channels_data] == ["Otra"]
    win.playback.stop_playback.assert_called_once()


def test_unhide_reloads_catalog_from_cache(ctrl, win):
    channels.hide_channels(["Pública"])
    radio.hide_stations(["Emisora"])

    assert ctrl.unhide_entries("tv", ["Pública"]) == 1
    assert ctrl.unhide_entries("radio", ["Emisora"]) == 1
    assert ctrl.unhide_entries("tv", []) == 0

    win.catalog.load_tv_channels.assert_called_once()
    win.catalog.load_radio_stations.assert_called_once()
    assert channels.load_hidden_channel_names() == set()
