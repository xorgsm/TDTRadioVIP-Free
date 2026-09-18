"""
Cobertura de core/radio.py: cliente de Radio-Browser (con caché en disco y
varios espejos de respaldo), deduplicado de emisoras, lista personalizada,
emisoras ocultas y contador de fallos consecutivos.

No hay un parámetro `request_get` inyectable en fetch_radio_stations (a
diferencia de core/vpngate.py o core/stream_health.py): la petición usa
`requests.get` directamente, así que se sustituye con monkeypatch sobre
`radio.requests.get`, igual que se hace con otras llamadas de red/proceso en
tests/test_downloader.py.
"""
import json

import pytest
import requests

from core import radio
from core.radio import Station


# --------------------------------------------------------------------------
# dedupe_stations (función pura)
# --------------------------------------------------------------------------

def test_dedupe_stations_returns_empty_list_for_empty_input():
    assert radio.dedupe_stations([]) == []


def test_dedupe_stations_keeps_unique_stations_in_order():
    a = Station("Radio A", "https://a.example/stream")
    b = Station("Radio B", "https://b.example/stream")
    assert radio.dedupe_stations([a, b]) == [a, b]


def test_dedupe_stations_merges_case_insensitive_duplicates_into_alternate_urls():
    original = Station("Radio Uno", "https://one.example/stream")
    duplicate = Station("RADIO UNO", "https://one-mirror.example/stream")

    result = radio.dedupe_stations([original, duplicate])

    assert len(result) == 1
    assert result[0].url == "https://one.example/stream"
    assert result[0].alternate_urls == ["https://one-mirror.example/stream"]


def test_dedupe_stations_does_not_duplicate_the_same_alternate_url_twice():
    original = Station("Radio Uno", "https://one.example/stream")
    duplicate1 = Station("Radio Uno", "https://mirror.example/stream")
    duplicate2 = Station("Radio Uno", "https://mirror.example/stream")

    result = radio.dedupe_stations([original, duplicate1, duplicate2])

    assert result[0].alternate_urls == ["https://mirror.example/stream"]


def test_dedupe_stations_ignores_duplicate_with_empty_url():
    original = Station("Radio Uno", "https://one.example/stream")
    duplicate = Station("Radio Uno", "")

    result = radio.dedupe_stations([original, duplicate])

    assert result[0].alternate_urls == []


def test_dedupe_stations_trims_and_folds_name_for_comparison():
    original = Station("  Radio Uno  ", "https://one.example/stream")
    duplicate = Station("radio uno", "https://other.example/stream")

    result = radio.dedupe_stations([original, duplicate])

    assert len(result) == 1


# --------------------------------------------------------------------------
# fetch_radio_stations
# --------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, payload, status_ok=True, json_error=False):
        self._payload = payload
        self._status_ok = status_ok
        self._json_error = json_error

    def raise_for_status(self):
        if not self._status_ok:
            raise requests.HTTPError("HTTP 500")

    def json(self):
        if self._json_error:
            raise ValueError("cuerpo no es JSON")
        return self._payload


def _raw_station(name="Radio Uno", url_resolved="https://one.example/stream", **extra):
    base = {"name": name, "url_resolved": url_resolved, "favicon": "", "tags": "", "bitrate": 128, "country": "Spain"}
    base.update(extra)
    return base


def test_fetch_radio_stations_parses_valid_response(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "get_app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(radio.requests, "get", lambda *a, **k: _FakeResponse([_raw_station()]))

    stations = radio.fetch_radio_stations("ES")

    assert len(stations) == 1
    assert stations[0].name == "Radio Uno"
    assert stations[0].url == "https://one.example/stream"
    assert stations[0].bitrate == 128


def test_fetch_radio_stations_falls_back_to_url_when_url_resolved_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "get_app_data_dir", lambda: tmp_path)
    raw = _raw_station(url_resolved=None, url="https://fallback.example/stream")
    monkeypatch.setattr(radio.requests, "get", lambda *a, **k: _FakeResponse([raw]))

    stations = radio.fetch_radio_stations("ES")

    assert stations[0].url == "https://fallback.example/stream"


def test_fetch_radio_stations_defaults_missing_name_and_skips_entries_without_any_url(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "get_app_data_dir", lambda: tmp_path)
    sin_nombre = _raw_station(name="")
    sin_url = _raw_station(name="Fantasma", url_resolved=None, url="")
    monkeypatch.setattr(radio.requests, "get", lambda *a, **k: _FakeResponse([sin_nombre, sin_url]))

    stations = radio.fetch_radio_stations("ES")

    assert [s.name for s in stations] == ["Sin nombre"]


