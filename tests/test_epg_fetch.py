"""
Cobertura de core/epg.py más allá del parseo de horas (ver
tests/test_epg.py): channel_key(), descarga y parseo XMLTV con
fetch_epg() y su caché en disco, y get_now_next() sobre guías sin
preparar.

requests.get se sustituye con monkeypatch -- ningún test toca la red.
"""
import json
import os
import time
from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest
import requests

from core import epg
from core.epg import Programme, channel_key, fetch_epg, get_now_next

URL_A = "https://guia-a.test/epg.xml"
URL_B = "https://guia-b.test/epg.xml"

XMLTV = """<?xml version="1.0" encoding="UTF-8"?>
<tv>
  <channel id="la 1.es">
    <display-name>La 1</display-name>
    <display-name>La 1 HD</display-name>
  </channel>
  <channel id=""><display-name>Sin id</display-name></channel>
  <programme channel="la 1.es" start="20260924220000" stop="20260924230000">
    <title>Segundo</title>
  </programme>
  <programme channel="la 1.es" start="20260924210000" stop="20260924220000">
    <title>Telediario</title><desc>Noticias</desc>
  </programme>
  <programme channel="Antena 3" start="20260924210000" stop="20260924220000">
    <title></title>
  </programme>
</tv>
""".encode("utf-8")


@pytest.fixture
def app_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(epg, "get_app_data_dir", lambda: tmp_path)
    return tmp_path


def _cache_file(app_dir):
    return app_dir / "cache" / epg.CACHE_FILE


def _mock_get(monkeypatch, content=XMLTV, error=None):
    if error is not None:
        get = Mock(side_effect=error)
    else:
        get = Mock(return_value=Mock(content=content, raise_for_status=Mock()))
    monkeypatch.setattr(epg.requests, "get", get)
    return get


# --------------------------------------------------------------------------
# channel_key()
# --------------------------------------------------------------------------

@pytest.mark.parametrize("entrada, esperado", [
    ("La1.es@SD", "la1"),
    ("la 1.es", "la1"),
    ("La 1 HD", "la1hd"),
    ("Antena 3.es", "antena3"),
    ("Cuatro@Originals", "cuatro"),
    ("Telecinco España", "telecincoespana"),
    ("", ""),
    (None, ""),
])
def test_channel_key_normalizes_ids_across_sources(entrada, esperado):
    assert channel_key(entrada) == esperado


# --------------------------------------------------------------------------
# fetch_epg(): descarga y parseo
# --------------------------------------------------------------------------

def test_fetch_epg_without_url_returns_empty_without_request(app_dir, monkeypatch):
    get = _mock_get(monkeypatch)

    assert fetch_epg("") == {}
    get.assert_not_called()


def test_fetch_epg_indexes_programmes_under_every_channel_alias(app_dir, monkeypatch):
    _mock_get(monkeypatch)

    guia = fetch_epg(URL_A)

    assert set(guia) == {"la1", "la1hd", "antena3"}
    assert guia["la1"] is not None
    assert [p.title for p in guia["la1"]] == ["Telediario", "Segundo"]  # ordenados
    assert guia["la1"][0].description == "Noticias"
    assert [p.title for p in guia["la1hd"]] == ["Telediario", "Segundo"]
    assert guia["antena3"][0].title == ""  # <title></title> -> "" y no None


def test_fetch_epg_writes_cache_and_reuses_it_while_fresh(app_dir, monkeypatch):
    get = _mock_get(monkeypatch)
    fetch_epg(URL_A)
    assert _cache_file(app_dir).exists()

    guia = fetch_epg(URL_A)

    assert get.call_count == 1
    assert [p.title for p in guia["la1"]] == ["Telediario", "Segundo"]
    assert hasattr(guia["la1"][0], "_start_dt")


def test_fetch_epg_force_refresh_ignores_fresh_cache(app_dir, monkeypatch):
    get = _mock_get(monkeypatch)
    fetch_epg(URL_A)

    fetch_epg(URL_A, force_refresh=True)

    assert get.call_count == 2


def test_fetch_epg_downloads_again_when_cache_is_stale(app_dir, monkeypatch):
    get = _mock_get(monkeypatch)
    fetch_epg(URL_A)
    viejo = time.time() - epg.CACHE_TTL_SECONDS - 60
    os.utime(_cache_file(app_dir), (viejo, viejo))

    fetch_epg(URL_A)

    assert get.call_count == 2


