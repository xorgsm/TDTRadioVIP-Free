"""
Tests de core/favorites.py -- gestión de canales/emisoras marcados como
favoritos, persistidos en favorites.json dentro de la carpeta de datos del
perfil activo.

Sigue el patrón de tests/test_vpn_profiles.py para aislar la carpeta de
datos: se redirige config.get_app_data_dir() a tmp_path y se limpia la
cache de core.config._profile_dir_for (lru_cache) antes y después de cada
test, para que un test no vea la carpeta que dejó cacheada el anterior.
"""
import json

import pytest

from core import config
from core import favorites


def _redirect(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "get_app_data_dir", lambda: tmp_path)
    config._profile_dir_for.cache_clear()


@pytest.fixture(autouse=True)
def _clear_profile_cache():
    yield
    config._profile_dir_for.cache_clear()


# --------------------------------------------------------------------------
# load_favorites
# --------------------------------------------------------------------------

def test_load_favorites_returns_empty_list_when_file_does_not_exist(monkeypatch, tmp_path):
    _redirect(monkeypatch, tmp_path)
    assert favorites.load_favorites() == []


def test_load_favorites_returns_empty_list_when_json_is_corrupt(monkeypatch, tmp_path):
    _redirect(monkeypatch, tmp_path)
    path = tmp_path / favorites.FAVORITES_FILE
    path.write_text('[{"type": "tv", "name": "La 1"', encoding="utf-8")  # sin cerrar

    assert favorites.load_favorites() == []


def test_load_favorites_returns_empty_list_when_json_root_is_not_a_list(monkeypatch, tmp_path):
    _redirect(monkeypatch, tmp_path)
    path = tmp_path / favorites.FAVORITES_FILE
    path.write_text(json.dumps({"type": "tv", "name": "La 1"}), encoding="utf-8")

    assert favorites.load_favorites() == []


def test_load_favorites_discards_malformed_entries(monkeypatch, tmp_path):
    """Un archivo corrupto no debe tumbar la app: se descartan las entradas
    sin 'type' o sin 'name', y se conservan las válidas."""
    _redirect(monkeypatch, tmp_path)
    path = tmp_path / favorites.FAVORITES_FILE
    path.write_text(json.dumps([
        {"type": "tv", "name": "La 1"},
        {"type": "tv"},  # sin name
        {"name": "Sin tipo"},  # sin type
        "no soy un dict",
        {"type": "", "name": "Tipo vacio"},  # type vacio -> falsy
        {"type": "radio", "name": "Los 40"},
    ]), encoding="utf-8")

    result = favorites.load_favorites()
    assert [f["name"] for f in result] == ["La 1", "Los 40"]


# --------------------------------------------------------------------------
# toggle_favorite / is_favorite
# --------------------------------------------------------------------------

def test_toggle_favorite_adds_new_entry_at_the_front(monkeypatch, tmp_path):
    _redirect(monkeypatch, tmp_path)
    favorites.toggle_favorite("tv", "La 1", url="http://x", logo="l.png")
    result = favorites.toggle_favorite("radio", "Los 40")

    assert [f["name"] for f in result] == ["Los 40", "La 1"]
    assert result[1] == {"type": "tv", "name": "La 1", "url": "http://x", "logo": "l.png", "folder": ""}


def test_toggle_favorite_removes_entry_when_already_present(monkeypatch, tmp_path):
    _redirect(monkeypatch, tmp_path)
    favorites.toggle_favorite("tv", "La 1")
    result = favorites.toggle_favorite("tv", "La 1")

    assert result == []


def test_toggle_favorite_is_a_no_op_when_type_or_name_is_missing(monkeypatch, tmp_path):
    _redirect(monkeypatch, tmp_path)
    favorites.toggle_favorite("tv", "La 1")

    unchanged = favorites.toggle_favorite("", "La 1")
    assert [f["name"] for f in unchanged] == ["La 1"]

    unchanged = favorites.toggle_favorite("tv", "")
    assert [f["name"] for f in unchanged] == ["La 1"]


def test_toggle_favorite_persists_across_reload(monkeypatch, tmp_path):
    """Los datos deben sobrevivir a un 'reinicio' -- volver a leer desde
    disco en vez de depender de un estado en memoria."""
    _redirect(monkeypatch, tmp_path)
    favorites.toggle_favorite("tv", "La 1", url="http://x")

    reloaded = favorites.load_favorites()
    assert reloaded == [{"type": "tv", "name": "La 1", "url": "http://x", "logo": "", "folder": ""}]


def test_is_favorite_true_when_present_false_otherwise(monkeypatch, tmp_path):
    _redirect(monkeypatch, tmp_path)
    favs = favorites.toggle_favorite("tv", "La 1")

    assert favorites.is_favorite(favs, "tv", "La 1") is True
    assert favorites.is_favorite(favs, "radio", "La 1") is False
    assert favorites.is_favorite(favs, "tv", "Otra") is False


def test_is_favorite_false_when_type_or_name_is_missing(monkeypatch, tmp_path):
    _redirect(monkeypatch, tmp_path)
    favs = favorites.toggle_favorite("tv", "La 1")

    assert favorites.is_favorite(favs, "", "La 1") is False
    assert favorites.is_favorite(favs, "tv", "") is False


# --------------------------------------------------------------------------
# remove_favorite
# --------------------------------------------------------------------------

