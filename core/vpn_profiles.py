"""
Perfiles VPN (OpenVPN) del perfil activo de la app.

Cada perfil VPN es un .ovpn de OpenVPN de un servidor gratuito de VPNGate
(core/vpngate.py) o importado a mano de otro proveedor gratuito
(bring-your-own, reactivado en 8.6.0 junto a VPNGate) -- la app no opera
servidores VPN propios, solo guarda el archivo y pide a openvpn-gui.exe
que conecte/desconecte el túnel correspondiente (ver core/vpn_client.py).
Sirve para acceder a listas públicas de TV/radio con restricción
geográfica, conectando a un servidor del país de la lista.

Igual que core/soulseek_account.py: JSON plano en la carpeta de datos del
PERFIL activo (get_profile_data_dir()), mismo nivel de protección que el
resto de datos de perfil ya existentes en el proyecto -- no es una
regresión guardar aquí las credenciales que traiga el .ovpn. Ojo: esto
aplica a la copia que vive en la carpeta del perfil; la copia que se
registra con OpenVPN (_register_with_openvpn(), más abajo) vive
necesariamente en una carpeta compartida por toda la máquina, y no
"por perfil" -- ver su propio docstring y el de
vpn_client.restrict_config_file_to_current_user() para el límite real
que queda ahí.

A diferencia de la versión anterior con WireGuard, este módulo ya no es
CRUD puro: OpenVPN conecta los túneles por NOMBRE desde una carpeta que
vigila el servicio interactivo (core.vpn_client.find_config_dir()), no
por ruta explícita, así que import_profile()/delete_profile() también
copian/borran el .ovpn ahí -- ver
docs/superpowers/specs/2026-09-11-vpn-client-design.md.

Coder By X@R
"""
import re
import shutil
from pathlib import Path
from typing import List, Optional, Tuple

from core import vpn_client
from core.config import get_profile_data_dir
from core.json_store import read_json, write_json_atomic
from core.logger import get_logger

log = get_logger(__name__)

VPN_DIR_NAME = "vpn"
INDEX_FILE = "vpn_profiles.json"
# openvpn-gui no documenta un límite estricto para el nombre de un
# perfil, pero se mantiene corto y saneado como con WireGuard antes --
# es también el nombre del archivo .ovpn en la carpeta de configs.
_MAX_TUNNEL_LEN = 32

# Directivas de OpenVPN capaces de ejecutar código o cargar una DLL
# arbitraria (client-connect, plugin...) o de subir el nivel de
# script-security que las habilita. Un .ovpn es, ante todo, texto que
# llega de fuera: los que trae VPNGate (lista pública sin ningún tipo de
# curación de contenido, cualquiera puede anunciar un relay) pasan por
# aquí igual que uno importado a mano. Sin este filtro, un perfil
# malicioso ejecutaría lo que traiga en "up"/"client-connect"/"plugin"
# con los privilegios del servicio interactivo de OpenVPN (ver el
# docstring de _register_with_openvpn) en cuanto el usuario pulsara
# "Conectar" -- la misma clase de fallo que CVEs conocidos en otros
# clientes VPN de consumo.
_DANGEROUS_DIRECTIVES = {
    "up", "down", "up-restart", "route-up", "route-pre-down", "ipchange",
    "client-connect", "client-disconnect", "client-crresponse",
    "tls-verify", "auth-user-pass-verify", "plugin", "script-security",
    # Cargan una DLL, incluyen otro fichero de configuracion, escriben
    # ficheros en rutas arbitrarias o cambian de directorio/raiz.
    "pkcs11-providers", "engine", "config", "log", "log-append", "writepid",
    "status", "cd", "chroot",
}
# Todas las que empiezan por "management" abren la interfaz de gestion.
_DANGEROUS_PREFIXES = ("management",)
# Caracteres que el tokenizador de OpenVPN descarta al leer el nombre de la
# directiva (comillas y barra de escape): `"up"` y `u\p` valen como `up`.
_TOKEN_NOISE = str.maketrans("", "", "\"'\\")


