"""
Cobertura de core/torrent_history.py: historial persistente de torrents
completados (la lista "Completados" de la pestaña Torrents).
"""
import json

import pytest

from core import torrent_history


@pytest.fixture
def profile_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(torrent_history, "get_profile_data_dir", lambda: tmp_path)
    return tmp_path


def _history_file(profile_dir):
    return profile_dir / torrent_history.TORRENT_HISTORY_FILE


def test_add_entry_puts_newest_first_with_timestamp(profile_dir):
    torrent_history.add_entry("a", "C:/d/a", 10)
    historial = torrent_history.add_entry("b", "C:/d/b", 20)

    assert [e["name"] for e in historial] == ["b", "a"]
    assert historial[0]["size"] == 20
    assert historial[0]["timestamp"]
    assert torrent_history.load_history() == historial
    assert torrent_history.has_entry("a", "C:/d/a")
    assert not torrent_history.has_entry("a", "C:/otra/a")


def test_add_entry_moves_existing_entry_to_top_instead_of_duplicating(profile_dir):
    torrent_history.add_entry("a", "C:/d/a")
    torrent_history.add_entry("b", "C:/d/b")

    historial = torrent_history.add_entry("a", "C:/d/a")

    assert [e["name"] for e in historial] == ["a", "b"]


@pytest.mark.parametrize("name, path", [("", "C:/d"), ("a", "")])
def test_add_entry_ignores_empty_name_or_path(profile_dir, name, path):
    assert torrent_history.add_entry(name, path) == []
    assert not _history_file(profile_dir).exists()


def test_add_entry_caps_history_size(profile_dir, monkeypatch):
    monkeypatch.setattr(torrent_history, "MAX_ENTRIES", 3)
    for i in range(5):
        torrent_history.add_entry(f"t{i}", f"C:/d/t{i}")

    assert [e["name"] for e in torrent_history.load_history()] == ["t4", "t3", "t2"]


def test_remove_entry_and_clear_history(profile_dir):
    torrent_history.add_entry("a", "C:/d/a")
    torrent_history.add_entry("b", "C:/d/b")

    assert [e["name"] for e in torrent_history.remove_entry("a", "C:/d/a")] == ["b"]
    assert torrent_history.clear_history() == []
    assert torrent_history.load_history() == []


@pytest.mark.parametrize("contenido", [
    "{no es json",
    '{"a": 1}',
])
def test_load_history_returns_empty_for_corrupt_file(profile_dir, contenido):
    _history_file(profile_dir).write_text(contenido, encoding="utf-8")

    assert torrent_history.load_history() == []


def test_load_history_returns_empty_for_non_utf8_file(profile_dir):
    """Un archivo dañado que ni siquiera es UTF-8 válido no puede hacer
    reventar la construcción del panel de Torrents."""
    _history_file(profile_dir).write_bytes(b"\xff\xfe\x00basura")

    assert torrent_history.load_history() == []


def test_load_history_skips_malformed_entries(profile_dir):
    _history_file(profile_dir).write_text(json.dumps([
        {"name": "ok", "path": "C:/d/ok", "size": 5, "timestamp": "01/01/2026 10:00"},
        "texto",
        {"name": "", "path": "C:/d"},
        {"name": "sin ruta"},
        {"name": 123, "path": "C:/d/num"},
        {"name": "ruta rara", "path": ["C:/d"]},
        {"name": "tamaño raro", "path": "C:/d/x", "size": "grande"},
    ]), encoding="utf-8")

    assert [e["name"] for e in torrent_history.load_history()] == ["ok"]
