"""
fetch_epg(wanted_keys=...): la guía y su caché solo conservan los canales
que la app usa. La guía pública completa pesaba 256 MB en disco y se
parseaba entera en cada arranque.
"""
import json
import os
import time
from unittest.mock import Mock

import pytest

from _fake_http import fake_response
from core import epg
from core.epg import fetch_epg
from core.json_store import remove_stale_temporaries

URL = "https://guia.test/epg.xml"

XMLTV = """<?xml version="1.0" encoding="UTF-8"?>
<tv>
  <channel id="la 1.es"><display-name>La 1</display-name></channel>
  <channel id="antena 3.es"><display-name>Antena 3</display-name></channel>
  <channel id="cuatro.es"><display-name>Cuatro</display-name></channel>
  <programme channel="la 1.es" start="20260924210000" stop="20260924220000"><title>Uno</title></programme>
  <programme channel="antena 3.es" start="20260924210000" stop="20260924220000"><title>Tres</title></programme>
  <programme channel="cuatro.es" start="20260924210000" stop="20260924220000"><title>Cuatro</title></programme>
</tv>
""".encode("utf-8")


@pytest.fixture
def app_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(epg, "get_app_data_dir", lambda: tmp_path)
    return tmp_path


@pytest.fixture
def get(monkeypatch):
    mock = Mock(return_value=fake_response(XMLTV))
    monkeypatch.setattr(epg.requests, "get", mock)
    return mock


def _cached_channels(app_dir):
    raw = json.loads((app_dir / "cache" / epg.CACHE_FILE).read_text(encoding="utf-8"))
    return set(raw["guide"])


def test_fetch_epg_keeps_only_wanted_channels(app_dir, get):
    guide = fetch_epg(URL, wanted_keys={"la1"})

    assert set(guide) == {"la1"}
    assert _cached_channels(app_dir) == {"la1"}


def test_fetch_epg_without_wanted_keys_keeps_every_channel(app_dir, get):
    guide = fetch_epg(URL)

    assert set(guide) == {"la1", "antena3", "cuatro"}


def test_cache_is_reused_when_wanted_keys_are_a_subset(app_dir, get):
    fetch_epg(URL, wanted_keys={"la1", "antena3"})

    guide = fetch_epg(URL, wanted_keys={"la1"})

    assert get.call_count == 1
    assert set(guide) == {"la1"}


def test_cache_is_refreshed_when_a_new_channel_is_wanted(app_dir, get):
    fetch_epg(URL, wanted_keys={"la1"})

    guide = fetch_epg(URL, wanted_keys={"la1", "antena3"})

    assert get.call_count == 2
    assert set(guide) == {"la1", "antena3"}


def test_filtered_cache_is_not_reused_for_a_full_request(app_dir, get):
    fetch_epg(URL, wanted_keys={"la1"})

    guide = fetch_epg(URL)

    assert get.call_count == 2
    assert set(guide) == {"la1", "antena3", "cuatro"}


def test_empty_wanted_keys_downloads_nothing(app_dir, get):
    assert fetch_epg(URL, wanted_keys=set()) == {}
    get.assert_not_called()


def test_remove_stale_temporaries_deletes_only_old_tmp_files(tmp_path):
    old = tmp_path / "tmpabc123.tmp"
    recent = tmp_path / "tmpnew456.tmp"
    data = tmp_path / "epg_cache.json"
    for path in (old, recent, data):
        path.write_text("x", encoding="utf-8")
    two_days_ago = time.time() - 2 * 86400
    os.utime(old, (two_days_ago, two_days_ago))
    os.utime(data, (two_days_ago, two_days_ago))

    removed = remove_stale_temporaries(tmp_path)

    assert removed == 1
    assert not old.exists()
    assert recent.exists()
    assert data.exists()


def test_filtered_guide_with_no_match_is_cached_instead_of_redownloaded(app_dir, get):
    assert fetch_epg(URL, wanted_keys={"canalinexistente"}) == {}

    assert fetch_epg(URL, wanted_keys={"canalinexistente"}) == {}
    assert get.call_count == 1


def test_cache_of_the_previous_format_without_keys_serves_a_filtered_request(app_dir, get):
    fetch_epg(URL)  # guía completa, sin filtrar
    raw = json.loads((app_dir / "cache" / epg.CACHE_FILE).read_text(encoding="utf-8"))
    raw.pop("keys")  # formato anterior: sin el campo
    (app_dir / "cache" / epg.CACHE_FILE).write_text(json.dumps(raw), encoding="utf-8")

    guide = fetch_epg(URL, wanted_keys={"la1"})

    assert get.call_count == 1
    assert set(guide) == {"la1"}


def test_failed_download_falls_back_to_an_incomplete_filtered_cache(app_dir, get):
    import requests

    fetch_epg(URL, wanted_keys={"la1"})
    get.side_effect = requests.RequestException("sin red")

    guide = fetch_epg(URL, force_refresh=True, wanted_keys={"la1", "antena3"})

    assert set(guide) == {"la1"}


def test_cache_of_another_url_is_not_reused_for_a_filtered_request(app_dir, get):
    fetch_epg(URL, wanted_keys={"la1"})

    fetch_epg("https://otra-guia.test/epg.xml", wanted_keys={"la1"})

    assert get.call_count == 2


def test_epg_download_has_separate_timeouts_and_a_total_deadline(app_dir, get, monkeypatch):
    captured = {}
    real = epg.fetch_limited

    def spy(*args, **kwargs):
        captured.update(kwargs)
        return real(*args, **kwargs)

    monkeypatch.setattr(epg, "fetch_limited", spy)

    fetch_epg(URL, wanted_keys={"la1"})

    connect, read = captured["timeout"]
    assert connect <= 5 and read <= 20
    # holgado: 256 MB por un enlace de ~3 Mbit/s tardan unos 11 minutos
    assert 600 <= captured["deadline"] <= 1800