def _directive_name(line: str) -> str:
    """Nombre normalizado de la directiva de una linea de .ovpn.

    OpenVPN admite en ficheros de configuracion el prefijo "--" (`--up`),
    comillas y barras de escape en el nombre; una comparacion exacta contra
    la lista negra se saltaba con cualquiera de ellos.
    """
    token = line.split(None, 1)[0].lower().translate(_TOKEN_NOISE)
    return token.lstrip("-")


def _is_dangerous(directive: str) -> bool:
    return directive in _DANGEROUS_DIRECTIVES or directive.startswith(_DANGEROUS_PREFIXES)


def _strip_dangerous_directives(text: str) -> Tuple[str, List[str]]:
    """Quita del .ovpn cualquier directiva de _DANGEROUS_DIRECTIVES y
    fuerza "script-security 0" al final -- así, aunque algún filtro de
    arriba pase por alto una variante no contemplada, OpenVPN no
    ejecutará ningún script/plugin de todos modos (script-security 0 lo
    desactiva por completo, y es la última ocurrencia de la directiva la
    que OpenVPN respeta). Devuelve (texto_limpio, directivas_quitadas)
    para poder avisar si el .ovpn traía algo peligroso."""
    kept_lines = []
    removed = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(("#", ";")):
            kept_lines.append(line)
            continue
        if _is_dangerous(_directive_name(stripped)):
            removed.append(stripped)
            continue
        kept_lines.append(line)
    kept_lines.append("script-security 0")
    return "\n".join(kept_lines) + "\n", removed


