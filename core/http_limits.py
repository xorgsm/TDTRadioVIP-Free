"""Descargas HTTP con tope de tamaño.

``requests.get(...).content`` carga la respuesta entera en memoria: una URL
hostil o un servidor roto que devuelva cientos de MB (o un gzip "bomba")
agotaría la RAM. ``fetch_limited`` cuenta los bytes ya descomprimidos y corta
en cuanto se supera el tope.
"""
import requests

# Topes por tipo de recurso, holgados para el uso real y lejos de agotar RAM.
MAX_PLAYLIST_BYTES = 64 * 1024 * 1024
MAX_EPG_BYTES = 256 * 1024 * 1024
MAX_FEED_BYTES = 32 * 1024 * 1024
MAX_LOGO_BYTES = 8 * 1024 * 1024

_CHUNK_SIZE = 64 * 1024


class ResponseTooLarge(requests.RequestException):
    """La respuesta supera el tamaño máximo permitido.

    Hereda de RequestException para que quien ya captura fallos de red
    degrade igual ante un tope superado, sin tocar sus manejadores.
    """


def _declared_length(resp) -> int | None:
    try:
        return int(resp.headers.get("Content-Length"))
    except (TypeError, ValueError):
        return None


def fetch_limited(url: str, *, max_bytes: int, timeout: float) -> bytes:
    """Descarga ``url`` y devuelve el cuerpo, sin pasar de ``max_bytes``.

    Lanza ``ResponseTooLarge`` si lo declarado en Content-Length o lo
    realmente leído lo supera, y propaga los errores de ``requests``.
    """
    resp = requests.get(url, timeout=timeout, stream=True)
    try:
        resp.raise_for_status()
        declared = _declared_length(resp)
        if declared is not None and declared > max_bytes:
            raise ResponseTooLarge(f"La respuesta declara {declared} bytes (máximo {max_bytes})")
        chunks = []
        total = 0
        for chunk in resp.iter_content(chunk_size=_CHUNK_SIZE):
            total += len(chunk)
            if total > max_bytes:
                raise ResponseTooLarge(f"La respuesta supera el máximo de {max_bytes} bytes")
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        resp.close()
