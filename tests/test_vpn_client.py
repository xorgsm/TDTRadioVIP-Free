from pathlib import Path

import pytest

from core import vpn_client


def _fake_registry(monkeypatch, value=None, raises=False):
    class _FakeKey:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def _open_key(hive, path):
        if raises:
            raise OSError("clave no encontrada")
        return _FakeKey()

    def _query_value(key, name):
        return (value, 1)

    monkeypatch.setattr(vpn_client.winreg, "OpenKey", _open_key)
    monkeypatch.setattr(vpn_client.winreg, "QueryValueEx", _query_value)


def test_find_config_dir_reads_registry_value(monkeypatch):
    _fake_registry(monkeypatch, value=r"C:\Custom\OpenVPN\config")
    assert vpn_client.find_config_dir() == Path(r"C:\Custom\OpenVPN\config")


def test_find_config_dir_falls_back_when_registry_missing(monkeypatch, tmp_path):
    _fake_registry(monkeypatch, raises=True)
    monkeypatch.setattr(vpn_client, "find_openvpn_gui_exe", lambda: None)
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "Program Files"))
    assert vpn_client.find_config_dir() == tmp_path / "Program Files" / "OpenVPN" / "config"


def test_find_log_dir_reads_hkcu_registry_value(monkeypatch):
    _fake_registry(monkeypatch, value=r"C:\Custom\OpenVPN\log")
    assert vpn_client.find_log_dir() == Path(r"C:\Custom\OpenVPN\log")


def test_find_log_dir_falls_back_to_userprofile_when_registry_missing(monkeypatch):
    """No es hermana de find_config_dir() -- una instalación real puede
    tener el config en la carpeta global (Program Files) y el log en la
    carpeta por usuario igualmente, así que aquí NO se monkeypatchea
    find_config_dir() a propósito: probaría lo contrario de lo que hace
    falta comprobar."""
    _fake_registry(monkeypatch, raises=True)
    monkeypatch.setenv("USERPROFILE", r"C:\Users\prueba")
    assert vpn_client.find_log_dir() == Path(r"C:\Users\prueba\OpenVPN\log")


def test_connect_raises_when_openvpn_not_installed(monkeypatch):
    monkeypatch.setattr(vpn_client, "find_openvpn_gui_exe", lambda: None)
    with pytest.raises(vpn_client.VpnClientError, match="no está instalado"):
        vpn_client.connect(Path("es.ovpn"), "es")


def test_disconnect_raises_when_openvpn_not_installed(monkeypatch):
    monkeypatch.setattr(vpn_client, "find_openvpn_gui_exe", lambda: None)
    with pytest.raises(vpn_client.VpnClientError, match="no está instalado"):
        vpn_client.disconnect("es")


def test_connect_runs_command_connect_with_tunnel_name(monkeypatch):
    monkeypatch.setattr(
        vpn_client, "find_openvpn_gui_exe", lambda: Path(r"C:\OpenVPN\bin\openvpn-gui.exe")
    )
    calls = []
    monkeypatch.setattr(vpn_client, "_run", lambda exe, *args: calls.append((exe, args)))
    vpn_client.connect(Path(r"C:\data\es.ovpn"), "es")
    exe = Path(r"C:\OpenVPN\bin\openvpn-gui.exe")
    assert calls == [
        (exe, ("--command", "silent_connection", "1")),
        (exe, ("--command", "connect", "es")),
    ]


def test_disconnect_runs_command_disconnect_with_tunnel_name(monkeypatch):
    monkeypatch.setattr(
        vpn_client, "find_openvpn_gui_exe", lambda: Path(r"C:\OpenVPN\bin\openvpn-gui.exe")
    )
    calls = []
    monkeypatch.setattr(vpn_client, "_run", lambda exe, *args: calls.append((exe, args)))
    vpn_client.disconnect("es")
    assert calls == [(Path(r"C:\OpenVPN\bin\openvpn-gui.exe"), ("--command", "disconnect", "es"))]


def test_rescan_is_a_no_op_when_openvpn_not_installed(monkeypatch):
    monkeypatch.setattr(vpn_client, "find_openvpn_gui_exe", lambda: None)
    calls = []
    monkeypatch.setattr(vpn_client, "_run", lambda exe, *args: calls.append((exe, args)))
    vpn_client.rescan()
    assert calls == []


def test_rescan_runs_command_rescan(monkeypatch):
    monkeypatch.setattr(
        vpn_client, "find_openvpn_gui_exe", lambda: Path(r"C:\OpenVPN\bin\openvpn-gui.exe")
    )
    calls = []
    monkeypatch.setattr(vpn_client, "_run", lambda exe, *args: calls.append((exe, args)))
    vpn_client.rescan()
    assert calls == [(Path(r"C:\OpenVPN\bin\openvpn-gui.exe"), ("--command", "rescan"))]


def test_status_false_when_log_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(vpn_client, "find_log_dir", lambda: tmp_path)
    assert vpn_client.status("es") is False