def test_fetch_radio_stations_deduplicates_raw_results(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "get_app_data_dir", lambda: tmp_path)
    raw = [_raw_station(name="Radio Uno", url_resolved="https://a.example/stream"),
           _raw_station(name="radio uno", url_resolved="https://b.example/stream")]
    monkeypatch.setattr(radio.requests, "get", lambda *a, **k: _FakeResponse(raw))

    stations = radio.fetch_radio_stations("ES")

    assert len(stations) == 1
    assert stations[0].alternate_urls == ["https://b.example/stream"]


def test_fetch_radio_stations_uses_country_code_uppercased_in_request_url(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "get_app_data_dir", lambda: tmp_path)
    seen_urls = []

    def _fake_get(url, **kwargs):
        seen_urls.append(url)
        return _FakeResponse([_raw_station()])

    monkeypatch.setattr(radio.requests, "get", _fake_get)

    radio.fetch_radio_stations("es")

    assert seen_urls[0].endswith("/json/stations/bycountrycodeexact/ES")


def test_fetch_radio_stations_defaults_country_code_to_es_when_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "get_app_data_dir", lambda: tmp_path)
    seen_urls = []

    def _fake_get(url, **kwargs):
        seen_urls.append(url)
        return _FakeResponse([_raw_station()])

    monkeypatch.setattr(radio.requests, "get", _fake_get)

    radio.fetch_radio_stations("")

    assert seen_urls[0].endswith("/bycountrycodeexact/ES")


def test_fetch_radio_stations_passes_expected_query_params(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "get_app_data_dir", lambda: tmp_path)
    seen_params = []

    def _fake_get(url, params=None, **kwargs):
        seen_params.append(params)
        return _FakeResponse([_raw_station()])

    monkeypatch.setattr(radio.requests, "get", _fake_get)

    radio.fetch_radio_stations("ES", limit=50)

    assert seen_params[0] == {"hidebroken": "true", "order": "clickcount", "reverse": "true", "limit": 50}


def test_fetch_radio_stations_tries_next_mirror_when_first_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "get_app_data_dir", lambda: tmp_path)
    calls = []

    def _fake_get(url, **kwargs):
        calls.append(url)
        if len(calls) == 1:
            raise requests.ConnectionError("espejo caído")
        return _FakeResponse([_raw_station()])

    monkeypatch.setattr(radio.requests, "get", _fake_get)

    stations = radio.fetch_radio_stations("ES")

    assert len(calls) == 2
    assert len(stations) == 1


def test_fetch_radio_stations_tries_next_mirror_when_body_is_not_valid_json(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "get_app_data_dir", lambda: tmp_path)
    calls = []

    def _fake_get(url, **kwargs):
        calls.append(url)
        if len(calls) == 1:
            return _FakeResponse(None, json_error=True)
        return _FakeResponse([_raw_station()])

    monkeypatch.setattr(radio.requests, "get", _fake_get)

    stations = radio.fetch_radio_stations("ES")

    assert len(calls) == 2
    assert len(stations) == 1


def test_fetch_radio_stations_tries_next_mirror_on_http_error_status(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "get_app_data_dir", lambda: tmp_path)
    calls = []

    def _fake_get(url, **kwargs):
        calls.append(url)
        if len(calls) == 1:
            return _FakeResponse(None, status_ok=False)
        return _FakeResponse([_raw_station()])

    monkeypatch.setattr(radio.requests, "get", _fake_get)

    stations = radio.fetch_radio_stations("ES")

    assert len(calls) == 2
    assert len(stations) == 1


def test_fetch_radio_stations_returns_empty_list_when_all_mirrors_fail_and_no_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "get_app_data_dir", lambda: tmp_path)

    def _raise(*args, **kwargs):
        raise requests.ConnectionError("sin red")

    monkeypatch.setattr(radio.requests, "get", _raise)

    assert radio.fetch_radio_stations("ES") == []


