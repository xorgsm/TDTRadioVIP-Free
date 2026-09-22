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
    # Sin esto, cada test que importa un perfil lanzaría un icacls.exe
    # real contra un archivo de tmp_path -- lento e innecesario aquí; el
    # propio endurecimiento de la ACL se cubre aparte (ver
    # test_register_with_openvpn_restricts_the_copied_file_to_the_current_user).
    monkeypatch.setattr(vpn_client, "restrict_config_file_to_current_user", lambda path: True)
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
        saneado, _ = vpn_profiles._strip_dangerous_directives(source.read_text(encoding="utf-8"))
        assert Path(entry["conf_path"]).read_text(encoding="utf-8") == saneado
        assert entry["conf_path"].endswith(f"{entry['tunnel']}.ovpn")
        registered = openvpn_config_dir / f"{entry['tunnel']}.ovpn"
        assert registered.read_text(encoding="utf-8") == saneado
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


def test_register_retries_after_permission_error_if_uac_grant_succeeds(monkeypatch, tmp_path):
    """Instalaciones de OpenVPN donde el instalador no dejó permiso de
    escritura para "OpenVPN Administrators" en la carpeta de configs
    (aunque el usuario sí pertenezca al grupo): la primera copia falla
    con PermissionError, se pide una elevación única
    (vpn_client.grant_config_dir_access()) y, si el usuario la acepta,
    se reintenta la copia una vez."""
    openvpn_config_dir = _redirect_profiles(monkeypatch, tmp_path)
    calls = {"copy_attempts": 0}
    real_copy = vpn_profiles.shutil.copy2

    def _flaky_copy2(src, dst):
        calls["copy_attempts"] += 1
        if calls["copy_attempts"] == 1:
            raise PermissionError(13, "Permission denied", str(dst))
        return real_copy(src, dst)

    monkeypatch.setattr(vpn_profiles.shutil, "copy2", _flaky_copy2)
    monkeypatch.setattr(vpn_profiles.vpn_client, "grant_config_dir_access", lambda: True)
    source = _write_conf(tmp_path / "src")
    try:
        entry = vpn_profiles.import_profile("Portugal", source)
        assert calls["copy_attempts"] == 2
        registered = openvpn_config_dir / f"{entry['tunnel']}.ovpn"
        saneado, _ = vpn_profiles._strip_dangerous_directives(source.read_text(encoding="utf-8"))
        assert registered.read_text(encoding="utf-8") == saneado
    finally:
        config._profile_dir_for.cache_clear()


def test_register_gives_up_when_uac_grant_is_declined(monkeypatch, tmp_path):
    _redirect_profiles(monkeypatch, tmp_path)

    def _always_denied(src, dst):
        raise PermissionError(13, "Permission denied", str(dst))

    monkeypatch.setattr(vpn_profiles.shutil, "copy2", _always_denied)
    monkeypatch.setattr(vpn_profiles.vpn_client, "grant_config_dir_access", lambda: False)
    source = _write_conf(tmp_path / "src")
    try:
        with pytest.raises(vpn_profiles.VpnProfileError, match="OpenVPN Administrators"):
            vpn_profiles.import_profile("Portugal", source)
        assert vpn_profiles.list_profiles() == []
    finally:
        config._profile_dir_for.cache_clear()


def test_register_reports_error_when_still_failing_after_granted_access(monkeypatch, tmp_path):
    _redirect_profiles(monkeypatch, tmp_path)

    def _always_denied(src, dst):
        raise PermissionError(13, "Permission denied", str(dst))

    monkeypatch.setattr(vpn_profiles.shutil, "copy2", _always_denied)
    monkeypatch.setattr(vpn_profiles.vpn_client, "grant_config_dir_access", lambda: True)
    source = _write_conf(tmp_path / "src")
    try:
        with pytest.raises(vpn_profiles.VpnProfileError, match="Portugal|acceso|Permission"):
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


def test_import_profile_from_text_registers_it_without_a_source_file(monkeypatch, tmp_path):
    openvpn_config_dir = _redirect_profiles(monkeypatch, tmp_path)
    body = "client\ndev tun\nproto udp\nremote jp1.vpngate.net 1194\n"
    try:
        entry = vpn_profiles.import_profile_from_text("Japón (VPNGate)", body)
        assert entry["name"] == "Japón (VPNGate)"
        saneado, _ = vpn_profiles._strip_dangerous_directives(body)
        assert Path(entry["conf_path"]).read_text(encoding="utf-8") == saneado
        registered = openvpn_config_dir / f"{entry['tunnel']}.ovpn"
        assert registered.read_text(encoding="utf-8") == saneado
    finally:
        config._profile_dir_for.cache_clear()


def test_import_profile_from_text_rejects_invalid_content(monkeypatch, tmp_path):
    _redirect_profiles(monkeypatch, tmp_path)
    try:
        with pytest.raises(vpn_profiles.VpnProfileError, match="no parece"):
            vpn_profiles.import_profile_from_text("Bogus", "not an openvpn conf")
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


