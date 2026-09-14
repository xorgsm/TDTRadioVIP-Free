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
import os
import shutil
import subprocess
import winreg
from pathlib import Path
from typing import Optional

from core.logger import get_logger

log = get_logger(__name__)

_CREATE_NO_WINDOW = 0x08000000
_DEFAULT_CONFIG_DIRNAME = "config"
_CONNECTED_MARKER = "Initialization Sequence Completed"
_DISCONNECTED_MARKERS = ("SIGTERM", "process exiting")


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
    perfil conectado -- hermana de find_config_dir() en una instalación
    estándar de OpenVPN."""
    return find_config_dir().parent / "log"


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
    except OSError as exc:
        raise VpnClientError(f"No se pudo lanzar openvpn-gui.exe: {exc}") from exc


def connect(conf_path: Path, tunnel: str) -> None:
    """Pide a openvpn-gui.exe que conecte el perfil `tunnel`.

    El .ovpn ya debe estar copiado en find_config_dir() con ese nombre
    -- lo hace core/vpn_profiles.import_profile() al importar el perfil.
    `conf_path` no se usa para construir el comando (OpenVPN conecta por
    nombre, no por ruta), se mantiene en la firma para no romper a quien
    ya llama a connect() igual que con el wireguard.exe anterior.
    """
    exe = find_openvpn_gui_exe()
    if exe is None:
        raise VpnClientError("OpenVPN no está instalado en este PC.")
    _run(exe, "--command", "connect", tunnel)


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


def status(tunnel: str) -> bool:
    """True si el túnel `tunnel` está conectado ahora mismo.

    openvpn-gui no expone un comando de solo-lectura por CLI, así que se
    lee el log que el servicio interactivo mantiene por perfil, buscando
    si la última aparición de "Initialization Sequence Completed" es más
    reciente que la última desconexión -- si el log no existe todavía
    (nunca se ha conectado ese perfil), se considera desconectado.
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
    return last_connected > last_disconnected