def test_fetch_radio_stations_falls_back_to_stale_cache_when_all_mirrors_fail(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "get_app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(radio.requests, "get", lambda *a, **k: _FakeResponse([_raw_station(name="Cacheada")]))
    radio.fetch_radio_stations("ES", force_refresh=True)

    def _raise(*args, **kwargs):
        raise requests.ConnectionError("sin red")

    monkeypatch.setattr(radio.requests, "get", _raise)

    stations = radio.fetch_radio_stations("ES", force_refresh=True)

    assert [s.name for s in stations] == ["Cacheada"]


def test_fetch_radio_stations_returns_cache_without_calling_network_when_fresh(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "get_app_data_dir", lambda: tmp_path)
    calls = []

    def _fake_get(*args, **kwargs):
        calls.append(1)
        return _FakeResponse([_raw_station()])

    monkeypatch.setattr(radio.requests, "get", _fake_get)

    radio.fetch_radio_stations("ES")
    radio.fetch_radio_stations("ES")

    assert len(calls) == 1


def test_fetch_radio_stations_force_refresh_bypasses_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "get_app_data_dir", lambda: tmp_path)
    responses = iter([
        _FakeResponse([_raw_station(name="Vieja")]),
        _FakeResponse([_raw_station(name="Nueva")]),
    ])
    monkeypatch.setattr(radio.requests, "get", lambda *a, **k: next(responses))

    radio.fetch_radio_stations("ES")
    refreshed = radio.fetch_radio_stations("ES", force_refresh=True)

    assert [s.name for s in refreshed] == ["Nueva"]


def test_fetch_radio_stations_ignores_corrupt_cache_and_fetches_from_network(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "get_app_data_dir", lambda: tmp_path)
    cache_path = radio._cache_path_for("ES")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text("no es json valido", encoding="utf-8")
    monkeypatch.setattr(radio.requests, "get", lambda *a, **k: _FakeResponse([_raw_station(name="De la red")]))

    stations = radio.fetch_radio_stations("ES")

    assert [s.name for s in stations] == ["De la red"]


def test_fetch_radio_stations_uses_separate_cache_per_country(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "get_app_data_dir", lambda: tmp_path)
    responses = iter([
        _FakeResponse([_raw_station(name="Espanola")]),
        _FakeResponse([_raw_station(name="Francesa")]),
    ])
    monkeypatch.setattr(radio.requests, "get", lambda *a, **k: next(responses))

    es_stations = radio.fetch_radio_stations("ES")
    fr_stations = radio.fetch_radio_stations("FR")

    assert [s.name for s in es_stations] == ["Espanola"]
    assert [s.name for s in fr_stations] == ["Francesa"]


def test_fetch_radio_stations_does_not_raise_when_cache_write_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "get_app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(radio.requests, "get", lambda *a, **k: _FakeResponse([_raw_station()]))

    def _raise(*args, **kwargs):
        raise OSError("disco lleno")

    monkeypatch.setattr(radio, "write_json_atomic", _raise)

    stations = radio.fetch_radio_stations("ES")

    assert len(stations) == 1


# --------------------------------------------------------------------------
# Lista personalizada (custom stations)
# --------------------------------------------------------------------------

def test_load_custom_stations_returns_empty_list_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "get_profile_data_dir", lambda: tmp_path)
    assert radio.load_custom_stations() == []


def test_load_custom_stations_returns_empty_list_on_corrupt_json(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "get_profile_data_dir", lambda: tmp_path)
    (tmp_path / radio.CUSTOM_FILE).write_text("{no es json", encoding="utf-8")
    assert radio.load_custom_stations() == []


def test_add_custom_station_appends_to_existing_list(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "get_profile_data_dir", lambda: tmp_path)
    radio.add_custom_station(Station("Uno", "https://one.example/stream"))
    radio.add_custom_station(Station("Dos", "https://two.example/stream"))

    assert [s.name for s in radio.load_custom_stations()] == ["Uno", "Dos"]


def test_add_custom_stations_bulk_writes_once(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "get_profile_data_dir", lambda: tmp_path)
    radio.add_custom_stations([
        Station("Uno", "https://one.example/stream"),
        Station("Dos", "https://two.example/stream"),
    ])

    assert [s.name for s in radio.load_custom_stations()] == ["Uno", "Dos"]


def test_add_custom_stations_with_empty_list_is_a_noop(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "get_profile_data_dir", lambda: tmp_path)
    radio.add_custom_stations([])
    assert not (tmp_path / radio.CUSTOM_FILE).exists()


def test_update_custom_station_replaces_matching_entry_by_old_name(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "get_profile_data_dir", lambda: tmp_path)
    radio.add_custom_stations([
        Station("Uno", "https://one.example/stream"),
        Station("Dos", "https://two.example/stream"),
    ])

    radio.update_custom_station("Uno", Station("Uno renombrada", "https://one-new.example/stream"))

    stations = radio.load_custom_stations()
    assert [s.name for s in stations] == ["Uno renombrada", "Dos"]


def test_remove_custom_station_removes_only_matching_name(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "get_profile_data_dir", lambda: tmp_path)
    radio.add_custom_stations([
        Station("Uno", "https://one.example/stream"),
        Station("Dos", "https://two.example/stream"),
    ])

    radio.remove_custom_station("Uno")

    assert [s.name for s in radio.load_custom_stations()] == ["Dos"]


