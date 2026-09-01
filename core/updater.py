"""
Comprobación de actualizaciones "de solo consulta": ni descarga ni
reemplaza el .exe en marcha (eso es tarea del instalador de Inno Setup,
ver TDTRadioVIP_Setup.iss) -- esto solo mira si hay una versión más
reciente publicada y, si la hay, deja que el usuario decida abrir la
página de descarga a mano. Mismo patrón de "URL opcional, vacía por
defecto = desactivado" que core/epg.py con epg_url.

Formato esperado en update_check_url: un JSON tipo
    {"version": "6.5.0", "url": "https://.../descargas"}

Coder By X@R
"""
import hashlib
import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit

import requests

from core.config import APP_VERSION
from core.logger import get_logger

log = get_logger(__name__)
MAX_UPDATE_BYTES = 750 * 1024 * 1024
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


def _version_tuple(texto: str) -> tuple:
    """
    '6.10.2' -> (6, 10, 2). Componentes no numéricos (sufijos tipo
    '6.4.0-beta') se ignoran en vez de reventar la comparación.
    """
    partes = re.findall(r"\d+", str(texto or ""))
    # Evita que un manifiesto hostil fuerce conversiones de enteros gigantes
    # (Python las rechaza a partir de cierto tamaño) o tuplas desmesuradas.
    if not partes or len(partes) > 8 or any(len(parte) > 9 for parte in partes):
        return (0,)
    return tuple(int(parte) for parte in partes)


def _is_https_url(url: object) -> bool:
    """Acepta solo HTTPS absoluto con host, nunca esquemas del sistema."""
    try:
        parts = urlsplit(str(url or "").strip())
        return parts.scheme.lower() == "https" and bool(parts.hostname)
    except (TypeError, ValueError):
        return False


def check_for_update(update_check_url: str, current_version: str = APP_VERSION) -> Optional[dict]:
    """
    Devuelve el JSON remoto ({"version": ..., "url": ...}) si describe una
    versión más nueva que la actual, o None si la URL está vacía (función
    desactivada), si no hay red, si el JSON es inválido, o si ya se tiene
    la última versión. Nunca lanza -- se llama desde un hilo de fondo (ver
    ui/fetch_worker.FetchWorker) y un fallo de red no debe ser más que
    "no hay actualización que mostrar".
    """
    if not update_check_url:
        return None
    if not _is_https_url(update_check_url):
        log.warning("La URL de comprobación de actualizaciones no es HTTPS válida")
        return None
    try:
        resp = requests.get(update_check_url, timeout=8)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        log.warning("No se pudo comprobar actualizaciones en %s", update_check_url, exc_info=True)
        return None

    if not isinstance(data, dict):
        return None
    version_remota = data.get("version", "")
    if not version_remota:
        return None

    release_url = data.get("download_url") or data.get("url")
    if not _is_https_url(release_url):
        log.warning("El manifiesto de actualización contiene una URL no segura")
        return None

    if _version_tuple(version_remota) > _version_tuple(current_version):
        return data
    return None


def validate_download_manifest(data: dict) -> dict:
    """Valida los campos necesarios antes de descargar un instalador."""
    if not isinstance(data, dict):
        raise ValueError("Manifiesto de actualización inválido.")
    url = str(data.get("download_url") or data.get("url") or "").strip()
    checksum = str(data.get("sha256") or "").strip().lower()
    if not _is_https_url(url):
        raise ValueError("La descarga de la actualización debe usar HTTPS.")
    if not SHA256_RE.fullmatch(checksum):
        raise ValueError("El manifiesto no incluye un SHA-256 válido.")
    filename = Path(url.split("?", 1)[0]).name or "TDTRadioVIP_Update.exe"
    if not filename.lower().endswith(".exe"):
        raise ValueError("La actualización debe ser un instalador EXE.")
    return {**data, "download_url": url, "sha256": checksum, "filename": filename}


def download_verified_update(
    manifest: dict,
    destination_dir: str | Path,
    *,
    request_get=requests.get,
    max_bytes: int = MAX_UPDATE_BYTES,
) -> Path:
    """Descarga a `.part`, verifica SHA-256 y publica el EXE atómicamente."""
    clean = validate_download_manifest(manifest)
    destination = Path(destination_dir)
    destination.mkdir(parents=True, exist_ok=True)
    final_path = destination / clean["filename"]
    partial_path = final_path.with_suffix(final_path.suffix + ".part")
    digest = hashlib.sha256()
    total = 0
    try:
        response = request_get(clean["download_url"], stream=True, timeout=30)
        response.raise_for_status()
        with partial_path.open("wb") as output:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > max_bytes:
                    raise ValueError("La actualización supera el tamaño máximo permitido.")
                digest.update(chunk)
                output.write(chunk)
        if digest.hexdigest() != clean["sha256"]:
            raise ValueError("La actualización descargada no supera la verificación SHA-256.")
        partial_path.replace(final_path)
        return final_path
    except Exception:
        partial_path.unlink(missing_ok=True)
        raise
