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


def test_connect_kills_orphaned_process_when_connect_command_times_out(monkeypatch):
    """Reproduce el bug real: un servidor VPNGate inalcanzable hace que
    "--command connect" no responda a tiempo -- el timeout de _run()
    solo mata nuestra llamada a openvpn-gui.exe, no el proceso
    openvpn.exe real que el servicio interactivo ya había arrancado, así
    que hay que matarlo aparte para no dejarlo huérfano (comprobado con
    un usuario real: dos procesos openvpn.exe acumulados tras dos
    intentos fallidos contra el mismo servidor)."""
    monkeypatch.setattr(
        vpn_client, "find_openvpn_gui_exe", lambda: Path(r"C:\OpenVPN\bin\openvpn-gui.exe")
    )

    def _fake_run(exe, *args):
        if args[1] == "connect":
            raise vpn_client.VpnClientError("timed out after 10.0 seconds")

    monkeypatch.setattr(vpn_client, "_run", _fake_run)
    kill_calls = []
    monkeypatch.setattr(
        vpn_client, "_kill_orphaned_tunnel_process", lambda tunnel: kill_calls.append(tunnel)
    )
    with pytest.raises(vpn_client.VpnClientError, match="timed out"):
        vpn_client.connect(Path(r"C:\data\mx.ovpn"), "Mexico_VPNGate")
    assert kill_calls == ["Mexico_VPNGate"]


def test_connect_does_not_kill_process_when_connect_succeeds(monkeypatch):
    monkeypatch.setattr(
        vpn_client, "find_openvpn_gui_exe", lambda: Path(r"C:\OpenVPN\bin\openvpn-gui.exe")
    )
    monkeypatch.setattr(vpn_client, "_run", lambda exe, *args: None)
    kill_calls = []
    monkeypatch.setattr(
        vpn_client, "_kill_orphaned_tunnel_process", lambda tunnel: kill_calls.append(tunnel)
    )
    vpn_client.connect(Path(r"C:\data\es.ovpn"), "es")
    assert kill_calls == []


def test_disconnect_runs_command_disconnect_with_tunnel_name(monkeypatch):
    monkeypatch.setattr(
        vpn_client, "find_openvpn_gui_exe", lambda: Path(r"C:\OpenVPN\bin\openvpn-gui.exe")
    )
    calls = []
    monkeypatch.setattr(vpn_client, "_run", lambda exe, *args: calls.append((exe, args)))
    monkeypatch.setattr(vpn_client, "_is_tunnel_process_running", lambda tunnel: False)
    vpn_client.disconnect("es")
    assert calls == [(Path(r"C:\OpenVPN\bin\openvpn-gui.exe"), ("--command", "disconnect", "es"))]


def test_disconnect_does_not_kill_when_process_already_gone(monkeypatch):
    monkeypatch.setattr(
        vpn_client, "find_openvpn_gui_exe", lambda: Path(r"C:\OpenVPN\bin\openvpn-gui.exe")
    )
    monkeypatch.setattr(vpn_client, "_run", lambda exe, *args: None)
    monkeypatch.setattr(vpn_client, "_is_tunnel_process_running", lambda tunnel: False)
    kill_calls = []
    monkeypatch.setattr(
        vpn_client, "_kill_orphaned_tunnel_process", lambda tunnel: kill_calls.append(tunnel)
    )
    vpn_client.disconnect("es")
    assert kill_calls == []


def test_disconnect_kills_process_if_still_running_after_verify_attempts(monkeypatch):
    """Reproduce el bug real: el proceso openvpn.exe seguía vivo (atrapado
    en su propio ciclo de reconexión) después de pedirle la desconexión
    a openvpn-gui.exe -- "Desconectar" debe garantizar que el túnel
    muere, no solo intentarlo."""
    monkeypatch.setattr(
        vpn_client, "find_openvpn_gui_exe", lambda: Path(r"C:\OpenVPN\bin\openvpn-gui.exe")
    )
    monkeypatch.setattr(vpn_client, "_run", lambda exe, *args: None)
    monkeypatch.setattr(vpn_client, "_is_tunnel_process_running", lambda tunnel: True)
    monkeypatch.setattr(vpn_client.time, "sleep", lambda seconds: None)
    kill_calls = []
    monkeypatch.setattr(
        vpn_client, "_kill_orphaned_tunnel_process", lambda tunnel: kill_calls.append(tunnel)
    )
    vpn_client.disconnect("Japan_VPNGate")
    assert kill_calls == ["Japan_VPNGate"]


def test_disconnect_kills_process_even_when_disconnect_command_times_out(monkeypatch):
    monkeypatch.setattr(
        vpn_client, "find_openvpn_gui_exe", lambda: Path(r"C:\OpenVPN\bin\openvpn-gui.exe")
    )

    def _raise(exe, *args):
        raise vpn_client.VpnClientError("timed out after 10.0 seconds")

    monkeypatch.setattr(vpn_client, "_run", _raise)
    monkeypatch.setattr(vpn_client, "_is_tunnel_process_running", lambda tunnel: True)
    monkeypatch.setattr(vpn_client.time, "sleep", lambda seconds: None)
    kill_calls = []
    monkeypatch.setattr(
        vpn_client, "_kill_orphaned_tunnel_process", lambda tunnel: kill_calls.append(tunnel)
    )
    vpn_client.disconnect("es")  # no debe lanzar
    assert kill_calls == ["es"]


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
    monkeypatch.setattr(vpn_client, "_is_tunnel_process_running", lambda tunnel: True)
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
    monkeypatch.setattr(vpn_client, "_is_tunnel_process_running", lambda tunnel: True)
    assert vpn_client.status("es") is True


