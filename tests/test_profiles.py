import pytest

from core import config


def _redirect_profiles(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "get_app_data_dir", lambda: tmp_path)
    config._profile_dir_for.cache_clear()


def test_duplicate_and_delete_profile(monkeypatch, tmp_path):
    _redirect_profiles(monkeypatch, tmp_path)
    source = config.create_profile("Origen")
    (config._profile_dir_for(source) / "favorites.json").write_text("[]", encoding="utf-8")
    try:
        duplicate = config.duplicate_profile("Origen", "Copia")
        assert (config._profile_dir_for(duplicate) / "favorites.json").exists()
        config.delete_profile("Copia")
        assert "Copia" not in config.list_profiles()
    finally:
        config._profile_dir_for.cache_clear()


def test_default_profile_cannot_be_deleted_or_renamed(monkeypatch, tmp_path):
    _redirect_profiles(monkeypatch, tmp_path)
    try:
        with pytest.raises(ValueError):
            config.delete_profile("Default")
        with pytest.raises(ValueError):
            config.rename_profile("Default", "Otro")
    finally:
        config._profile_dir_for.cache_clear()


def test_duplicate_default_copies_only_its_profile_data(monkeypatch, tmp_path):
    _redirect_profiles(monkeypatch, tmp_path)
    (tmp_path / "favorites.json").write_text('["La 1"]', encoding="utf-8")
    (tmp_path / "settings.json").write_text('{"volume": 80}', encoding="utf-8")
    (tmp_path / "cache").mkdir()
    (tmp_path / "cache" / "epg.xml").write_text("cache", encoding="utf-8")
    try:
        duplicate = config.duplicate_profile("Default", "Copia")
        copied = config._profile_dir_for(duplicate)
        assert (copied / "favorites.json").read_text(encoding="utf-8") == '["La 1"]'
        assert not (copied / "settings.json").exists()
        assert not (copied / "cache").exists()
        assert not (copied / "profiles").exists()
    finally:
        config._profile_dir_for.cache_clear()


def test_duplicate_profile_rejects_an_existing_destination(monkeypatch, tmp_path):
    _redirect_profiles(monkeypatch, tmp_path)
    try:
        config.create_profile("Origen")
        config.create_profile("Copia")
        with pytest.raises(ValueError, match="Ya existe"):
            config.duplicate_profile("Origen", "Copia")
    finally:
        config._profile_dir_for.cache_clear()


def test_duplicate_profile_rejects_destination_with_different_case(monkeypatch, tmp_path):
    _redirect_profiles(monkeypatch, tmp_path)
    try:
        config.create_profile("Origen")
        config.create_profile("Familia")
        with pytest.raises(ValueError, match="Ya existe"):
            config.duplicate_profile("Origen", "familia")
    finally:
        config._profile_dir_for.cache_clear()


def test_rename_profile_rejects_same_name_with_different_case(monkeypatch, tmp_path):
    _redirect_profiles(monkeypatch, tmp_path)
    try:
        profile = config.create_profile("Familia")
        marker = config._profile_dir_for(profile) / "favorites.json"
        marker.write_text('["La 1"]', encoding="utf-8")

        with pytest.raises(ValueError, match="Ya existe"):
            config.rename_profile("Familia", "familia")

        assert marker.read_text(encoding="utf-8") == '["La 1"]'
        assert "Familia" in config.list_profiles()
    finally:
        config._profile_dir_for.cache_clear()


def test_profile_lookup_uses_canonical_spelling(monkeypatch, tmp_path):
    _redirect_profiles(monkeypatch, tmp_path)
    monkeypatch.setattr(config, "load_settings", lambda: {"active_profile": "familia"})
    try:
        config.create_profile("Familia")
        assert config.get_current_profile() == "Familia"
    finally:
        config._profile_dir_for.cache_clear()


def test_session_profile_is_pinned_until_restart(monkeypatch, tmp_path):
    _redirect_profiles(monkeypatch, tmp_path)
    ajustes = {"active_profile": "Default"}
    monkeypatch.setattr(config, "load_settings", lambda: dict(ajustes))
    config.create_profile("Familia")
    try:
        assert config.pin_session_profile() == "Default"
        ajustes["active_profile"] = "Familia"  # cambiado en Configuración

        assert config.get_current_profile() == "Default"
        assert config.get_profile_data_dir() == config._profile_dir_for("Default")
    finally:
        config._session_profile = None
        config._profile_dir_for.cache_clear()


def test_profile_in_use_cannot_be_deleted(monkeypatch, tmp_path):
    _redirect_profiles(monkeypatch, tmp_path)
    monkeypatch.setattr(config, "load_settings", lambda: {"active_profile": "Familia"})
    config.create_profile("Familia")
    try:
        config.pin_session_profile()
        with pytest.raises(ValueError):
            config.delete_profile("Familia")
        assert "Familia" in config.list_profiles()
    finally:
        config._session_profile = None
        config._profile_dir_for.cache_clear()