def test_fetch_epg_does_not_reuse_cache_from_another_url(app_dir, monkeypatch):
    """Cambiar la URL de la EPG en Configuración tiene que surtir efecto ya,
    no seguir mostrando durante horas la guía cacheada de la URL anterior."""
    get = _mock_get(monkeypatch)
    fetch_epg(URL_A)
    otra_guia = XMLTV.replace(b"Telediario", b"Otra guia")
    get.return_value = Mock(content=otra_guia, raise_for_status=Mock())

    guia = fetch_epg(URL_B)

    assert get.call_count == 2
    assert get.call_args.args[0] == URL_B
    assert guia["la1"][0].title == "Otra guia"


@pytest.mark.parametrize("error", [requests.ConnectionError("sin red"), None])
def test_fetch_epg_falls_back_to_cache_of_same_url_on_failure(app_dir, monkeypatch, error):
    _mock_get(monkeypatch)
    fetch_epg(URL_A)
    if error is None:
        _mock_get(monkeypatch, content=b"<tv><programme")  # XML roto
    else:
        _mock_get(monkeypatch, error=error)

    guia = fetch_epg(URL_A, force_refresh=True)

    assert [p.title for p in guia["la1"]] == ["Telediario", "Segundo"]


def test_fetch_epg_failure_does_not_fall_back_to_cache_of_another_url(app_dir, monkeypatch):
    _mock_get(monkeypatch)
    fetch_epg(URL_A)
    _mock_get(monkeypatch, error=requests.ConnectionError("sin red"))

    assert fetch_epg(URL_B) == {}


def test_fetch_epg_ignores_legacy_cache_without_url(app_dir, monkeypatch):
    """Caché del formato anterior (sin URL de origen): no se sabe de qué
    guía viene, así que no se reutiliza -- se descarga de nuevo."""
    _cache_file(app_dir).parent.mkdir(parents=True)
    _cache_file(app_dir).write_text(json.dumps({
        "la1": [{"channel_id": "la1", "title": "Vieja", "start": "20260924210000",
                 "stop": "20260924220000", "description": ""}],
    }), encoding="utf-8")
    get = _mock_get(monkeypatch)

    guia = fetch_epg(URL_A)

    assert get.call_count == 1
    assert guia["la1"][0].title == "Telediario"


@pytest.mark.parametrize("contenido", [
    b"{no es json",
    b"\xff\xfe basura no utf-8",
    json.dumps(["no", "es", "dict"]).encode(),
    json.dumps({"url": URL_A, "guide": {"la1": "no es lista"}}).encode(),
    json.dumps({"url": URL_A, "guide": {"la1": [{"title": "sin campos"}]}}).encode(),
    json.dumps({"url": URL_A, "guide": {"la1": [{
        "channel_id": "la1", "title": "T", "start": 20260924210000,
        "stop": "20260924220000", "description": "",
    }]}}).encode(),
])
def test_fetch_epg_with_corrupt_cache_and_no_network_returns_empty(app_dir, monkeypatch, contenido):
    _cache_file(app_dir).parent.mkdir(parents=True)
    _cache_file(app_dir).write_bytes(contenido)
    _mock_get(monkeypatch, error=requests.ConnectionError("sin red"))

    assert fetch_epg(URL_A) == {}


def test_fetch_epg_keeps_guide_when_cache_cannot_be_written(app_dir, monkeypatch):
    _mock_get(monkeypatch)
    monkeypatch.setattr(epg, "write_json_atomic", Mock(side_effect=OSError("disco lleno")))

    assert "la1" in fetch_epg(URL_A)


# --------------------------------------------------------------------------
# get_now_next()
# --------------------------------------------------------------------------

def _xmltv(dt):
    return dt.strftime("%Y%m%d%H%M%S")


def test_get_now_next_on_unprepared_guide():
    ahora = datetime.now()
    actual = Programme("la1", "Ahora", _xmltv(ahora - timedelta(minutes=10)),
                       _xmltv(ahora + timedelta(minutes=20)))
    siguiente = Programme("la1", "Luego", _xmltv(ahora + timedelta(minutes=20)),
                          _xmltv(ahora + timedelta(minutes=50)))
    pasado = Programme("la1", "Antes", _xmltv(ahora - timedelta(hours=2)),
                       _xmltv(ahora - timedelta(hours=1)))

    assert get_now_next({"la1": [siguiente, actual, pasado]}, "La1.es@SD") == (actual, siguiente)


def test_get_now_next_unknown_channel_returns_nothing():
    assert get_now_next({}, "La1.es@SD") == (None, None)
