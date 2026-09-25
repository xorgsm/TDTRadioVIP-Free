"""
Cobertura de core/channels.py: parseo M3U, descarga de la lista pública
con caché por URL, lista personalizada, canales ocultos y contador de
fallos consecutivos -- incluidos archivos de perfil corruptos.

requests.get se sustituye con monkeypatch -- ningún test toca la red.
"""
import json
from unittest.mock import Mock

import pytest
import requests

from core import channels
from core.channels import Channel

M3U = """#EXTM3U
#EXTINF:-1 tvg-id="La1.es@SD" tvg-logo="https://logo/la1.png" group-title="General, Nacional",La 1
https://stream.test/la1.m3u8
#EXTINF:-1,Antena 3
#EXTVLCOPT:http-user-agent=Mozilla
https://stream.test/a3.m3u8
#EXTINF:-1 tvg-id="la1b",la 1
https://stream.test/la1-respaldo.m3u8
#EXTINF:sin duracion valida
https://stream.test/huerfana.m3u8
"""

URL = "https://lista.test/es.m3u"


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    app = tmp_path / "app"
    perfil = tmp_path / "perfil"
    monkeypatch.setattr(channels, "get_app_data_dir", lambda: app)
    monkeypatch.setattr(channels, "get_profile_data_dir", lambda: perfil)
    perfil.mkdir(parents=True)
    return app, perfil


def _mock_get(monkeypatch, text=M3U, error=None):
    if error is not None:
        get = Mock(side_effect=error)
    else:
        get = Mock(return_value=Mock(content=text.encode("utf-8"), raise_for_status=Mock()))
    monkeypatch.setattr(channels.requests, "get", get)
    return get


# --------------------------------------------------------------------------
# parse_m3u() / playlist_url_for()
# --------------------------------------------------------------------------

def test_parse_m3u_reads_attributes_and_merges_duplicates_as_alternates():
    lista = channels.parse_m3u(M3U)

    assert [c.name for c in lista] == ["La 1", "Antena 3"]
    la1 = lista[0]
    assert la1.tvg_id == "La1.es@SD"
    assert la1.logo == "https://logo/la1.png"
    assert la1.group == "General, Nacional"
    assert la1.url == "https://stream.test/la1.m3u8"
    assert la1.alternate_urls == ["https://stream.test/la1-respaldo.m3u8"]
    assert lista[1].url == "https://stream.test/a3.m3u8"


def test_parse_m3u_without_dedupe_keeps_repeated_names():
    assert len(channels.parse_m3u(M3U, deduplicate=False)) == 3


def test_playlist_url_for_country():
    assert channels.playlist_url_for("FR").endswith("/fr.m3u")
    assert channels.playlist_url_for("").endswith("/es.m3u")


# --------------------------------------------------------------------------
# fetch_tv_channels()
# --------------------------------------------------------------------------

def test_fetch_downloads_caches_and_then_uses_cache(dirs, monkeypatch):
    get = _mock_get(monkeypatch)

    primera = channels.fetch_tv_channels(URL)
    segunda = channels.fetch_tv_channels(URL)

    assert [c.name for c in primera] == ["La 1", "Antena 3"]
    assert segunda == primera
    assert get.call_count == 1


def test_fetch_uses_one_cache_per_url(dirs, monkeypatch):
    get = _mock_get(monkeypatch)
    channels.fetch_tv_channels(URL)

    channels.fetch_tv_channels("https://lista.test/fr.m3u")

    assert get.call_count == 2


def test_fetch_force_refresh_falls_back_to_cache_on_error(dirs, monkeypatch):
    _mock_get(monkeypatch)
    channels.fetch_tv_channels(URL)
    _mock_get(monkeypatch, error=requests.ConnectionError("sin red"))

    assert [c.name for c in channels.fetch_tv_channels(URL, force_refresh=True)] == ["La 1", "Antena 3"]


