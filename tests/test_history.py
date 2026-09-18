"""
Tests de core/history.py -- historial de lo último reproducido, persistido
en history.json dentro de la carpeta de datos del perfil activo.

Mismo patrón de aislamiento que tests/test_favorites.py y
tests/test_vpn_profiles.py: se redirige config.get_app_data_dir() a
tmp_path y se limpia la cache de core.config._profile_dir_for (lru_cache)
antes y después de cada test.
"""
import json

import pytest

from core import config
from core import history


def _redirect(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "get_app_data_dir", lambda: tmp_path)
    config._profile_dir_for.cache_clear()


@pytest.fixture(autouse=True)
def _clear_profile_cache():
    yield
    config._profile_dir_for.cache_clear()


# --------------------------------------------------------------------------
# load_history
# --------------------------------------------------------------------------

def test_load_history_returns_empty_list_when_file_does_not_exist(monkeypatch, tmp_path):
    _redirect(monkeypatch, tmp_path)
    assert history.load_history() == []


def test_load_history_returns_empty_list_when_json_is_corrupt(monkeypatch, tmp_path):
    _redirect(monkeypatch, tmp_path)
    path = tmp_path / history.HISTORY_FILE
    path.write_text('[{"type": "tv", "name": "La 1"', encoding="utf-8")  # sin cerrar

    assert history.load_history() == []


def test_load_history_returns_empty_list_when_json_root_is_not_a_list(monkeypatch, tmp_path):
    _redirect(monkeypatch, tmp_path)
    path = tmp_path / history.HISTORY_FILE
    path.write_text(json.dumps({"type": "tv", "name": "La 1"}), encoding="utf-8")

    assert history.load_history() == []


def test_load_history_discards_malformed_entries(monkeypatch, tmp_path):
    _redirect(monkeypatch, tmp_path)
    path = tmp_path / history.HISTORY_FILE
    path.write_text(json.dumps([
        {"type": "tv", "name": "La 1"},
        {"type": "tv"},  # sin name
        {"name": "Sin tipo"},  # sin type
        "no soy un dict",
        {"type": "radio", "name": "Los 40"},
    ]), encoding="utf-8")

    result = history.load_history()
    assert [e["name"] for e in result] == ["La 1", "Los 40"]


# --------------------------------------------------------------------------
# add_entry
# --------------------------------------------------------------------------

def test_add_entry_adds_new_entry_at_the_front_with_play_count_one(monkeypatch, tmp_path):
    _redirect(monkeypatch, tmp_path)
    result = history.add_entry("tv", "La 1", url="http://x")

    assert len(result) == 1
    entry = result[0]
    assert entry["type"] == "tv"
    assert entry["name"] == "La 1"
    assert entry["url"] == "http://x"
    assert entry["play_count"] == 1
    assert entry["timestamp"]  # se ha rellenado con algo


def test_add_entry_moves_existing_entry_to_the_front(monkeypatch, tmp_path):
    _redirect(monkeypatch, tmp_path)
    history.add_entry("tv", "La 1")
    history.add_entry("radio", "Los 40")
    result = history.add_entry("tv", "La 1")  # se reproduce otra vez

    assert [e["name"] for e in result] == ["La 1", "Los 40"]
    assert len(result) == 2  # no se duplica


def test_add_entry_increments_play_count_instead_of_resetting_it(monkeypatch, tmp_path):
    """El play_count se conserva incrementado -- así top_played() sabe qué
    se reproduce más, no solo qué se reprodujo la última vez."""
    _redirect(monkeypatch, tmp_path)
    history.add_entry("tv", "La 1")
    history.add_entry("tv", "La 1")
    result = history.add_entry("tv", "La 1")

    assert result[0]["play_count"] == 3