class VpnProfileError(Exception):
    """Perfil VPN inválido, duplicado, o archivo .ovpn no legible."""


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
    """Deriva un nombre de perfil válido para OpenVPN a partir del nombre
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
            "conf_path": str(vpn_dir / f"{tunnel}.ovpn"),
        })
    result.sort(key=lambda item: item["name"].casefold())
    return result


def get_profile(name: str, profile: Optional[str] = None) -> Optional[dict]:
    for entry in list_profiles(profile):
        if entry["name"] == name:
            return entry
    return None


def _register_with_openvpn(dest: Path, tunnel: str) -> None:
    """Copia `dest` a la carpeta que vigila el servicio interactivo de
    OpenVPN, con el nombre de túnel como nombre de archivo, y pide un
    rescan para que openvpn-gui.exe lo reconozca sin reiniciar.

    Puede fallar con PermissionError si esa carpeta no concede escritura
    al usuario actual -- pasa tanto si no pertenece al grupo de Windows
    "OpenVPN Administrators" como si pertenece pero el instalador de
    OpenVPN nunca dejó esa ACL puesta en la carpeta. En ese caso se pide
    una única elevación (UAC) para arreglarlo con
    vpn_client.grant_config_dir_access() y se reintenta la copia una
    vez; si el usuario cancela el UAC o sigue fallando, se propaga el
    error y quien llama lo traduce en un VpnProfileError con
    instrucciones.

    Tras copiar, restringe la ACL del archivo (no de la carpeta entera,
    que sigue compartida por diseño del servicio interactivo) para que
    solo el usuario de Windows actual pueda leerlo -- ver el docstring
    de vpn_client.restrict_config_file_to_current_user(). Best-effort:
    un fallo ahí no debe impedir que el perfil quede registrado y
    utilizable, solo deja la ACL heredada de la carpeta en vez de la
    restringida."""
    config_dir = vpn_client.find_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    dest_in_config = config_dir / f"{tunnel}.ovpn"
    try:
        shutil.copy2(dest, dest_in_config)
    except PermissionError:
        if not vpn_client.grant_config_dir_access():
            raise
        shutil.copy2(dest, dest_in_config)
    vpn_client.restrict_config_file_to_current_user(dest_in_config)
    vpn_client.rescan()


def _unregister_from_openvpn(tunnel: str) -> None:
    try:
        (vpn_client.find_config_dir() / f"{tunnel}.ovpn").unlink(missing_ok=True)
    except OSError:
        pass
    else:
        vpn_client.rescan()


def _import_text(
    display_name: str, text: str, source_label: str, profile: Optional[str] = None
) -> dict:
    """Núcleo común de import_profile()/import_profile_from_text(): valida
    el nombre y el contenido, elige un nombre de túnel, escribe el .ovpn
    en la carpeta del perfil y lo registra con OpenVPN. `source_label` es
    solo para el mensaje de error si el contenido no parece un .ovpn
    válido (nombre de archivo o "servidor de VPNGate", según quien
    llame)."""
    display_name = display_name.strip()
    if not display_name:
        raise VpnProfileError("El perfil necesita un nombre.")

    index = _load_index(profile)
    if display_name in index:
        raise VpnProfileError(f"Ya existe un perfil VPN llamado «{display_name}».")

    if "client" not in text or "remote " not in text:
        raise VpnProfileError(
            f"«{source_label}» no parece un archivo de configuración de OpenVPN "
            "válido (faltan las directivas 'client' o 'remote')."
        )

    text, removed_directives = _strip_dangerous_directives(text)
    if removed_directives:
        log.warning(
            "Perfil VPN «%s» (%s): se quitaron directivas potencialmente "
            "peligrosas del .ovpn antes de guardarlo: %s",
            display_name, source_label, ", ".join(removed_directives),
        )

    taken = {entry.get("tunnel") for entry in index.values() if isinstance(entry, dict)}
    tunnel = _sanitize_tunnel_name(display_name, taken)

    vpn_dir = _vpn_dir(profile)
    vpn_dir.mkdir(parents=True, exist_ok=True)
    dest = vpn_dir / f"{tunnel}.ovpn"
    try:
        dest.write_text(text, encoding="utf-8")
    except OSError as exc:
        raise VpnProfileError(f"No se pudo guardar el archivo: {exc}") from exc

    try:
        _register_with_openvpn(dest, tunnel)
    except OSError as exc:
        dest.unlink(missing_ok=True)
        raise VpnProfileError(
            "No se pudo registrar el perfil en OpenVPN. Si apareció una "
            "ventana pidiendo permiso de administrador, acéptala para que "
            "la app configure el acceso ella sola; si la cancelaste o el "
            "problema persiste, comprueba que tu usuario de Windows "
            "pertenece al grupo «OpenVPN Administrators» "
            f"(detalle: {exc})."
        ) from exc

    index[display_name] = {"tunnel": tunnel}
    _save_index(index, profile)
    return {"name": display_name, "tunnel": tunnel, "conf_path": str(dest)}


def import_profile(display_name: str, source_conf: Path, profile: Optional[str] = None) -> dict:
    """Copia `source_conf` a la carpeta VPN del perfil, la registra con
    OpenVPN, y la indexa bajo `display_name`. Lanza VpnProfileError si el
    nombre ya existe, el archivo de origen no existe, no es un .ovpn
    legible, o no se pudo registrar con OpenVPN (normalmente por no
    pertenecer al grupo "OpenVPN Administrators")."""
    source_conf = Path(source_conf)
    if not source_conf.is_file():
        raise VpnProfileError(f"No se encuentra el archivo: {source_conf}")
    try:
        text = source_conf.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise VpnProfileError(f"No se pudo leer «{source_conf.name}»: {exc}") from exc
    return _import_text(display_name, text, source_conf.name, profile)


def import_profile_from_text(
    display_name: str, ovpn_text: str, profile: Optional[str] = None
) -> dict:
    """Igual que import_profile(), pero a partir del contenido .ovpn ya
    en memoria en vez de un archivo -- lo usa el selector de servidores
    gratuitos de VPNGate (ver core/vpngate.py) para no tener que escribir
    un archivo temporal solo para volver a leerlo."""
    return _import_text(display_name, ovpn_text, "servidor de VPNGate", profile)


def delete_profile(name: str, profile: Optional[str] = None) -> None:
    """Quita el perfil del índice, borra su .ovpn local y su copia
    registrada con OpenVPN. No desconecta el túnel si estuviera en
    marcha -- quien llama debe desconectarlo antes con
    core.vpn_client.disconnect() si procede."""
    index = _load_index(profile)
    entry = index.pop(name, None)
    if entry is None:
        return
    tunnel = entry.get("tunnel") if isinstance(entry, dict) else None
    if tunnel:
        conf = _vpn_dir(profile) / f"{tunnel}.ovpn"
        conf.unlink(missing_ok=True)
        _unregister_from_openvpn(tunnel)
    _save_index(index, profile)