def test_remove_favorite_removes_matching_entry_without_toggling(monkeypatch, tmp_path):
    _redirect(monkeypatch, tmp_path)
    favorites.toggle_favorite("tv", "La 1")
    favorites.toggle_favorite("radio", "Los 40")

    result = favorites.remove_favorite("tv", "La 1")

    assert [f["name"] for f in result] == ["Los 40"]
    assert favorites.load_favorites() == result


def test_remove_favorite_is_a_no_op_when_entry_is_missing(monkeypatch, tmp_path):
    _redirect(monkeypatch, tmp_path)
    favorites.toggle_favorite("tv", "La 1")

    result = favorites.remove_favorite("tv", "No existe")

    assert [f["name"] for f in result] == ["La 1"]


# --------------------------------------------------------------------------
# carpetas: get_folders / set_favorite_folder / rename_folder / delete_folder
# --------------------------------------------------------------------------

def test_get_folders_returns_sorted_unique_non_empty_folder_names(monkeypatch, tmp_path):
    _redirect(monkeypatch, tmp_path)
    favorites.toggle_favorite("tv", "La 1", folder="Deportes")
    favorites.toggle_favorite("tv", "La 2", folder="Cine")
    favorites.toggle_favorite("radio", "Los 40", folder="Deportes")
    favorites.toggle_favorite("radio", "Sin carpeta")  # folder=""

    assert favorites.get_folders() == ["Cine", "Deportes"]


def test_get_folders_uses_provided_list_instead_of_reloading(monkeypatch, tmp_path):
    _redirect(monkeypatch, tmp_path)
    favs = [
        {"type": "tv", "name": "La 1", "folder": "Guardado"},
    ]
    # Nada en disco, pero se le pasa la lista explícitamente.
    assert favorites.get_folders(favs) == ["Guardado"]


def test_set_favorite_folder_assigns_folder_and_persists(monkeypatch, tmp_path):
    _redirect(monkeypatch, tmp_path)
    favorites.toggle_favorite("tv", "La 1")

    result = favorites.set_favorite_folder("tv", "La 1", "Deportes")

    assert result[0]["folder"] == "Deportes"
    assert favorites.load_favorites()[0]["folder"] == "Deportes"


def test_set_favorite_folder_with_empty_string_clears_folder(monkeypatch, tmp_path):
    _redirect(monkeypatch, tmp_path)
    favorites.toggle_favorite("tv", "La 1")
    favorites.set_favorite_folder("tv", "La 1", "Deportes")

    result = favorites.set_favorite_folder("tv", "La 1", "")

    assert result[0]["folder"] == ""


def test_set_favorite_folder_is_a_no_op_when_favorite_is_missing(monkeypatch, tmp_path):
    _redirect(monkeypatch, tmp_path)
    favorites.toggle_favorite("tv", "La 1")

    result = favorites.set_favorite_folder("tv", "No existe", "Deportes")

    assert result[0]["folder"] == ""


def test_rename_folder_renames_folder_on_all_matching_favorites(monkeypatch, tmp_path):
    _redirect(monkeypatch, tmp_path)
    favorites.toggle_favorite("tv", "La 1", folder="Deportes")
    favorites.toggle_favorite("radio", "Los 40", folder="Deportes")
    favorites.toggle_favorite("tv", "La 2", folder="Cine")

    result = favorites.rename_folder("Deportes", "Sport")

    folders_by_name = {f["name"]: f["folder"] for f in result}
    assert folders_by_name["La 1"] == "Sport"
    assert folders_by_name["Los 40"] == "Sport"
    assert folders_by_name["La 2"] == "Cine"


def test_delete_folder_clears_folder_field_but_keeps_the_favorites(monkeypatch, tmp_path):
    """Los favoritos de la carpeta borrada no se eliminan: pasan a
    'sin carpeta' (folder='')."""
    _redirect(monkeypatch, tmp_path)
    favorites.toggle_favorite("tv", "La 1", folder="Deportes")
    favorites.toggle_favorite("tv", "La 2", folder="Cine")

    result = favorites.delete_folder("Deportes")

    assert len(result) == 2
    folders_by_name = {f["name"]: f["folder"] for f in result}
    assert folders_by_name["La 1"] == ""
    assert folders_by_name["La 2"] == "Cine"


# --------------------------------------------------------------------------
# reorder
# --------------------------------------------------------------------------

def test_reorder_persists_the_list_exactly_as_given(monkeypatch, tmp_path):
    _redirect(monkeypatch, tmp_path)
    favorites.toggle_favorite("tv", "La 1")
    favorites.toggle_favorite("tv", "La 2")
    current = favorites.load_favorites()
    swapped = list(reversed(current))

    result = favorites.reorder(swapped)

    assert result == swapped
    assert favorites.load_favorites() == swapped


# --------------------------------------------------------------------------
# tolerancia a fallos de escritura
# --------------------------------------------------------------------------

def test_toggle_favorite_does_not_raise_when_disk_write_fails(monkeypatch, tmp_path):
    """Si _save() falla (disco lleno, sin permisos...) no debe tumbar la
    sesión -- ver el comentario de _save() en core/favorites.py."""
    _redirect(monkeypatch, tmp_path)

    def _raise(*args, **kwargs):
        raise OSError("disco lleno")

    monkeypatch.setattr(favorites, "write_json_atomic", _raise)

    result = favorites.toggle_favorite("tv", "La 1")
    assert [f["name"] for f in result] == ["La 1"]
