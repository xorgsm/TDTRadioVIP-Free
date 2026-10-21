"""Descargas HTTP con tope de tamaño.

``requests.get(...).content`` carga la respuesta entera en memoria: una URL
hostil o un servidor roto que devuelva cientos de MB (o un gzip "bomba")
agotaría la RAM. ``fetch_limited`` cuenta los bytes ya descomprimidos y corta
en cuanto se supera el tope.
"""
import logging
import time
from typing import Callable, Optional, Union
from urllib.parse import urljoin, urlsplit

import requests

# Topes por tipo de recurso, holgados para el uso real y lejos de agotar RAM.
MAX_PLAYLIST_BYTES = 64 * 1024 * 1024
MAX_EPG_BYTES = 256 * 1024 * 1024
MAX_FEED_BYTES = 32 * 1024 * 1024
MAX_LOGO_BYTES = 8 * 1024 * 1024

_CHUNK_SIZE = 64 * 1024
MAX_REDIRECTS = 5
# Umbrales para dejar rastro en el log de una descarga lenta: si las cabeceras
# tardan, el tiempo se va en DNS, conexión o TLS (VPN, proxy, DNS lento); si
# tarda el cuerpo, en la transferencia.
SLOW_HEADERS_SECONDS = 3.0
SLOW_TOTAL_SECONDS = 20.0

# Un aviso por host y minuto como máximo: el catálogo pide docenas de logos del
# mismo CDN y, si va lento, cada uno repetiría la misma línea.
SLOW_LOG_INTERVAL_SECONDS = 60.0

logger = logging.getLogger(__name__)
_clock = time.monotonic
_last_slow_log: dict = {}
_REDIRECT_CODES = frozenset({301, 302, 303, 307, 308})


class ResponseTooLarge(requests.RequestException):
    """La respuesta supera el tamaño máximo permitido.

    Hereda de RequestException para que quien ya captura fallos de red
    degrade igual ante un tope superado, sin tocar sus manejadores.
    """


class UnsafeRedirect(requests.RequestException):
    """Una URL (inicial o de una redirección) no pasó la validación."""


class DownloadDeadlineExceeded(requests.Timeout):
    """La descarga superó su plazo total.

    ``timeout`` de requests es por operación de socket: un servidor que
    entrega bytes a gotas puede alargar una descarga indefinidamente.
    """


def get_following_safe_redirects(
    url: str,
    *,
    validate_url: Callable[[str], bool],
    get: Optional[Callable] = None,
    max_redirects: int = MAX_REDIRECTS,
    **kwargs,
):
    """GET que valida `url` y cada salto de redirección con `validate_url`
    antes de pedirlo, en vez de dejar que `requests` los siga a ciegas
    (una URL HTTPS podía redirigir a HTTP, a loopback o a la red local).
    Devuelve la primera respuesta que no es una redirección."""
    do_get = get or requests.get
    current = url
    for _ in range(max_redirects + 1):
        if not validate_url(current):
            raise UnsafeRedirect(f"Destino no permitido: {current}")
        resp = do_get(current, allow_redirects=False, **kwargs)
        if getattr(resp, "status_code", None) not in _REDIRECT_CODES:
            return resp
        location = resp.headers.get("Location")
        resp.close()
        if not location:
            raise UnsafeRedirect("Redirección sin destino")
        current = urljoin(current, location)
    raise UnsafeRedirect("Demasiadas redirecciones")


def _declared_length(resp) -> int | None:
    try:
        return int(resp.headers.get("Content-Length"))
    except (TypeError, ValueError):
        return None


def _log_if_slow(
    url: str, headers_seconds: float, total_seconds: float, now: float, *, aborted: bool = False
) -> None:
    """Rastro de una descarga lenta o abortada. Solo el host: la ruta y la
    consulta de una lista pueden llevar credenciales o tokens."""
    if (
        not aborted
        and headers_seconds < SLOW_HEADERS_SECONDS
        and total_seconds < SLOW_TOTAL_SECONDS
    ):
        return
    host = urlsplit(url).hostname or "?"
    last = _last_slow_log.get(host)
    if last is not None and 0 <= now - last < SLOW_LOG_INTERVAL_SECONDS:
        return
    _last_slow_log[host] = now
    logger.warning(
        "Descarga %s de %s: cabeceras %.1f s (DNS, conexión y TLS), total %.1f s",
        "abortada por plazo" if aborted else "lenta", host, headers_seconds, total_seconds,
    )


def fetch_limited(
    url: str,
    *,
    max_bytes: int,
    timeout: Union[float, tuple],
    validate_url: Optional[Callable[[str], bool]] = None,
    deadline: Optional[float] = None,
    max_redirects: int = MAX_REDIRECTS,
) -> bytes:
    """Descarga ``url`` y devuelve el cuerpo, sin pasar de ``max_bytes``.

    Lanza ``ResponseTooLarge`` si lo declarado en Content-Length o lo
    realmente leído lo supera, y propaga los errores de ``requests``. Si se
    pasa ``validate_url``, la URL y cada redirección se validan con ella
    (``UnsafeRedirect`` si alguna no pasa; ``max_redirects`` acota la cadena).

    ``timeout`` puede ser ``(conexión, lectura)``. ``deadline`` es el plazo
    TOTAL en segundos (``DownloadDeadlineExceeded`` si se supera entre trozos).
    """
    started = _clock()
    if validate_url is None:
        resp = requests.get(url, timeout=timeout, stream=True)
    else:
        resp = get_following_safe_redirects(
            url, validate_url=validate_url, max_redirects=max_redirects,
            timeout=timeout, stream=True,
        )
    headers_seconds = _clock() - started
    try:
        resp.raise_for_status()
        declared = _declared_length(resp)
        if declared is not None and declared > max_bytes:
            raise ResponseTooLarge(f"La respuesta declara {declared} bytes (máximo {max_bytes})")
        chunks = []
        total = 0
        incoming = iter(resp.iter_content(chunk_size=_CHUNK_SIZE))
        chunk = next(incoming, None)
        while chunk is not None:
            total += len(chunk)
            if total > max_bytes:
                raise ResponseTooLarge(f"La respuesta supera el máximo de {max_bytes} bytes")
            chunks.append(chunk)
            following = next(incoming, None)
            # El plazo solo corta si aún falta cuerpo: una descarga que ya
            # terminó no se descarta por haber llegado justo tarde.
            if following is not None and deadline is not None:
                now = _clock()
                if now - started > deadline:
                    _log_if_slow(url, headers_seconds, now - started, now, aborted=True)
                    raise DownloadDeadlineExceeded(
                        f"La descarga superó el plazo de {deadline:g} s"
                    )
            chunk = following
        now = _clock()
        _log_if_slow(url, headers_seconds, now - started, now)
        return b"".join(chunks)
    finally:
        resp.close()