def test_remove_custom_stations_returns_count_removed_and_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "get_profile_data_dir", lambda: tmp_path)
    radio.add_custom_stations([
        Station("Uno", "https://one.example/stream"),
        Station("Dos", "https://two.example/stream"),
    ])

    removed = radio.remove_custom_stations(["Uno"])
    removed_again = radio.remove_custom_stations(["Uno"])

    assert removed == 1
    assert removed_again == 0
    assert [s.name for s in radio.load_custom_stations()] == ["Dos"]


def test_remove_custom_stations_with_empty_names_returns_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "get_profile_data_dir", lambda: tmp_path)
    assert radio.remove_custom_stations([]) == 0


# --------------------------------------------------------------------------
# Emisoras ocultas
# --------------------------------------------------------------------------

def test_load_hidden_station_names_returns_empty_set_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "get_profile_data_dir", lambda: tmp_path)
    assert radio.load_hidden_station_names() == set()


def test_load_hidden_station_names_returns_empty_set_when_data_is_not_a_list(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "get_profile_data_dir", lambda: tmp_path)
    (tmp_path / radio.HIDDEN_FILE).write_text(json.dumps({"no": "es lista"}), encoding="utf-8")
    assert radio.load_hidden_station_names() == set()


def test_load_hidden_station_names_returns_empty_set_on_corrupt_json(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "get_profile_data_dir", lambda: tmp_path)
    (tmp_path / radio.HIDDEN_FILE).write_text("{roto", encoding="utf-8")
    assert radio.load_hidden_station_names() == set()


def test_hide_stations_returns_count_of_newly_added_and_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "get_profile_data_dir", lambda: tmp_path)

    assert radio.hide_stations(["Radio A", "Radio B"]) == 2
    assert radio.hide_stations(["Radio A"]) == 0  # ya estaba oculta
    assert radio.load_hidden_station_names() == {"Radio A", "Radio B"}


def test_hide_stations_with_empty_names_returns_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "get_profile_data_dir", lambda: tmp_path)
    assert radio.hide_stations([]) == 0


def test_unhide_stations_returns_count_removed_and_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "get_profile_data_dir", lambda: tmp_path)
    radio.hide_stations(["Radio A", "Radio B"])

    assert radio.unhide_stations(["Radio A"]) == 1
    assert radio.unhide_stations(["Radio A"]) == 0
    assert radio.load_hidden_station_names() == {"Radio B"}


def test_filter_hidden_returns_same_list_when_nothing_hidden(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "get_profile_data_dir", lambda: tmp_path)
    catalog = [Station("Radio A", "https://a.example/stream")]

    assert radio.filter_hidden(catalog) is catalog


def test_filter_hidden_excludes_hidden_station_names(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "get_profile_data_dir", lambda: tmp_path)
    radio.hide_stations(["Radio A"])
    catalog = [
        Station("Radio A", "https://a.example/stream"),
        Station("Radio B", "https://b.example/stream"),
    ]

    assert [s.name for s in radio.filter_hidden(catalog)] == ["Radio B"]


# --------------------------------------------------------------------------
# Fallos consecutivos por emisora
# --------------------------------------------------------------------------

def test_record_channel_failure_increments_consecutive_count(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "get_profile_data_dir", lambda: tmp_path)

    assert radio.record_channel_failure("Radio A") == 1
    assert radio.record_channel_failure("Radio A") == 2
    assert radio.record_channel_failure("Radio B") == 1


def test_record_channel_failure_with_empty_name_returns_zero_without_saving(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "get_profile_data_dir", lambda: tmp_path)

    assert radio.record_channel_failure("") == 0
    assert not (tmp_path / radio.FAILCOUNT_FILE).exists()


def test_reset_channel_failures_clears_existing_counter(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "get_profile_data_dir", lambda: tmp_path)
    radio.record_channel_failure("Radio A")
    radio.record_channel_failure("Radio B")

    radio.reset_channel_failures("Radio A")

    data = json.loads((tmp_path / radio.FAILCOUNT_FILE).read_text(encoding="utf-8"))
    assert data == {"Radio B": 1}


def test_reset_channel_failures_is_a_noop_when_name_not_present(tmp_path, monkeypatch):
    monkeypatch.setattr(radio, "get_profile_data_dir", lambda: tmp_path)
    radio.reset_channel_failures("Radio Desconocida")  # no debe lanzar
    assert not (tmp_path / radio.FAILCOUNT_FILE).exists()


def test_reset_channel_failures_with_empty_name_is_a_noop():
    radio.reset_channel_failures("")  # no debe lanzar ni tocar disco
