"""
Control del túnel WireGuard para la VPN de la edición VIP.

wireguard.exe es el cliente oficial de WireGuard para Windows. Instalar o
quitar un túnel como servicio (`/installtunnelservice`,
`/uninstalltunnelservice`) requiere privilegios de administrador -- el
propio cliente gráfico de WireGuard pide elevación para lo mismo, así que
esto no es una limitación añadida por esta app. Se lanza con
ShellExecuteExW y el verbo "runas" para que Windows muestre el UAC;
consultar el estado del túnel (`sc query`) no necesita elevación.

Solo Windows -- la app entera se distribuye solo para Windows (ver
PRODUCT.md).

Coder By X@R
"""
import ctypes
import os
import shutil
import subprocess
from ctypes import wintypes
from pathlib import Path
from typing import Optional

from core.logger import get_logger

log = get_logger(__name__)

_CREATE_NO_WINDOW = 0x08000000
_ERROR_CANCELLED = 1223
_SEE_MASK_NOCLOSEPROCESS = 0x00000040
_SW_HIDE = 0
_INFINITE = 0xFFFFFFFF


class VpnClientError(Exception):
    """Fallo al hablar con wireguard.exe o con el servicio del túnel."""


def find_wireguard_exe() -> Optional[Path]:
    """Ruta a wireguard.exe, o None si no está instalado.

    Primero la ruta estándar de instalación (el instalador oficial de
    WireGuard no añade el ejecutable al PATH), y el PATH como alternativa
    por si el usuario lo puso a mano.
    """
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    standard = Path(program_files) / "WireGuard" / "wireguard.exe"
    if standard.is_file():
        return standard
    found = shutil.which("wireguard.exe")
    return Path(found) if found else None


def is_wireguard_installed() -> bool:
    return find_wireguard_exe() is not None


def _tunnel_service_name(tunnel: str) -> str:
    return f"WireGuardTunnel${tunnel}"


class _ShellExecuteInfo(ctypes.Structure):
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
        ("hKeyClass", wintypes.HKEY),
        ("dwHotKey", wintypes.DWORD),
        ("hIconOrMonitor", wintypes.HANDLE),
        ("hProcess", wintypes.HANDLE),
    ]


def _run_elevated(exe: Path, args: str) -> None:
    """Lanza `exe args` elevado (UAC) y espera a que termine.

    Traduce tanto la cancelación del UAC como un código de salida
    distinto de 0 en VpnClientError -- conectar/desconectar sin avisar
    del motivo dejaría al usuario sin saber si tiene que reintentar o
    revisar el .conf importado.
    """
    info = _ShellExecuteInfo()
    info.cbSize = ctypes.sizeof(_ShellExecuteInfo)
    info.fMask = _SEE_MASK_NOCLOSEPROCESS
    info.hwnd = None
    info.lpVerb = "runas"
    info.lpFile = str(exe)
    info.lpParameters = args
    info.lpDirectory = None
    info.nShow = _SW_HIDE
    info.hInstApp = None

    if not ctypes.windll.shell32.ShellExecuteExW(ctypes.byref(info)):
        error = ctypes.GetLastError()
        if error == _ERROR_CANCELLED:
            raise VpnClientError(
                "Windows canceló la operación: se rechazó el permiso de administrador."
            )
        raise VpnClientError(f"No se pudo lanzar wireguard.exe (error {error}).")

    if not info.hProcess:
        return
    try:
        ctypes.windll.kernel32.WaitForSingleObject(info.hProcess, _INFINITE)
        exit_code = wintypes.DWORD()
        ctypes.windll.kernel32.GetExitCodeProcess(info.hProcess, ctypes.byref(exit_code))
        if exit_code.value != 0:
            raise VpnClientError(f"wireguard.exe terminó con error (código {exit_code.value}).")
    finally:
        ctypes.windll.kernel32.CloseHandle(info.hProcess)


def connect(conf_path: Path, tunnel: str) -> None:
    """Instala y arranca el túnel `tunnel` a partir de `conf_path`."""
    exe = find_wireguard_exe()
    if exe is None:
        raise VpnClientError("WireGuard no está instalado en este PC.")
    _run_elevated(exe, f'/installtunnelservice "{conf_path}"')


def disconnect(tunnel: str) -> None:
    """Para y desinstala el servicio del túnel `tunnel`."""
    exe = find_wireguard_exe()
    if exe is None:
        raise VpnClientError("WireGuard no está instalado en este PC.")
    _run_elevated(exe, f"/uninstalltunnelservice {tunnel}")


def status(tunnel: str) -> bool:
    """True si el servicio del túnel existe y está en marcha.

    `sc query` no necesita elevación (a diferencia de instalar/quitar el
    túnel), así que el estado se puede refrescar sin lanzar ningún UAC.
    """
    try:
        out = subprocess.check_output(
            ["sc", "query", _tunnel_service_name(tunnel)],
            stderr=subprocess.DEVNULL,
            creationflags=_CREATE_NO_WINDOW,
            timeout=3,
            text=True,
        )
    except Exception:
        log.warning("No se pudo consultar el estado del túnel %s", tunnel, exc_info=True)
        return False
    return "RUNNING" in out
