from pathlib import Path

import pytest

from core import config
from core import vpn_client
from core import vpn_profiles


def _redirect_profiles(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "get_app_data_dir", lambda: tmp_path)
    config._profile_dir_for.cache_clear()
    openvpn_config_dir = tmp_path / "openvpn_config"
    monkeypatch.setattr(vpn_client, "find_config_dir", lambda: openvpn_config_dir)
    monkeypatch.setattr(vpn_client, "rescan", lambda: None)
    return openvpn_config_dir


def _write_conf(directory, name="server.ovpn", body=None):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(
        body or "client\ndev tun\nproto udp\nremote vpn.example.com 1194\n",
        encoding="utf-8",
    )
    return path


def test_import_profile_copies_conf_and_registers_it(monkeypatch, tmp_path):
    openvpn_config_dir = _redirect_profiles(monkeypatch, tmp_path)
    source = _write_conf(tmp_path / "src", "spain.ovpn")
    try:
        entry = vpn_profiles.import_profile("España", source)
        assert entry["name"] == "España"
        assert entry["tunnel"]
        profiles = vpn_profiles.list_profiles()
        assert [p["name"] for p in profiles] == ["España"]
        assert profiles[0]["conf_path"] == entry["conf_path"]
        assert Path(entry["conf_path"]).read_text(encoding="utf-8") == source.read_text(encoding="utf-8")
        assert entry["conf_path"].endswith(f"{entry['tunnel']}.ovpn")
        registered = openvpn_config_dir / f"{entry['tunnel']}.ovpn"
        assert registered.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")
    finally:
        config._profile_dir_for.cache_clear()


def test_import_profile_rejects_duplicate_name(monkeypatch, tmp_path):
    _redirect_profiles(monkeypatch, tmp_path)
    source = _write_conf(tmp_path / "src")
    try:
        vpn_profiles.import_profile("Francia", source)
        with pytest.raises(vpn_profiles.VpnProfileError, match="Ya existe"):
            vpn_profiles.import_profile("Francia", source)
    finally:
        config._profile_dir_for.cache_clear()


def test_import_profile_rejects_missing_source(monkeypatch, tmp_path):
    _redirect_profiles(monkeypatch, tmp_path)
    try:
        with pytest.raises(vpn_profiles.VpnProfileError, match="No se encuentra"):
            vpn_profiles.import_profile("Italia", tmp_path / "no_existe.ovpn")
    finally:
        config._profile_dir_for.cache_clear()


def test_import_profile_rejects_non_openvpn_file(monkeypatch, tmp_path):
    _redirect_profiles(monkeypatch, tmp_path)
    bogus = _write_conf(tmp_path / "src", "bogus.ovpn", body="not an openvpn conf")
    try:
        with pytest.raises(vpn_profiles.VpnProfileError, match="no parece"):
            vpn_profiles.import_profile("Bogus", bogus)
    finally:
        config._profile_dir_for.cache_clear()


def test_import_profile_rejects_blank_name(monkeypatch, tmp_path):
    _redirect_profiles(monkeypatch, tmp_path)
    source = _write_conf(tmp_path / "src")
    try:
        with pytest.raises(vpn_profiles.VpnProfileError, match="nombre"):
            vpn_profiles.import_profile("   ", source)
    finally:
        config._profile_dir_for.cache_clear()


def test_import_profile_rejects_when_openvpn_registration_fails(monkeypatch, tmp_path):
    _redirect_profiles(monkeypatch, tmp_path)

    def _raise(dest, tunnel):
        raise OSError("acceso denegado")

    monkeypatch.setattr(vpn_profiles, "_register_with_openvpn", _raise)
    source = _write_conf(tmp_path / "src")
    try:
        with pytest.raises(vpn_profiles.VpnProfileError, match="OpenVPN Administrators"):
            vpn_profiles.import_profile("Portugal", source)
        assert vpn_profiles.list_profiles() == []
    finally:
        config._profile_dir_for.cache_clear()


def test_two_profiles_with_colliding_sanitized_names_get_distinct_tunnels(monkeypatch, tmp_path):
    _redirect_profiles(monkeypatch, tmp_path)
    source_a = _write_conf(tmp_path / "src", "a.ovpn")
    source_b = _write_conf(tmp_path / "src2", "b.ovpn")
    try:
        first = vpn_profiles.import_profile("País #1", source_a)
        second = vpn_profiles.import_profile("País #2", source_b)
        assert first["tunnel"] != second["tunnel"]
    finally:
        config._profile_dir_for.cache_clear()


def test_get_profile_returns_none_when_missing(monkeypatch, tmp_path):
    _redirect_profiles(monkeypatch, tmp_path)
    try:
        assert vpn_profiles.get_profile("No existe") is None
    finally:
        config._profile_dir_for.cache_clear()


def test_delete_profile_removes_conf_index_entry_and_openvpn_registration(monkeypatch, tmp_path):
    openvpn_config_dir = _redirect_profiles(monkeypatch, tmp_path)
    source = _write_conf(tmp_path / "src")
    try:
        entry = vpn_profiles.import_profile("Alemania", source)
        assert Path(entry["conf_path"]).exists()
        registered = openvpn_config_dir / f"{entry['tunnel']}.ovpn"
        assert registered.exists()
        vpn_profiles.delete_profile("Alemania")
        assert vpn_profiles.get_profile("Alemania") is None
        assert not Path(entry["conf_path"]).exists()
        assert not registered.exists()
    finally:
        config._profile_dir_for.cache_clear()


def test_delete_profile_is_a_no_op_when_missing(monkeypatch, tmp_path):
    _redirect_profiles(monkeypatch, tmp_path)
    try:
        vpn_profiles.delete_profile("No existe")  # no debe lanzar
    finally:
        config._profile_dir_for.cache_clear()


def test_list_profiles_sorted_case_insensitively(monkeypatch, tmp_path):
    _redirect_profiles(monkeypatch, tmp_path)
    source_a = _write_conf(tmp_path / "src", "a.ovpn")
    source_b = _write_conf(tmp_path / "src2", "b.ovpn")
    try:
        vpn_profiles.import_profile("zelanda", source_a)
        vpn_profiles.import_profile("Alemania", source_b)
        names = [p["name"] for p in vpn_profiles.list_profiles()]
        assert names == ["Alemania", "zelanda"]
    finally:
        config._profile_dir_for.cache_clear()