def test_status_false_when_log_says_connected_but_no_process_running(monkeypatch, tmp_path):
    """Reproduce el bug real: el túnel murió sin un cierre limpio (corte
    de red, suspensión del PC...) y el log se quedó con "Initialization
    Sequence Completed" como último evento para siempre, sin ningún
    SIGTERM/process exiting -- sin el chequeo de proceso vivo, status()
    reportaría "conectado" de forma indefinida (comprobado con un
    usuario real: la VPN aparecía siempre conectada al arrancar la app
    y el botón "Desconectar" no tenía ningún efecto)."""
    (tmp_path / "es.log").write_text(
        "Initialization Sequence Completed\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(vpn_client, "find_log_dir", lambda: tmp_path)
    monkeypatch.setattr(vpn_client, "_is_tunnel_process_running", lambda tunnel: False)
    assert vpn_client.status("es") is False


def test_status_passes_the_right_tunnel_to_the_process_check(monkeypatch, tmp_path):
    (tmp_path / "es.log").write_text("Initialization Sequence Completed\n", encoding="utf-8")
    monkeypatch.setattr(vpn_client, "find_log_dir", lambda: tmp_path)
    seen = []
    monkeypatch.setattr(
        vpn_client, "_is_tunnel_process_running", lambda tunnel: seen.append(tunnel) or True
    )
    vpn_client.status("es")
    assert seen == ["es"]


def test_is_tunnel_process_running_true_when_command_line_matches_tunnel(monkeypatch):
    class _FakeResult:
        stdout = (
            'openvpn --log "log\\Japan_VPNGate.log" --config "Japan_VPNGate.ovpn" --service x\r\n'
        )

    monkeypatch.setattr(vpn_client.subprocess, "run", lambda *args, **kwargs: _FakeResult())
    assert vpn_client._is_tunnel_process_running("Japan_VPNGate") is True


def test_is_tunnel_process_running_false_when_only_a_different_tunnel_matches(monkeypatch):
    """Reproduce el bug real: un intento fallido de conexión a un
    servidor VPNGate inalcanzable dejó procesos openvpn.exe huérfanos de
    un túnel distinto corriendo a la vez que otro túnel sí estaba
    conectado -- sin distinguir por línea de comandos, el estado de un
    túnel muerto (p.ej. "Mexico_VPNGate") heredaba el "conectado" del
    huérfano de otro túnel completamente distinto (p.ej.
    "Japan_VPNGate")."""

    class _FakeResult:
        stdout = (
            'openvpn --log "log\\Japan_VPNGate.log" --config "Japan_VPNGate.ovpn" --service x\r\n'
        )

    monkeypatch.setattr(vpn_client.subprocess, "run", lambda *args, **kwargs: _FakeResult())
    assert vpn_client._is_tunnel_process_running("Mexico_VPNGate") is False


def test_is_tunnel_process_running_false_when_no_process_running(monkeypatch):
    class _FakeResult:
        stdout = ""

    monkeypatch.setattr(vpn_client.subprocess, "run", lambda *args, **kwargs: _FakeResult())
    assert vpn_client._is_tunnel_process_running("es") is False


def test_is_tunnel_process_running_true_when_query_fails(monkeypatch):
    """Fail-safe: si la consulta de procesos no se puede ejecutar, no se
    debe negar un estado "conectado" que solo se puede confirmar por el
    log -- mejor un falso "conectado" ocasional que romper el
    comportamiento anterior cuando este chequeo adicional no es
    fiable."""

    def _raise(*args, **kwargs):
        raise OSError("powershell no encontrado")

    monkeypatch.setattr(vpn_client.subprocess, "run", _raise)
    assert vpn_client._is_tunnel_process_running("es") is True


def test_kill_orphaned_tunnel_process_targets_the_right_tunnel(monkeypatch):
    monkeypatch.setattr(vpn_client, "find_log_dir", lambda: Path("."))
    calls = []
    monkeypatch.setattr(
        vpn_client.subprocess, "run",
        lambda args, **kwargs: calls.append(args) or None,
    )
    vpn_client._kill_orphaned_tunnel_process("Mexico_VPNGate")
    [args] = calls
    assert "Mexico_VPNGate.ovpn" in args[-1]


def test_kill_orphaned_tunnel_process_swallows_failures(monkeypatch):
    def _raise(*args, **kwargs):
        raise OSError("powershell no encontrado")

    monkeypatch.setattr(vpn_client.subprocess, "run", _raise)
    vpn_client._kill_orphaned_tunnel_process("es")  # no debe lanzar


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
