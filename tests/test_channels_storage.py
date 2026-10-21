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

from _fake_http import fake_response
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
        get = Mock(return_value=fake_response(text.encode("utf-8")))
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
    respuesta._content_consumed = True
    respuesta.status_code = 200
    respuesta.headers["content-type"] = "text/plain"
    respuesta.encoding = "ISO-8859-1"
    monkeypatch.setattr(channels.requests, "get", Mock(return_value=respuesta))

    assert channels.fetch_tv_channels(URL)[0].name == "Canción España"


# --------------------------------------------------------------------------
# Refresco forzado: sin trabajo innecesario en disco
# --------------------------------------------------------------------------

M3U_CHANGED = M3U + "#EXTINF:-1,Cuatro\nhttps://stream.test/c4.m3u8\n"


def test_forced_refresh_does_not_rewrite_an_unchanged_cache(dirs, monkeypatch):
    _mock_get(monkeypatch)
    channels.fetch_tv_channels(URL)
    writes = Mock(wraps=channels.write_json_atomic)
    monkeypatch.setattr(channels, "write_json_atomic", writes)

    channels.fetch_tv_channels(URL, force_refresh=True)

    writes.assert_not_called()


def test_forced_refresh_rewrites_the_cache_when_the_list_changed(dirs, monkeypatch):
    _mock_get(monkeypatch)
    channels.fetch_tv_channels(URL)
    _mock_get(monkeypatch, text=M3U_CHANGED)
    writes = Mock(wraps=channels.write_json_atomic)
    monkeypatch.setattr(channels, "write_json_atomic", writes)

    result = channels.fetch_tv_channels(URL, force_refresh=True)

    assert [c.name for c in result] == ["La 1", "Antena 3", "Cuatro"]
    writes.assert_called_once()
    assert [c.name for c in channels.fetch_tv_channels(URL)] == ["La 1", "Antena 3", "Cuatro"]


# --------------------------------------------------------------------------
# custom_channel_names(): nombres sin releer la lista personalizada
# --------------------------------------------------------------------------

def test_custom_channel_names_lists_the_names(dirs):
    channels.add_custom_channels([Channel("Uno", "u1"), Channel("Dos", "u2")])

    assert channels.custom_channel_names() == frozenset({"Uno", "Dos"})


def test_custom_channel_names_is_empty_without_a_custom_file(dirs):
    assert channels.custom_channel_names() == frozenset()


def test_custom_channel_names_does_not_reread_an_unchanged_file(dirs, monkeypatch):
    channels.add_custom_channels([Channel("Uno", "u1")])
    channels.custom_channel_names()
    reads = []
    real = channels._load_channel_list
    monkeypatch.setattr(channels, "_load_channel_list", lambda path: reads.append(path) or real(path))

    channels.custom_channel_names()
    channels.custom_channel_names()

    assert reads == []


def test_custom_channel_names_notices_added_and_removed_channels(dirs):
    channels.add_custom_channels([Channel("Uno", "u1")])
    assert channels.custom_channel_names() == frozenset({"Uno"})

    channels.add_custom_channel(Channel("Dos", "u2"))
    assert channels.custom_channel_names() == frozenset({"Uno", "Dos"})

    channels.remove_custom_channel("Uno")
    assert channels.custom_channel_names() == frozenset({"Dos"})


def test_saving_invalidates_the_names_even_if_size_and_mtime_are_unchanged(dirs):
    import os

    channels.add_custom_channels([Channel("Uno", "u1")])
    path = dirs[1] / channels.CUSTOM_FILE
    before = path.stat()
    assert channels.custom_channel_names() == frozenset({"Uno"})

    channels.update_custom_channel("Uno", Channel("Dos", "u1"))  # mismo tamaño
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert path.stat().st_size == before.st_size

    assert channels.custom_channel_names() == frozenset({"Dos"})


# --------------------------------------------------------------------------
# dedupe_channels(): muchas URLs de respaldo bajo el mismo nombre
# --------------------------------------------------------------------------

def test_dedupe_keeps_alternate_urls_in_order_without_repeats():
    items = [
        Channel("La 1", "u0"), Channel("la 1", "u1"), Channel("LA 1", "u2"),
        Channel("La 1", "u1"), Channel("La 1", "u0"), Channel("Otro", "o0"),
    ]

    result = channels.dedupe_channels(items)

    assert [c.name for c in result] == ["La 1", "Otro"]
    assert result[0].url == "u0"
    assert result[0].alternate_urls == ["u1", "u2"]


def test_dedupe_scales_with_many_urls_under_the_same_name():
    import time

    items = [Channel("Mismo", f"https://s.test/{i}") for i in range(30000)]

    started = time.perf_counter()
    result = channels.dedupe_channels(items)
    elapsed = time.perf_counter() - started

    assert len(result) == 1
    assert len(result[0].alternate_urls) == 29999
    assert elapsed < 2


def test_playlist_download_separates_connect_and_read_timeouts(dirs, monkeypatch):
    get = _mock_get(monkeypatch)

    channels.fetch_tv_channels(URL)

    connect, read = get.call_args.kwargs["timeout"]
    assert connect <= 5 and read <= 15


def test_playlist_download_has_a_total_deadline(dirs, monkeypatch):
    captured = {}
    real = channels.fetch_limited

    def spy(*args, **kwargs):
        captured.update(kwargs)
        return real(*args, **kwargs)

    _mock_get(monkeypatch)
    monkeypatch.setattr(channels, "fetch_limited", spy)

    channels.fetch_tv_channels(URL)

    assert 0 < captured["deadline"] <= 60


# --------------------------------------------------------------------------
# cache_is_stale(): cuándo conviene revalidar la lista en segundo plano
# --------------------------------------------------------------------------

def _age_cache(url, seconds):
    import os
    import time

    path = channels._cache_path_for(url)
    old = time.time() - seconds
    os.utime(path, (old, old))


def test_cache_is_stale_only_after_its_ttl(dirs, monkeypatch):
    _mock_get(monkeypatch)
    channels.fetch_tv_channels(URL)
    assert channels.cache_is_stale(URL) is False

    _age_cache(URL, channels.CACHE_TTL_SECONDS + 60)

    assert channels.cache_is_stale(URL) is True


def test_cache_is_stale_without_a_cache_file(dirs):
    assert channels.cache_is_stale(URL) is True


def test_a_revalidation_that_finds_no_changes_refreshes_the_cache_age(dirs, monkeypatch):
    _mock_get(monkeypatch)
    channels.fetch_tv_channels(URL)
    _age_cache(URL, channels.CACHE_TTL_SECONDS + 60)

    channels.fetch_tv_channels(URL, force_refresh=True)

    assert channels.cache_is_stale(URL) is False


def test_a_cache_dated_in_the_future_counts_as_stale(dirs, monkeypatch):
    import os
    import time

    _mock_get(monkeypatch)
    channels.fetch_tv_channels(URL)
    future = time.time() + 3 * 86400
    os.utime(channels._cache_path_for(URL), (future, future))

    assert channels.cache_is_stale(URL) is True


def test_a_missing_cache_is_not_stale_when_asked_not_to_count_it(dirs):
    assert channels.cache_is_stale(URL, missing=False) is False


def test_dedupe_does_not_repeat_urls_the_original_already_lists_as_alternates():
    original = Channel("La 1", "u0", alternate_urls=["u1"])

    result = channels.dedupe_channels([original, Channel("la 1", "u1"), Channel("LA 1", "u2")])

    assert result[0].alternate_urls == ["u1", "u2"]
