from pathlib import Path

import pytest

from core import vpn_client


def test_status_true_when_service_running(monkeypatch):
    monkeypatch.setattr(
        vpn_client.subprocess, "check_output",
        lambda *a, **k: "SERVICE_NAME: WireGuardTunnel$es\n        STATE : 4  RUNNING\n",
    )
    assert vpn_client.status("es") is True


def test_status_false_when_service_stopped(monkeypatch):
    monkeypatch.setattr(
        vpn_client.subprocess, "check_output",
        lambda *a, **k: "SERVICE_NAME: WireGuardTunnel$es\n        STATE : 1  STOPPED\n",
    )
    assert vpn_client.status("es") is False


def test_status_false_when_service_does_not_exist(monkeypatch):
    def _raise(*a, **k):
        raise Exception("service does not exist")
    monkeypatch.setattr(vpn_client.subprocess, "check_output", _raise)
    assert vpn_client.status("es") is False


def test_connect_raises_when_wireguard_not_installed(monkeypatch):
    monkeypatch.setattr(vpn_client, "find_wireguard_exe", lambda: None)
    with pytest.raises(vpn_client.VpnClientError, match="no está instalado"):
        vpn_client.connect(Path("es.conf"), "es")


def test_disconnect_raises_when_wireguard_not_installed(monkeypatch):
    monkeypatch.setattr(vpn_client, "find_wireguard_exe", lambda: None)
    with pytest.raises(vpn_client.VpnClientError, match="no está instalado"):
        vpn_client.disconnect("es")


def test_connect_runs_installtunnelservice_with_conf_path(monkeypatch):
    monkeypatch.setattr(vpn_client, "find_wireguard_exe", lambda: Path(r"C:\WireGuard\wireguard.exe"))
    calls = []
    monkeypatch.setattr(vpn_client, "_run_elevated", lambda exe, args: calls.append((exe, args)))
    vpn_client.connect(Path(r"C:\data\es.conf"), "es")
    assert calls == [(Path(r"C:\WireGuard\wireguard.exe"), '/installtunnelservice "C:\\data\\es.conf"')]


def test_disconnect_runs_uninstalltunnelservice_with_tunnel_name(monkeypatch):
    monkeypatch.setattr(vpn_client, "find_wireguard_exe", lambda: Path(r"C:\WireGuard\wireguard.exe"))
    calls = []
    monkeypatch.setattr(vpn_client, "_run_elevated", lambda exe, args: calls.append((exe, args)))
    vpn_client.disconnect("es")
    assert calls == [(Path(r"C:\WireGuard\wireguard.exe"), "/uninstalltunnelservice es")]


def test_run_elevated_raises_on_cancelled_uac(monkeypatch):
    monkeypatch.setattr(vpn_client.ctypes.windll.shell32, "ShellExecuteExW", lambda info: False)
    monkeypatch.setattr(vpn_client.ctypes, "GetLastError", lambda: vpn_client._ERROR_CANCELLED)
    with pytest.raises(vpn_client.VpnClientError, match="canceló"):
        vpn_client._run_elevated(Path(r"C:\WireGuard\wireguard.exe"), "/installtunnelservice x")


def test_find_wireguard_exe_prefers_standard_install_path(monkeypatch, tmp_path):
    program_files = tmp_path / "Program Files"
    wg = program_files / "WireGuard" / "wireguard.exe"
    wg.parent.mkdir(parents=True)
    wg.write_bytes(b"")
    monkeypatch.setenv("ProgramFiles", str(program_files))
    assert vpn_client.find_wireguard_exe() == wg


def test_find_wireguard_exe_falls_back_to_path(monkeypatch, tmp_path):
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "no_wireguard_here"))
    monkeypatch.setattr(vpn_client.shutil, "which", lambda name: r"C:\Tools\wireguard.exe")
    assert vpn_client.find_wireguard_exe() == Path(r"C:\Tools\wireguard.exe")


def test_find_wireguard_exe_none_when_not_found(monkeypatch, tmp_path):
    monkeypatch.setenv("ProgramFiles", str(tmp_path / "no_wireguard_here"))
    monkeypatch.setattr(vpn_client.shutil, "which", lambda name: None)
    assert vpn_client.find_wireguard_exe() is None
