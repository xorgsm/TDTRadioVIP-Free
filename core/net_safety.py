"""Comprobaciones de destino para peticiones HTTP que salen de la app.

Una URL pública puede redirigir (o resolver por DNS) a servicios que no
deberían ser alcanzables desde un enlace externo: el propio equipo
(loopback), los metadatos de la nube (169.254.169.254) o la red local.
Estas funciones deciden si un host es aceptable *después* de resolverlo.

Coder By X@R
"""
import ipaddress
import re
import socket
from urllib.parse import urlsplit

from core.logger import get_logger

log = get_logger(__name__)

# Rangos que no son "globales" para Python pero que VPN y proxies en modo
# fake-IP (Clash, v2ray, Surge...) devuelven para hosts públicos.
_VPN_FAKE_IP_NETWORKS = (
    ipaddress.ip_network("100.64.0.0/10"),
    ipaddress.ip_network("198.18.0.0/15"),
)


# Esquemas que libVLC puede reproducir como emision. Todo lo demas (file:,
# smb:, ftp:, screen:, dshow:, fd:...) lo puede traer una lista M3U hostil
# para que el reproductor abra recursos que no son una emision.
PLAYABLE_STREAM_SCHEMES = frozenset({
    "http", "https", "rtsp", "rtsps", "rtmp", "rtmps", "rtp", "udp",
    "mms", "mmsh", "mmst",
})
_LOCAL_DRIVE_PATH = re.compile(r"^[A-Za-z]:[\\/]")


def _ip_is_never_allowed(ip: ipaddress._BaseAddress) -> bool:
    """Loopback, link-local (metadatos cloud), sin especificar, multicast,
    reservadas. La red local privada (RFC 1918) no entra aquí a propósito:
    hay usos legítimos (un servidor DLNA o Plex en casa)."""
    return (
        ip.is_loopback or ip.is_link_local or ip.is_unspecified
        or ip.is_multicast or ip.is_reserved
    )


def _resolve(host: str) -> list:
    infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    return [ipaddress.ip_address(info[4][0].split("%")[0]) for info in infos]


def host_is_reachable_target(host: str, *, allow_private: bool) -> bool:
    """True si ninguna dirección a la que resuelve `host` está prohibida.

    Con `allow_private=False` (actualizaciones) tampoco se admiten las
    redes privadas. Un host que no resuelve se rechaza.
    """
    try:
        addresses = _resolve(host)
    except (OSError, ValueError):
        return False
    if not addresses:
        return False
    for ip in addresses:
        if _ip_is_never_allowed(ip):
            log.warning("Destino rechazado: %s resuelve a %s", host, ip)
            return False
        if allow_private or ip.is_global:
            continue
        if any(ip in network for network in _VPN_FAKE_IP_NETWORKS):
            continue
        log.warning("Destino rechazado (red privada): %s resuelve a %s", host, ip)
        return False
    return True


def is_safe_https_url(url: object, *, allow_private: bool = False) -> bool:
    """HTTPS absoluto cuyo host resuelve solo a destinos permitidos."""
    try:
        parts = urlsplit(str(url or "").strip())
        host = parts.hostname
    except (TypeError, ValueError):
        return False
    if parts.scheme.lower() != "https" or not host:
        return False
    return host_is_reachable_target(host, allow_private=allow_private)


def is_safe_download_url(url: object) -> bool:
    """http(s) con host, sin apuntar al propio equipo ni a metadatos de
    nube. Admite la red local: el descargador se usa también con servidores
    de casa."""
    try:
        parts = urlsplit(str(url or "").strip())
        host = parts.hostname
    except (TypeError, ValueError):
        return False
    if parts.scheme.lower() not in ("http", "https") or not host:
        return False
    return host_is_reachable_target(host, allow_private=True)


def is_playable_stream_url(url: object) -> bool:
    """True si `url` es una emision que el reproductor puede abrir: un esquema
    de streaming conocido o una ruta local con letra de unidad.

    Se rechazan las rutas UNC (con barras invertidas o dobles barras
    iniciales) y `smb:`: Windows enviaria el hash NTLM del usuario al host
    de la lista.
    """
    if not isinstance(url, str):
        return False
    text = url.strip()
    if not text or text.startswith(("\\\\", "//")):
        return False
    if _LOCAL_DRIVE_PATH.match(text):
        return True
    try:
        scheme = urlsplit(text).scheme.lower()
    except ValueError:
        return False
    return scheme in PLAYABLE_STREAM_SCHEMES
