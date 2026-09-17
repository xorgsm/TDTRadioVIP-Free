"""
Control de la conexión OpenVPN para la VPN de la edición VIP.

openvpn-gui.exe es el cliente gráfico oficial y gratuito de OpenVPN para
Windows. Desde la versión 2.4 se apoya en el "OpenVPN Interactive
Service": un servicio de Windows que se instala una sola vez, con
privilegios de administrador, durante la instalación de OpenVPN -- no lo
instala ni lo eleva esta app. A partir de ahí, cualquier usuario que
pertenezca al grupo local de Windows "OpenVPN Administrators" puede
conectar y desconectar sin que aparezca ningún UAC, pilotando
openvpn-gui.exe por línea de comandos (`--command connect <nombre>` /
`--command disconnect <nombre>`). Es justo lo contrario del
comportamiento que tenía aquí wireguard.exe (pedía UAC en cada conexión
porque instalaba/quitaba un servicio por túnel cada vez) -- ver
docs/superpowers/specs/2026-09-11-vpn-client-design.md.

`connect()`/`disconnect()` son fire-and-forget: openvpn-gui.exe recibe el
comando y se lo pasa al servicio interactivo, pero no hay forma de
bloquear hasta que el túnel termine de levantarse (limitación conocida,
documentada en el spec). `status()` tampoco tiene un comando de
solo-lectura por CLI (ver
https://github.com/OpenVPN/openvpn-gui/issues/104), así que lee el log
por perfil que ya escribe el servicio interactivo.

Solo Windows -- la app entera se distribuye solo para Windows (ver
PRODUCT.md).

Coder By X@R
"""
import ctypes
import os
import shutil
import subprocess
import winreg
from ctypes import wintypes
from pathlib import Path
from typing import Optional

from core.logger import get_logger

log = get_logger(__name__)

_CREATE_NO_WINDOW = 0x08000000
_DEFAULT_CONFIG_DIRNAME = "config"
_CONNECTED_MARKER = "Initialization Sequence Completed"
_DISCONNECTED_MARKERS = ("SIGTERM", "process exiting")
_SW_HIDE = 0
_SEE_MASK_NOCLOSEPROCESS = 0x00000040
_INFINITE = 0xFFFFFFFF


class _ShellExecuteInfoW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("fMask", ctypes.c_ulong),
        ("hwnd", wintypes.HWND),
        ("lpVerb", wintypes.LPCWSTR),
        ("lpFile", wintypes.LPCWSTR),
        ("lpParameters", wintypes.LPCWSTR),
        ("lpDirectory", wintypes.LPCWSTR),
        ("nShow", ctypes.c_int),
        ("hInstApp", wintypes.HINSTANCE),
        ("lpIDList", ctypes.c_void_p),
        ("lpClass", wintypes.LPCWSTR),
        ("hKeyClass", wintypes.HANDLE),
        ("dwHotKey", wintypes.DWORD),
        ("hIcon", wintypes.HANDLE),
        ("hProcess", wintypes.HANDLE),
    ]


class VpnClientError(Exception):
    """Fallo al hablar con openvpn-gui.exe o con el servicio interactivo."""


def find_openvpn_gui_exe() -> Optional[Path]:
    """Ruta a openvpn-gui.exe, o None si OpenVPN no está instalado.

    Primero la ruta estándar de instalación (el instalador oficial de
    OpenVPN no siempre añade el ejecutable al PATH), y el PATH como
    alternativa por si el usuario lo puso a mano.
    """
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    standard = Path(program_files) / "OpenVPN" / "bin" / "openvpn-gui.exe"
    if standard.is_file():
        return standard
    found = shutil.which("openvpn-gui.exe")
    return Path(found) if found else None


def is_openvpn_installed() -> bool:
    return find_openvpn_gui_exe() is not None


