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


def test_find_log_dir_is_sibling_of_config_dir(monkeypatch):
    monkeypatch.setattr(vpn_client, "find_config_dir", lambda: Path(r"C:\OpenVPN\config"))
    assert vpn_client.find_log_dir() == Path(r"C:\OpenVPN\log")


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
    assert calls == [(Path(r"C:\OpenVPN\bin\openvpn-gui.exe"), ("--command", "connect", "es"))]


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