def test_fetch_empty_playlist_keeps_previous_cache(dirs, monkeypatch):
    _mock_get(monkeypatch)
    channels.fetch_tv_channels(URL)
    _mock_get(monkeypatch, text="#EXTM3U\n")

    assert len(channels.fetch_tv_channels(URL, force_refresh=True)) == 2


def test_fetch_keeps_download_when_cache_cannot_be_written(dirs, monkeypatch):
    _mock_get(monkeypatch)
    monkeypatch.setattr(channels, "write_json_atomic", Mock(side_effect=OSError("disco lleno")))

    assert len(channels.fetch_tv_channels(URL)) == 2


@pytest.mark.parametrize("contenido", [
    b"{no es json",
    b"\xff\xfe basura no utf-8",
    json.dumps({"no": "lista"}).encode(),
    json.dumps([{"name": "Sin url"}]).encode(),
    json.dumps([{"name": 1, "url": "https://x"}]).encode(),
])
def test_fetch_with_corrupt_cache_and_no_network_returns_empty(dirs, monkeypatch, contenido):
    app, _ = dirs
    ruta = channels._cache_path_for(URL)
    ruta.parent.mkdir(parents=True)
    ruta.write_bytes(contenido)
    _mock_get(monkeypatch, error=requests.ConnectionError("sin red"))

    assert channels.fetch_tv_channels(URL) == []


# --------------------------------------------------------------------------
# Lista personalizada
# --------------------------------------------------------------------------

def test_custom_channels_add_update_remove(dirs):
    channels.add_custom_channel(Channel("Uno", "https://1"))
    channels.add_custom_channels([Channel("Dos", "https://2"), Channel("Tres", "https://3")])
    channels.add_custom_channels([])

    channels.update_custom_channel("Dos", Channel("Dos bis", "https://2b"))
    channels.remove_custom_channel("Uno")

    assert [(c.name, c.url) for c in channels.load_custom_channels()] == [
        ("Dos bis", "https://2b"), ("Tres", "https://3"),
    ]
    assert channels.remove_custom_channels(["Tres", "No existe"]) == 1
    assert channels.remove_custom_channels([]) == 0
    assert [c.name for c in channels.load_custom_channels()] == ["Dos bis"]


def test_load_custom_channels_repairs_stored_duplicates(dirs):
    _, perfil = dirs
    (perfil / channels.CUSTOM_FILE).write_text(json.dumps([
        {"name": "Uno", "url": "https://1"}, {"name": "uno ", "url": "https://1b"},
    ]), encoding="utf-8")

    cargados = channels.load_custom_channels()

    assert [c.name for c in cargados] == ["Uno"]
    assert cargados[0].alternate_urls == ["https://1b"]
    assert len(json.loads((perfil / channels.CUSTOM_FILE).read_text(encoding="utf-8"))) == 1


@pytest.mark.parametrize("contenido", [
    b"{no es json",
    b"\xff\xfe basura no utf-8",
    json.dumps({"no": "lista"}).encode(),
])
def test_load_custom_channels_returns_empty_for_corrupt_file(dirs, contenido):
    _, perfil = dirs
    (perfil / channels.CUSTOM_FILE).write_bytes(contenido)

    assert channels.load_custom_channels() == []


def test_load_custom_channels_skips_malformed_entries(dirs):
    _, perfil = dirs
    (perfil / channels.CUSTOM_FILE).write_text(json.dumps([
        {"name": "Bueno", "url": "https://ok"},
        "texto",
        {"name": "Sin url"},
        {"name": 5, "url": "https://num"},
        {"name": "Alternativas raras", "url": "https://x", "alternate_urls": "https://y"},
        {"name": "Campo extra", "url": "https://x", "extra": 1},
    ]), encoding="utf-8")

    assert [c.name for c in channels.load_custom_channels()] == ["Bueno"]


# --------------------------------------------------------------------------
# Canales ocultos
# --------------------------------------------------------------------------

def test_hide_and_unhide_ignore_empty_input(dirs):
    assert channels.hide_channels([]) == 0
    assert channels.unhide_channels([]) == 0
    lista = [Channel("A", "u")]
    assert channels.filter_hidden(lista) is lista