# --------------------------------------------------------------------------
# _strip_dangerous_directives(): un .ovpn de VPNGate (lista pública, sin
# curar) o importado a mano puede traer directivas capaces de ejecutar
# código (up/down/client-connect/plugin...) con los privilegios del
# servicio interactivo de OpenVPN -- ver el comentario junto a
# _DANGEROUS_DIRECTIVES. Estos tests cubren el saneado en sí (puro, sin
# tocar disco) y que import_profile()/import_profile_from_text() lo
# apliquen antes de escribir/registrar el .ovpn.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("directiva", [
    "up /tmp/evil.sh",
    "down evil.sh",
    "route-up \"cmd /c calc.exe\"",
    "route-pre-down evil.sh",
    "ipchange evil.sh",
    "client-connect /tmp/evil.sh",
    "client-disconnect evil.sh",
    "tls-verify evil.sh",
    "auth-user-pass-verify evil.sh via-env",
    "plugin evil.dll",
    "script-security 3",
])
def test_strip_dangerous_directives_removes_known_code_execution_directives(directiva):
    ovpn = f"client\ndev tun\nproto udp\n{directiva}\nremote vpn.example.com 1194\n"
    limpio, quitadas = vpn_profiles._strip_dangerous_directives(ovpn)
    assert directiva not in limpio
    assert quitadas == [directiva]


def test_strip_dangerous_directives_is_case_insensitive_on_directive_name():
    ovpn = "client\nUP /tmp/evil.sh\nremote vpn.example.com 1194\n"
    limpio, quitadas = vpn_profiles._strip_dangerous_directives(ovpn)
    assert "evil.sh" not in limpio
    assert quitadas == ["UP /tmp/evil.sh"]


def test_strip_dangerous_directives_forces_script_security_zero_even_when_absent():
    ovpn = "client\ndev tun\nremote vpn.example.com 1194\n"
    limpio, quitadas = vpn_profiles._strip_dangerous_directives(ovpn)
    assert quitadas == []
    assert limpio.splitlines()[-1] == "script-security 0"


def test_strip_dangerous_directives_leaves_a_clean_config_unchanged_in_content():
    ovpn = "client\ndev tun\nproto udp\nremote vpn.example.com 1194\ncipher AES-256-GCM\n"
    limpio, quitadas = vpn_profiles._strip_dangerous_directives(ovpn)
    assert quitadas == []
    for line in ovpn.splitlines():
        assert line in limpio.splitlines()


def test_strip_dangerous_directives_ignores_comments_mentioning_directive_names():
    ovpn = "client\n# up /tmp/evil.sh (comentario, no directiva real)\nremote vpn.example.com 1194\n"
    limpio, quitadas = vpn_profiles._strip_dangerous_directives(ovpn)
    assert quitadas == []
    assert "# up /tmp/evil.sh" in limpio


def test_register_with_openvpn_restricts_the_copied_file_to_the_current_user(monkeypatch, tmp_path):
    """_register_with_openvpn() debe endurecer la ACL del .ovpn recién
    copiado a la carpeta compartida de OpenVPN -- ver el docstring de
    vpn_client.restrict_config_file_to_current_user()."""
    openvpn_config_dir = _redirect_profiles(monkeypatch, tmp_path)
    calls = []
    monkeypatch.setattr(
        vpn_profiles.vpn_client, "restrict_config_file_to_current_user",
        lambda path: calls.append(path) or True,
    )
    source = _write_conf(tmp_path / "src")
    try:
        entry = vpn_profiles.import_profile("Suecia", source)
        assert calls == [openvpn_config_dir / f"{entry['tunnel']}.ovpn"]
    finally:
        config._profile_dir_for.cache_clear()


def test_import_profile_from_text_strips_malicious_directives_before_writing(monkeypatch, tmp_path):
    """Integración: un .ovpn de VPNGate con un client-connect y un plugin
    (RCE/carga de DLL arbitraria contra el servicio interactivo de
    OpenVPN) se importa igualmente -- sigue teniendo 'client'/'remote ',
    únicos requisitos de _import_text -- pero sin esas directivas en el
    archivo que llega a disco ni al que se registra con OpenVPN."""
    openvpn_config_dir = _redirect_profiles(monkeypatch, tmp_path)
    malicioso = (
        "client\ndev tun\nproto udp\n"
        "client-connect /tmp/evil.sh\n"
        "plugin evil.dll\n"
        "remote vpn.example.com 1194\n"
    )
    try:
        entry = vpn_profiles.import_profile_from_text("Servidor sospechoso", malicioso)
        guardado = Path(entry["conf_path"]).read_text(encoding="utf-8")
        registrado = (openvpn_config_dir / f"{entry['tunnel']}.ovpn").read_text(encoding="utf-8")
        for texto in (guardado, registrado):
            assert "client-connect" not in texto
            assert "plugin" not in texto
            assert "evil.sh" not in texto
            assert "evil.dll" not in texto
            assert "script-security 0" in texto
    finally:
        config._profile_dir_for.cache_clear()
