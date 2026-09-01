"""Pruebas de core/config.py que no tocan el APPDATA real."""
import pytest

from core import config
from core.config import DEFAULT_SETTINGS


@pytest.mark.parametrize(
    "name",
    ["con", "CON", "prn.json", "COM1", "lpt9", "Perfil. ", r"..\otro", "sub/perfil"],
)
def test_create_profile_rejects_windows_reserved_names(monkeypatch, tmp_path, name):
    # mkdir() sobre una carpeta llamada "con", "prn", "com1"... revienta con
    # OSError en Windows sin que _profile_dir_for lo capture -- create_profile
    # debe rechazarlas con ValueError antes de intentar crear la carpeta.
    monkeypatch.setattr(config, "get_app_data_dir", lambda: tmp_path)
    config._profile_dir_for.cache_clear()
    try:
        with pytest.raises(ValueError):
            config.create_profile(name)
    finally:
        config._profile_dir_for.cache_clear()


def test_create_profile_accepts_normal_name(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "get_app_data_dir", lambda: tmp_path)
    config._profile_dir_for.cache_clear()
    try:
        assert config.create_profile("Familia") == "Familia"
    finally:
        config._profile_dir_for.cache_clear()


def test_profile_apis_reject_path_traversal(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "get_app_data_dir", lambda: tmp_path)
    config._profile_dir_for.cache_clear()
    try:
        for action in (
            lambda: config.get_profile_data_dir(r"..\fuera"),
            lambda: config.set_current_profile(r"..\fuera"),
            lambda: config.rename_profile(r"..\fuera", "Destino"),
            lambda: config.delete_profile(r"..\fuera"),
        ):
            with pytest.raises(ValueError):
                action()
        assert not (tmp_path.parent / "fuera").exists()
    finally:
        config._profile_dir_for.cache_clear()


def test_invalid_active_profile_falls_back_to_default(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "get_app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(config, "load_settings", lambda: {"active_profile": r"..\fuera"})
    config._profile_dir_for.cache_clear()
    try:
        assert config.get_current_profile() == config.DEFAULT_PROFILE
        assert config.get_profile_data_dir() == tmp_path
        assert not (tmp_path.parent / "fuera").exists()
    finally:
        config._profile_dir_for.cache_clear()


def test_splash_free_seen_defaults_to_false():
    # El splash de bienvenida debe mostrarse en el primer arranque; solo
    # tras elegir "Continuar en modo gratuito" se recuerda la elección.
    assert DEFAULT_SETTINGS["splash_free_seen"] is False


def test_app_org_uses_coder_by_xor(monkeypatch, tmp_path):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    config.get_app_data_dir.cache_clear()
    try:
        migrated = config.get_app_data_dir()
        assert migrated == tmp_path / "CoderByXOR" / config.APP_DATA_NAME
        assert config.APP_ORG == "CoderByXOR"
        assert config.LEGACY_APP_ORG == "CoderByXOR"
    finally:
        config.get_app_data_dir.cache_clear()
