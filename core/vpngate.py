"""
Lista de servidores VPN gratuitos de VPNGate (vpngate.net), un proyecto
público de la Universidad de Tsukuba (Japón) que ofrece servidores
OpenVPN mantenidos por voluntarios, sin cuenta ni suscripción -- pensado
justo para esto: acceder a listas públicas de TV/radio con restricción
geográfica sin que el usuario tenga que pagar ni configurar nada aparte.
Ver docs/superpowers/specs/2026-09-14-vpngate-free-servers-design.md.

No sustituye el modelo "trae tu propia VPN" de core/vpn_profiles.py --
lo complementa: aquí se resuelve la lista de servidores gratuitos
disponibles ahora mismo, y el que elija el usuario se importa igual que
cualquier otro .ovpn, con vpn_profiles.import_profile_from_text().

Coder By X@R
"""
import base64
import csv
from typing import List

import requests

from core.logger import get_logger

log = get_logger(__name__)

API_URL = "https://www.vpngate.net/api/iphone/"
_TIMEOUT = 10
_CONFIG_FIELD = "OpenVPN_ConfigData_Base64"


class VpnGateError(Exception):
    """Fallo al descargar o interpretar la lista de servidores de VPNGate."""


def fetch_servers(request_get=requests.get) -> List[dict]:
    """Lista de servidores disponibles ahora mismo en VPNGate, cada uno
    como {"hostname", "ip", "country_long", "country_short", "ping",
    "speed", "score", "ovpn_text"}, ordenada por score descendente (los
    primeros son, según el propio VPNGate, los más rápidos/estables).

    Lanza VpnGateError si no se pudo descargar la lista o el formato no
    es el esperado -- VPNGate cambia constantemente (los servidores son
    PCs de voluntarios encendidos y apagados a su antojo) y no tiene
    sentido devolver una lista parcial en silencio que el usuario no
    sepa que está incompleta."""
    try:
        resp = request_get(API_URL, timeout=_TIMEOUT)
        resp.raise_for_status()
        text = resp.text
    except Exception as exc:
        raise VpnGateError(f"No se pudo descargar la lista de VPNGate: {exc}") from exc
    return _parse_csv(text)


def _parse_csv(text: str) -> List[dict]:
    """El CSV de VPNGate empieza con una línea `*vpn_servers` y una
    cabecera `#Campo1,Campo2,...` -- ninguna de las dos es una fila de
    datos. La última columna (`OpenVPN_ConfigData_Base64`) es el .ovpn
    completo en Base64."""
    lines = [line for line in text.splitlines() if line and not line.startswith("*")]
    if not lines:
        raise VpnGateError("VPNGate devolvió una lista vacía.")

    header = lines[0].lstrip("#").split(",")
    servers = []
    for row in csv.reader(lines[1:]):
        if len(row) != len(header):
            continue
        entry = dict(zip(header, row))
        b64 = entry.get(_CONFIG_FIELD, "")
        if not b64:
            continue
        try:
            ovpn_text = base64.b64decode(b64).decode("utf-8", errors="replace")
        except (ValueError, TypeError):
            continue

        def _to_int(value):
            try:
                return int(value)
            except (TypeError, ValueError):
                return 0

        servers.append({
            "hostname": entry.get("HostName", ""),
            "ip": entry.get("IP", ""),
            "country_long": entry.get("CountryLong", ""),
            "country_short": entry.get("CountryShort", ""),
            "ping": _to_int(entry.get("Ping")),
            "speed": _to_int(entry.get("Speed")),
            "score": _to_int(entry.get("Score")),
            "ovpn_text": ovpn_text,
        })

    servers.sort(key=lambda s: s["score"], reverse=True)
    return servers