def test_add_entry_is_a_no_op_when_type_or_name_is_missing(monkeypatch, tmp_path):
    _redirect(monkeypatch, tmp_path)
    history.add_entry("tv", "La 1")

    unchanged = history.add_entry("", "La 1")
    assert [e["name"] for e in unchanged] == ["La 1"]

    unchanged = history.add_entry("tv", "")
    assert [e["name"] for e in unchanged] == ["La 1"]


def test_add_entry_persists_across_reload(monkeypatch, tmp_path):
    _redirect(monkeypatch, tmp_path)
    history.add_entry("tv", "La 1", url="http://x")

    reloaded = history.load_history()
    assert len(reloaded) == 1
    assert reloaded[0]["name"] == "La 1"
    assert reloaded[0]["url"] == "http://x"


def test_add_entry_caps_history_at_max_entries(monkeypatch, tmp_path):
    """El historial se recorta a MAX_ENTRIES para que el zapeo no lo haga
    crecer indefinidamente."""
    _redirect(monkeypatch, tmp_path)
    for i in range(history.MAX_ENTRIES):
        history.add_entry("tv", f"Canal {i}")

    assert len(history.load_history()) == history.MAX_ENTRIES

    result = history.add_entry("tv", "Canal nuevo")

    assert len(result) == history.MAX_ENTRIES
    names = [e["name"] for e in result]
    assert names[0] == "Canal nuevo"
    # El más antiguo (Canal 0, insertado primero) se ha caído del límite.
    assert "Canal 0" not in names


# --------------------------------------------------------------------------
# clear_history
# --------------------------------------------------------------------------

def test_clear_history_empties_and_persists(monkeypatch, tmp_path):
    _redirect(monkeypatch, tmp_path)
    history.add_entry("tv", "La 1")

    result = history.clear_history()

    assert result == []
    assert history.load_history() == []


# --------------------------------------------------------------------------
# top_played
# --------------------------------------------------------------------------

def test_top_played_sorts_by_play_count_descending(monkeypatch, tmp_path):
    _redirect(monkeypatch, tmp_path)
    history.add_entry("tv", "Poco")
    for _ in range(3):
        history.add_entry("tv", "Mucho")
    for _ in range(2):
        history.add_entry("radio", "Medio")

    result = history.top_played()

    assert [e["name"] for e in result] == ["Mucho", "Medio", "Poco"]


def test_top_played_respects_limit(monkeypatch, tmp_path):
    _redirect(monkeypatch, tmp_path)
    for i in range(5):
        history.add_entry("tv", f"Canal {i}")

    assert len(history.top_played(limit=2)) == 2


def test_top_played_uses_provided_history_instead_of_reloading(monkeypatch, tmp_path):
    _redirect(monkeypatch, tmp_path)
    # Nada guardado en disco: se le pasa la lista explícitamente.
    provided = [
        {"type": "tv", "name": "A", "play_count": 1},
        {"type": "tv", "name": "B", "play_count": 5},
    ]

    result = history.top_played(provided)

    assert [e["name"] for e in result] == ["B", "A"]


def test_top_played_treats_missing_play_count_as_one(monkeypatch, tmp_path):
    """Historiales guardados antes de la 6.4 no tenían play_count: deben
    contar como 1 reproducción en vez de romper el orden."""
    _redirect(monkeypatch, tmp_path)
    legacy_and_new = [
        {"type": "tv", "name": "Antiguo"},  # sin play_count
        {"type": "tv", "name": "Nuevo", "play_count": 3},
    ]

    result = history.top_played(legacy_and_new)

    assert [e["name"] for e in result] == ["Nuevo", "Antiguo"]


# --------------------------------------------------------------------------
# tolerancia a fallos de escritura
# --------------------------------------------------------------------------

def test_add_entry_does_not_raise_when_disk_write_fails(monkeypatch, tmp_path):
    _redirect(monkeypatch, tmp_path)

    def _raise(*args, **kwargs):
        raise OSError("disco lleno")

    monkeypatch.setattr(history, "write_json_atomic", _raise)

    result = history.add_entry("tv", "La 1")
    assert [e["name"] for e in result] == ["La 1"]
