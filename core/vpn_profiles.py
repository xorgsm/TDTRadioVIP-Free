"""
Perfiles VPN (WireGuard) del perfil activo de la app.

Cada perfil VPN es un .conf de WireGuard que el usuario importa desde su
propia suscripción -- la app no opera servidores VPN propios, solo guarda
el archivo y arranca/para el túnel correspondiente (ver
core/vpn_client.py). Sirve para acceder a listas públicas de TV/radio con
restricción geográfica, conectando a un servidor del país de la lista.

Igual que core/soulseek_account.py: JSON plano en la carpeta de datos del
PERFIL activo (get_profile_data_dir()), mismo nivel de protección que el
resto de datos de perfil ya existentes en el proyecto -- no es una
regresión guardar aquí la clave privada que trae el .conf.

Coder By X@R
"""
import re
import shutil
from pathlib import Path
from typing import Optional

from core.config import get_profile_data_dir
from core.json_store import read_json, write_json_atomic

VPN_DIR_NAME = "vpn"
INDEX_FILE = "vpn_profiles.json"
# Límite de WireGuard para el nombre del adaptador/servicio del túnel.
_MAX_TUNNEL_LEN = 32


class VpnProfileError(Exception):
    """Perfil VPN inválido, duplicado, o archivo .conf no legible."""


def _vpn_dir(profile: Optional[str] = None) -> Path:
    return get_profile_data_dir(profile) / VPN_DIR_NAME


def _index_path(profile: Optional[str] = None) -> Path:
    return _vpn_dir(profile) / INDEX_FILE


def _load_index(profile: Optional[str] = None) -> dict:
    data = read_json(_index_path(profile), {})
    return data if isinstance(data, dict) else {}


def _save_index(index: dict, profile: Optional[str] = None) -> None:
    write_json_atomic(_index_path(profile), index, indent=2)


def _sanitize_tunnel_name(display_name: str, taken: set) -> str:
    """Deriva un nombre de túnel válido para WireGuard a partir del nombre
    que ve el usuario: solo alfanuméricos, "-" y "_", máximo 32
    caracteres, y único frente a `taken` (sufijo numérico si colisiona)."""
    base = re.sub(r"[^A-Za-z0-9_-]+", "_", display_name).strip("_") or "vpn"
    base = base[:_MAX_TUNNEL_LEN]
    candidate = base
    suffix = 1
    while candidate in taken:
        suffix_str = f"_{suffix}"
        candidate = base[: _MAX_TUNNEL_LEN - len(suffix_str)] + suffix_str
        suffix += 1
    return candidate


def list_profiles(profile: Optional[str] = None) -> list:
    """[{"name", "tunnel", "conf_path"}, ...] ordenados por nombre."""
    index = _load_index(profile)
    vpn_dir = _vpn_dir(profile)
    result = []
    for name, entry in index.items():
        tunnel = entry.get("tunnel") if isinstance(entry, dict) else None
        if not tunnel:
            continue
        result.append({
            "name": name,
            "tunnel": tunnel,
            "conf_path": str(vpn_dir / f"{tunnel}.conf"),
        })
    result.sort(key=lambda item: item["name"].casefold())
    return result


def get_profile(name: str, profile: Optional[str] = None) -> Optional[dict]:
    for entry in list_profiles(profile):
        if entry["name"] == name:
            return entry
    return None


def import_profile(display_name: str, source_conf: Path, profile: Optional[str] = None) -> dict:
    """Copia `source_conf` a la carpeta VPN del perfil y lo registra bajo
    `display_name`. Lanza VpnProfileError si el nombre ya existe, el
    archivo de origen no existe, o no es un .conf de WireGuard legible."""
    display_name = display_name.strip()
    if not display_name:
        raise VpnProfileError("El perfil necesita un nombre.")

    index = _load_index(profile)
    if display_name in index:
        raise VpnProfileError(f"Ya existe un perfil VPN llamado «{display_name}».")

    source_conf = Path(source_conf)
    if not source_conf.is_file():
        raise VpnProfileError(f"No se encuentra el archivo: {source_conf}")
    try:
        text = source_conf.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise VpnProfileError(f"No se pudo leer «{source_conf.name}»: {exc}") from exc
    if "[Interface]" not in text or "[Peer]" not in text:
        raise VpnProfileError(
            f"«{source_conf.name}» no parece un archivo de configuración de WireGuard "
            "válido (faltan las secciones [Interface] o [Peer])."
        )

    taken = {entry.get("tunnel") for entry in index.values() if isinstance(entry, dict)}
    tunnel = _sanitize_tunnel_name(display_name, taken)

    vpn_dir = _vpn_dir(profile)
    vpn_dir.mkdir(parents=True, exist_ok=True)
    dest = vpn_dir / f"{tunnel}.conf"
    try:
        shutil.copy2(source_conf, dest)
    except OSError as exc:
        raise VpnProfileError(f"No se pudo copiar el archivo: {exc}") from exc

    index[display_name] = {"tunnel": tunnel}
    _save_index(index, profile)
    return {"name": display_name, "tunnel": tunnel, "conf_path": str(dest)}


def delete_profile(name: str, profile: Optional[str] = None) -> None:
    """Quita el perfil del índice y borra su .conf. No toca el servicio
    de Windows del túnel si estuviera en marcha -- quien llama debe
    desconectarlo antes con core.vpn_client.disconnect() si procede."""
    index = _load_index(profile)
    entry = index.pop(name, None)
    if entry is None:
        return
    tunnel = entry.get("tunnel") if isinstance(entry, dict) else None
    if tunnel:
        conf = _vpn_dir(profile) / f"{tunnel}.conf"
        conf.unlink(missing_ok=True)
    _save_index(index, profile)