def find_config_dir() -> Path:
    """Carpeta que vigila el servicio interactivo de OpenVPN en busca de
    archivos .ovpn -- ahí hay que copiar cada perfil (ver
    core/vpn_profiles.py) para que `--command connect <nombre>` lo
    encuentre por nombre.

    openvpn-gui.exe guarda esta ruta en el registro porque cambia entre
    instalaciones y versiones; si esa clave no existe (instalación muy
    antigua o no estándar), se usa la ruta por defecto del instalador
    oficial junto al propio ejecutable.
    """
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\OpenVPN-GUI") as key:
            value, _ = winreg.QueryValueEx(key, "config_dir")
            if value:
                return Path(value)
    except OSError:
        pass
    exe = find_openvpn_gui_exe()
    base = (
        exe.parent.parent
        if exe is not None
        else Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "OpenVPN"
    )
    return base / _DEFAULT_CONFIG_DIRNAME


def find_log_dir() -> Path:
    """Carpeta donde el servicio interactivo escribe el log de cada
    perfil conectado.

    NO es una carpeta hermana de find_config_dir() -- comprobado en una
    instalación real (OpenVPN GUI 11.66.0.0 / OpenVPN 2.7.7): el config
    puede vivir en la carpeta global (`Program Files\\OpenVPN\\config`,
    compartida, ver find_config_dir()) pero el log lo escribe siempre
    openvpn-gui.exe en la carpeta de logs *por usuario* que guarda en el
    registro bajo `HKCU\\SOFTWARE\\OpenVPN-GUI\\log_dir` -- si esa clave
    no existe, su propio valor por defecto (código fuente de
    openvpn-gui, registry.c) es `%USERPROFILE%\\OpenVPN\\log`. Usar
    find_config_dir().parent aquí hacía que status() no encontrase
    nunca el log real y devolviera "desconectado" aunque el túnel
    estuviera activo."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\OpenVPN-GUI") as key:
            value, _ = winreg.QueryValueEx(key, "log_dir")
            if value:
                return Path(os.path.expandvars(value))
    except OSError:
        pass
    return Path(os.path.expandvars(r"%USERPROFILE%\OpenVPN\log"))


def _run_elevated(file: str, parameters: str) -> Optional[int]:
    """Lanza `file parameters` con el verbo "runas" (pide UAC) y espera a
    que termine. Devuelve el código de salida del proceso, o None si el
    usuario canceló el UAC o no se pudo lanzar."""
    info = _ShellExecuteInfoW()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = _SEE_MASK_NOCLOSEPROCESS
    info.lpVerb = "runas"
    info.lpFile = file
    info.lpParameters = parameters
    info.nShow = _SW_HIDE
    if not ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(info)):
        return None
    if not info.hProcess:
        return None
    ctypes.windll.kernel32.WaitForSingleObject(info.hProcess, _INFINITE)
    exit_code = wintypes.DWORD()
    ctypes.windll.kernel32.GetExitCodeProcess(info.hProcess, ctypes.byref(exit_code))
    ctypes.windll.kernel32.CloseHandle(info.hProcess)
    return exit_code.value


def grant_config_dir_access() -> bool:
    """Pide una única elevación (UAC) para dar permiso de escritura al
    grupo "OpenVPN Administrators" sobre find_config_dir(), con
    `icacls /grant`.

    Autoreparación para instalaciones de OpenVPN donde el instalador no
    dejó esa ACL puesta en la carpeta de configs -- pasa aunque el
    usuario ya pertenezca al grupo (el grupo por sí solo no da acceso si
    la carpeta nunca lo concedió). La usa
    core.vpn_profiles._register_with_openvpn() cuando copiar el .ovpn
    falla con PermissionError. Devuelve True si el usuario aceptó el UAC
    e icacls terminó con éxito; False si lo canceló o icacls falló."""
    config_dir = find_config_dir()
    parameters = f'"{config_dir}" /grant "OpenVPN Administrators:(OI)(CI)M"'
    exit_code = _run_elevated("icacls.exe", parameters)
    return exit_code == 0


def _run(exe: Path, *args: str) -> None:
    """Lanza `exe args` sin elevar.

    A diferencia de wireguard.exe, openvpn-gui.exe no necesita
    ShellExecuteExW con "runas": habla con el servicio interactivo (ya
    elevado de antemano, ver el docstring del módulo) por su cuenta.
    """
    try:
        subprocess.run(
            [str(exe), *args],
            creationflags=_CREATE_NO_WINDOW,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        # subprocess.SubprocessError además de OSError: si
        # openvpn-gui.exe no responde en 10s (servicio interactivo
        # ocupado), subprocess.run() lanza TimeoutExpired, que NO
        # hereda de OSError -- sin capturarlo aparte se escapaba sin
        # convertir a VpnClientError, y como esta app no tiene ningún
        # manejador global de excepciones, desaparecía en silencio
        # (comprobado: cortaba a medias
        # AppLifecycle.disconnect_vpn_profiles() al cerrar la app, sin
        # rastro en ningún log ni aviso visible).
        raise VpnClientError(f"No se pudo lanzar openvpn-gui.exe: {exc}") from exc


def connect(conf_path: Path, tunnel: str) -> None:
    """Pide a openvpn-gui.exe que conecte el perfil `tunnel`.

    El .ovpn ya debe estar copiado en find_config_dir() con ese nombre
    -- lo hace core/vpn_profiles.import_profile() al importar el perfil.
    `conf_path` no se usa para construir el comando (OpenVPN conecta por
    nombre, no por ruta), se mantiene en la firma para no romper a quien
    ya llama a connect() igual que con el wireguard.exe anterior.

    Antes de conectar, activa "silent_connection" -- si no,
    openvpn-gui.exe muestra su propia ventana con el log de conexión y
    los botones Desconectar/Reconectar cada vez, y el estado de verdad
    solo se ve ahí en vez de en esta app (ver
    ui.dialogs.settings.SettingsDialog._refresh_vpn_status, que ya lee
    el mismo log y pinta el botón de conectar en verde). Es solo
    cosmético: si falla, no debe impedir el connect real.

    Si el comando "connect" no responde a tiempo (servidor VPNGate
    inalcanzable, comprobado con un usuario real contra un servidor
    caído: el log se queda parado en "Attempting to establish TCP
    connection"), se intenta matar el proceso openvpn.exe huérfano
    antes de propagar el error -- el timeout de _run() solo mata nuestra
    llamada a openvpn-gui.exe, no el proceso openvpn.exe real que ya
    había arrancado el servicio interactivo (son procesos
    independientes); sin esto, cada intento fallido contra un servidor
    caído dejaba un proceso huérfano corriendo para siempre, intentando
    reconectar solo, y varios intentos fallidos consecutivos se iban
    acumulando."""
    exe = find_openvpn_gui_exe()
    if exe is None:
        raise VpnClientError("OpenVPN no está instalado en este PC.")
    try:
        _run(exe, "--command", "silent_connection", "1")
    except VpnClientError:
        pass
    try:
        _run(exe, "--command", "connect", tunnel)
    except VpnClientError:
        _kill_orphaned_tunnel_process(tunnel)
        raise


def disconnect(tunnel: str) -> None:
    exe = find_openvpn_gui_exe()
    if exe is None:
        raise VpnClientError("OpenVPN no está instalado en este PC.")
    _run(exe, "--command", "disconnect", tunnel)


def rescan() -> None:
    """Pide a openvpn-gui.exe que vuelva a mirar su carpeta de configs.

    Hace falta tras copiar un .ovpn nuevo en find_config_dir() para que
    aparezca sin tener que reiniciar el GUI. Si OpenVPN no está
    instalado, no hace nada -- no tiene sentido fallar por esto en medio
    de un import de perfil cuyo error real ya se reporta aparte.
    """
    exe = find_openvpn_gui_exe()
    if exe is None:
        return
    _run(exe, "--command", "rescan")


def _openvpn_process_command_lines() -> Optional[str]:
    """Líneas de comando de todos los procesos openvpn.exe corriendo
    ahora mismo, o None si la consulta falló (entorno restringido,
    PowerShell no disponible...) -- se distingue de "" (consulta
    correcta, ningún proceso) a propósito, para que quien llama decida
    el fallback.

    tasklist no expone la línea de comandos completa sin permisos
    elevados (`/V` solo da el título de ventana), así que se usa
    Get-CimInstance/Win32_Process por PowerShell -- necesario para
    poder distinguir A QUÉ túnel pertenece cada proceso (ver
    _is_tunnel_process_running)."""
    try:
        result = subprocess.run(
            [
                "powershell", "-NoProfile", "-NonInteractive", "-Command",
                "(Get-CimInstance Win32_Process -Filter \"Name='openvpn.exe'\" "
                "-ErrorAction SilentlyContinue).CommandLine",
            ],
            creationflags=_CREATE_NO_WINDOW,
            timeout=10,
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout


def _is_tunnel_process_running(tunnel: str) -> bool:
    """True si hay un proceso openvpn.exe corriendo ahora mismo cuya
    línea de comandos referencia el túnel `tunnel` (busca
    "<tunnel>.ovpn" en `--config "<tunnel>.ovpn"`).

    status() solo mira el log del túnel, pero ese log solo se actualiza
    en eventos puntuales (arranque, cambios de ruta, renegociación TLS
    cada hora) -- si el túnel muere sin un cierre limpio (corte de red,
    suspensión del PC, apagado forzado...) el log se queda con
    "Initialization Sequence Completed" como último evento para siempre,
    y status() reportaría "conectado" de forma indefinida aunque no
    quede ningún proceso real (confirmado con un usuario real: la VPN
    aparecía siempre conectada al arrancar la app, y el botón
    "Desconectar" no tenía ningún efecto porque no había nada que
    desconectar).

    Se distingue por túnel a propósito -- el diseño asume que no hay
    más de un túnel activo a la vez (ver
    docs/superpowers/specs/2026-09-11-vpn-client-design.md), pero en la
    práctica sí pueden coexistir varios procesos openvpn.exe: un
    intento de conexión contra un servidor VPNGate inalcanzable deja un
    proceso huérfano (ver connect()) que puede seguir vivo a la vez que
    otro túnel sí está conectado de verdad. Comprobado con un usuario
    real: sin este chequeo específico, el estado de un túnel muerto
    heredaba el "conectado" del proceso huérfano de otro túnel
    completamente distinto.

    Si la consulta falla (entorno restringido, etc.) se asume True para
    no romper el comportamiento anterior basado solo en el log -- mejor
    un falso "conectado" ocasional que negar el estado real cuando el
    propio chequeo no es fiable.
    """
    command_lines = _openvpn_process_command_lines()
    if command_lines is None:
        return True
    return f"{tunnel}.ovpn".lower() in command_lines.lower()


def _kill_orphaned_tunnel_process(tunnel: str) -> None:
    """Mata cualquier proceso openvpn.exe huérfano para `tunnel`.

    Se llama desde connect() cuando el comando "connect" no responde a
    tiempo -- ver el docstring de connect() para el porqué. Best-effort:
    un fallo aquí (PowerShell no disponible, etc.) no debe ocultar el
    error real de connect() que ya se está propagando."""
    config_name = f"{tunnel}.ovpn"
    command = (
        "Get-CimInstance Win32_Process -Filter \"Name='openvpn.exe'\" "
        f"-ErrorAction SilentlyContinue | Where-Object {{ $_.CommandLine -like '*{config_name}*' }} "
        "| ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            creationflags=_CREATE_NO_WINDOW,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        pass


def status(tunnel: str) -> bool:
    """True si el túnel `tunnel` está conectado ahora mismo.

    openvpn-gui no expone un comando de solo-lectura por CLI, así que se
    lee el log que el servicio interactivo mantiene por perfil, buscando
    si la última aparición de "Initialization Sequence Completed" es más
    reciente que la última desconexión -- si el log no existe todavía
    (nunca se ha conectado ese perfil), se considera desconectado. Si el
    log dice "conectado" se comprueba además que exista un proceso
    openvpn.exe real para *este* túnel (ver _is_tunnel_process_running)
    para no quedarse en un falso "conectado" permanente cuando el túnel
    murió sin dejar rastro de desconexión en el log, ni confundirlo con
    el proceso de otro túnel distinto.
    """
    log_path = find_log_dir() / f"{tunnel}.log"
    try:
        text = log_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    last_connected = text.rfind(_CONNECTED_MARKER)
    if last_connected == -1:
        return False
    last_disconnected = max(text.rfind(marker) for marker in _DISCONNECTED_MARKERS)
    if last_connected <= last_disconnected:
        return False
    return _is_tunnel_process_running(tunnel)