def test_status_true_when_last_event_is_connect(monkeypatch, tmp_path):
    (tmp_path / "es.log").write_text(
        "Fri Sep 12 12:00:00 2026 Initialization Sequence Completed\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(vpn_client, "find_log_dir", lambda: tmp_path)
    assert vpn_client.status("es") is True


def test_status_false_when_last_event_is_disconnect(monkeypatch, tmp_path):
    (tmp_path / "es.log").write_text(
        "Initialization Sequence Completed\n"
        "event_wait : Interrupted system call (code=4)\n"
        "TCP/UDP: Closing socket\n"
        "SIGTERM[soft,exit-with-notification] received, process exiting\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(vpn_client, "find_log_dir", lambda: tmp_path)
    assert vpn_client.status("es") is False


def test_status_true_after_reconnect_following_a_disconnect(monkeypatch, tmp_path):
    (tmp_path / "es.log").write_text(
        "Initialization Sequence Completed\n"
        "SIGTERM[soft,exit-with-notification] received, process exiting\n"
        "Initialization Sequence Completed\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(vpn_client, "find_log_dir", lambda: tmp_path)
    assert vpn_client.status("es") is True


def test_find_openvpn_gui_exe_prefers_standard_install_path(monkeypatch, tmp_path):
    program_files = tmp_path / "Program Files"
    exe = program_files / "OpenVPN" / "bin" / "openvpn-gui.exe"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"")
    monkeypatch.setenv("ProgramFiles", str(program_files))
    assert vpn_client.find_openvpn_gui_exe() == exe


def test_find_openvpn_gui_exe_falls_back_to_path(monkeypatch, tmp_path):
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "no_openvpn_here"))
    monkeypatch.setattr(vpn_client.shutil, "which", lambda name: r"C:\Tools\openvpn-gui.exe")
    assert vpn_client.find_openvpn_gui_exe() == Path(r"C:\Tools\openvpn-gui.exe")


def test_find_openvpn_gui_exe_none_when_not_found(monkeypatch, tmp_path):
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "no_openvpn_here"))
    monkeypatch.setattr(vpn_client.shutil, "which", lambda name: None)
    assert vpn_client.find_openvpn_gui_exe() is None


def test_grant_config_dir_access_true_on_exit_code_zero(monkeypatch, tmp_path):
    monkeypatch.setattr(vpn_client, "find_config_dir", lambda: tmp_path / "config")
    calls = []

    def _fake_elevated(file, parameters):
        calls.append((file, parameters))
        return 0

    monkeypatch.setattr(vpn_client, "_run_elevated", _fake_elevated)
    assert vpn_client.grant_config_dir_access() is True
    [(file, parameters)] = calls
    assert file == "icacls.exe"
    assert str(tmp_path / "config") in parameters
    assert "OpenVPN Administrators" in parameters


def test_grant_config_dir_access_false_on_nonzero_exit_code(monkeypatch, tmp_path):
    monkeypatch.setattr(vpn_client, "find_config_dir", lambda: tmp_path / "config")
    monkeypatch.setattr(vpn_client, "_run_elevated", lambda file, parameters: 5)
    assert vpn_client.grant_config_dir_access() is False


def test_run_raises_vpn_client_error_when_subprocess_times_out(monkeypatch):
    """openvpn-gui.exe puede no responder a tiempo (servicio interactivo
    ocupado) -- subprocess.run() lanza TimeoutExpired, que NO es un
    OSError, así que hacía falta capturarlo aparte para no dejarlo
    escapar sin convertir a VpnClientError (ver
    AppLifecycle.disconnect_vpn_profiles(), que depende de esto para no
    abortar el cierre de la app en silencio)."""
    import subprocess as subprocess_module

    def _raise(*args, **kwargs):
        raise subprocess_module.TimeoutExpired(cmd="openvpn-gui.exe", timeout=10)

    monkeypatch.setattr(vpn_client.subprocess, "run", _raise)
    with pytest.raises(vpn_client.VpnClientError):
        vpn_client._run(Path(r"C:\OpenVPN\bin\openvpn-gui.exe"), "--command", "disconnect", "es")


def test_connect_still_connects_when_silent_connection_command_fails(monkeypatch):
    """silent_connection es cosmético (evita la ventana emergente de
    openvpn-gui.exe) -- si falla no debe impedir el connect real."""
    monkeypatch.setattr(
        vpn_client, "find_openvpn_gui_exe", lambda: Path(r"C:\OpenVPN\bin\openvpn-gui.exe")
    )
    calls = []

    def _fake_run(exe, *args):
        calls.append((exe, args))
        if args[1] == "silent_connection":
            raise vpn_client.VpnClientError("no se pudo lanzar")

    monkeypatch.setattr(vpn_client, "_run", _fake_run)
    vpn_client.connect(Path(r"C:\data\es.ovpn"), "es")
    assert calls[-1] == (
        Path(r"C:\OpenVPN\bin\openvpn-gui.exe"), ("--command", "connect", "es"),
    )


def test_grant_config_dir_access_false_when_uac_cancelled(monkeypatch, tmp_path):
    monkeypatch.setattr(vpn_client, "find_config_dir", lambda: tmp_path / "config")
    monkeypatch.setattr(vpn_client, "_run_elevated", lambda file, parameters: None)
    assert vpn_client.grant_config_dir_access() is False
