"""
fetch_limited: descarga con tope de tamaño.

EPG, listas M3U, podcasts y logos se cargaban enteros en memoria con
`resp.content`: una URL hostil (o un servidor roto) que devolviera cientos de
MB o un zip/gzip "bomba" agotaba la RAM del equipo. El tope se aplica a los
bytes ya descomprimidos y corta en cuanto se supera, sin esperar al final.
"""
from unittest.mock import Mock

import pytest
import requests

from core import http_limits
from core.http_limits import ResponseTooLarge, fetch_limited


def _respuesta(chunks, content_length=None, status_ok=True):
    resp = Mock()
    resp.headers = {} if content_length is None else {"Content-Length": str(content_length)}
    resp.iter_content = Mock(return_value=iter(chunks))
    if status_ok:
        resp.raise_for_status = Mock()
    else:
        resp.raise_for_status = Mock(side_effect=requests.HTTPError("HTTP 500"))
    return resp


def _patch_get(monkeypatch, resp):
    get = Mock(return_value=resp)
    monkeypatch.setattr(http_limits.requests, "get", get)
    return get


def test_devuelve_los_bytes_si_caben_en_el_limite(monkeypatch):
    resp = _respuesta([b"abc", b"def"])
    get = _patch_get(monkeypatch, resp)

    assert fetch_limited("https://x.test/a", max_bytes=10, timeout=5) == b"abcdef"

    assert get.call_args.kwargs["stream"] is True
    assert get.call_args.kwargs["timeout"] == 5
    resp.close.assert_called_once()


def test_acepta_justo_el_limite(monkeypatch):
    _patch_get(monkeypatch, _respuesta([b"12345"]))
    assert fetch_limited("https://x.test/a", max_bytes=5, timeout=5) == b"12345"


def test_rechaza_si_content_length_declarado_supera_el_limite_sin_leer_el_cuerpo(monkeypatch):
    resp = _respuesta([b"x"], content_length=1000)
    _patch_get(monkeypatch, resp)

    with pytest.raises(ResponseTooLarge):
        fetch_limited("https://x.test/a", max_bytes=100, timeout=5)

    resp.iter_content.assert_not_called()
    resp.close.assert_called_once()


def test_corta_la_lectura_cuando_los_bytes_reales_superan_el_limite(monkeypatch):
    """Content-Length ausente o mentiroso (chunked, gzip): se cuenta lo leído."""
    leidos = []

    def _chunks():
        for _ in range(100):
            leidos.append(1)
            yield b"x" * 10

    resp = _respuesta([])
    resp.iter_content = Mock(return_value=_chunks())
    _patch_get(monkeypatch, resp)

    with pytest.raises(ResponseTooLarge):
        fetch_limited("https://x.test/a", max_bytes=25, timeout=5)

    assert len(leidos) == 3  # 10 + 10 + 10 > 25: no sigue leyendo
    resp.close.assert_called_once()


def test_content_length_invalido_se_ignora_y_se_cuenta_lo_leido(monkeypatch):
    resp = _respuesta([b"abc"])
    resp.headers = {"Content-Length": "no-es-un-numero"}
    _patch_get(monkeypatch, resp)

    assert fetch_limited("https://x.test/a", max_bytes=10, timeout=5) == b"abc"


def test_propaga_el_error_http_y_cierra_la_respuesta(monkeypatch):
    resp = _respuesta([b"x"], status_ok=False)
    _patch_get(monkeypatch, resp)

    with pytest.raises(requests.HTTPError):
        fetch_limited("https://x.test/a", max_bytes=10, timeout=5)

    resp.close.assert_called_once()


def test_response_too_large_es_un_request_exception():
    """Los llamadores ya capturan requests.RequestException: no hace falta
    tocar sus manejadores de error para que un tope superado degrade igual
    que una red caída."""
    assert issubclass(ResponseTooLarge, requests.RequestException)