@pytest.mark.parametrize("contenido", [
    b"{no es json",
    b"\xff\xfe basura no utf-8",
    json.dumps({"no": "lista"}).encode(),
    json.dumps([{"no": "hashable"}]).encode(),
])
def test_load_hidden_returns_empty_for_corrupt_file(dirs, contenido):
    _, perfil = dirs
    (perfil / channels.HIDDEN_FILE).write_bytes(contenido)

    assert channels.load_hidden_channel_names() == set()


def test_load_hidden_ignores_non_string_names(dirs):
    _, perfil = dirs
    (perfil / channels.HIDDEN_FILE).write_text(json.dumps(["A", 1, None, "B"]), encoding="utf-8")

    assert channels.load_hidden_channel_names() == {"A", "B"}


# --------------------------------------------------------------------------
# Fallos consecutivos
# --------------------------------------------------------------------------

def test_record_and_reset_channel_failures(dirs):
    assert channels.record_channel_failure("") == 0
    assert channels.record_channel_failure("A") == 1
    assert channels.record_channel_failure("A") == 2
    assert channels.record_channel_failure("B") == 1

    channels.reset_channel_failures("A")
    channels.reset_channel_failures("No existe")
    channels.reset_channel_failures("")

    assert channels.record_channel_failure("A") == 1
    assert channels.record_channel_failure("B") == 2


@pytest.mark.parametrize("contenido", [
    b"{no es json",
    b"\xff\xfe basura no utf-8",
    json.dumps(["no", "dict"]).encode(),
])
def test_record_failure_with_corrupt_file_starts_from_zero(dirs, contenido):
    _, perfil = dirs
    (perfil / channels.FAILCOUNT_FILE).write_bytes(contenido)

    assert channels.record_channel_failure("A") == 1


def test_record_failure_ignores_non_numeric_stored_count(dirs):
    """Un contador guardado con un tipo raro no puede hacer reventar el
    manejo de errores de reproducción (se llama desde PlaybackController)."""
    _, perfil = dirs
    (perfil / channels.FAILCOUNT_FILE).write_text(
        json.dumps({"A": "tres", "B": 2, "C": True}), encoding="utf-8"
    )

    assert channels.record_channel_failure("A") == 1
    assert channels.record_channel_failure("B") == 3
    assert channels.record_channel_failure("C") == 1


# --------------------------------------------------------------------------
# Codificación de listas M3U
# --------------------------------------------------------------------------

M3U_ES = '#EXTM3U\n#EXTINF:-1 group-title="Música",Canción España\nhttps://stream.test/es\n'


@pytest.mark.parametrize("datos", [
    M3U_ES.encode("utf-8"),
    M3U_ES.encode("utf-8-sig"),   # UTF-8 con BOM
    M3U_ES.encode("cp1252"),      # "ANSI" de Windows
])
def test_decode_playlist_keeps_accents_in_every_common_encoding(datos):
    lista = channels.parse_m3u(channels.decode_playlist(datos))

    assert [(c.name, c.group) for c in lista] == [("Canción España", "Música")]


def test_parse_m3u_ignores_bom_before_first_entry_without_header():
    lista = channels.parse_m3u("﻿#EXTINF:-1,Uno\nhttps://a\n#EXTINF:-1,Dos\nhttps://b\n")

    assert [c.name for c in lista] == ["Uno", "Dos"]


def test_fetch_decodes_utf8_even_when_server_omits_charset(dirs, monkeypatch):
    """requests asume ISO-8859-1 para text/* sin charset: resp.text daría
    "CanciÃ³n". La lista se decodifica desde los bytes."""
    respuesta = requests.models.Response()
    respuesta._content = M3U_ES.encode("utf-8")
    respuesta.status_code = 200
    respuesta.headers["content-type"] = "text/plain"
    respuesta.encoding = "ISO-8859-1"
    monkeypatch.setattr(channels.requests, "get", Mock(return_value=respuesta))

    assert channels.fetch_tv_channels(URL)[0].name == "Canción España"
