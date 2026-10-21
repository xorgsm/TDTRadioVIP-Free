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


# --- Plazo total, diagnóstico de lentitud y límite de redirecciones ----------

def _clock(*ticks):
    values = iter(ticks)
    last = [ticks[-1]]

    def now():
        last[0] = next(values, last[0])
        return last[0]

    return now


def test_the_connect_and_read_timeouts_can_be_given_separately(monkeypatch):
    get = _patch_get(monkeypatch, _respuesta([b"abc"]))

    fetch_limited("https://x.test/a", max_bytes=10, timeout=(3.05, 8))

    assert get.call_args.kwargs["timeout"] == (3.05, 8)


def test_a_download_that_trickles_past_the_deadline_is_aborted(monkeypatch):
    resp = _respuesta([b"a", b"b", b"c", b"d"])
    _patch_get(monkeypatch, resp)
    # inicio=0, cabeceras=1, y cada trozo avanza 10 s frente a un plazo de 15
    monkeypatch.setattr(http_limits, "_clock", _clock(0, 1, 11, 21, 31, 41))

    with pytest.raises(requests.Timeout):
        fetch_limited("https://x.test/a", max_bytes=100, timeout=5, deadline=15)

    resp.close.assert_called_once()


def test_no_deadline_means_no_time_limit(monkeypatch):
    _patch_get(monkeypatch, _respuesta([b"a", b"b"]))
    monkeypatch.setattr(http_limits, "_clock", _clock(0, 1, 5000, 9000))

    assert fetch_limited("https://x.test/a", max_bytes=100, timeout=5) == b"ab"


def test_slow_response_headers_are_logged_with_the_host_only(monkeypatch, caplog):
    _patch_get(monkeypatch, _respuesta([b"abc"]))
    monkeypatch.setattr(http_limits, "_clock", _clock(0, 7.5, 8))

    with caplog.at_level("WARNING", logger="core.http_limits"):
        fetch_limited("https://lista.test/privado/tok3n?clave=secreta", max_bytes=10, timeout=5)

    message = " ".join(record.getMessage() for record in caplog.records)
    assert "lista.test" in message
    assert "7.5" in message
    assert "secreta" not in message and "tok3n" not in message


def test_a_fast_download_logs_nothing_at_warning_level(monkeypatch, caplog):
    _patch_get(monkeypatch, _respuesta([b"abc"]))
    monkeypatch.setattr(http_limits, "_clock", _clock(0, 0.2, 0.4))

    with caplog.at_level("WARNING", logger="core.http_limits"):
        fetch_limited("https://x.test/a", max_bytes=10, timeout=5)

    assert caplog.records == []


def test_max_redirects_caps_the_redirect_chain():
    redirect = Mock(status_code=302, headers={"Location": "https://x.test/otra"})
    get = Mock(return_value=redirect)

    with pytest.raises(http_limits.UnsafeRedirect):
        http_limits.get_following_safe_redirects(
            "https://x.test/a", validate_url=lambda _u: True, get=get, max_redirects=2,
        )

    assert get.call_count == 3  # la petición inicial y dos saltos


def test_fetch_limited_passes_max_redirects_to_the_safe_follower(monkeypatch):
    redirect = Mock(status_code=302, headers={"Location": "https://x.test/otra"})
    get = Mock(return_value=redirect)
    monkeypatch.setattr(http_limits.requests, "get", get)

    with pytest.raises(http_limits.UnsafeRedirect):
        fetch_limited(
            "https://x.test/a", max_bytes=10, timeout=5,
            validate_url=lambda _u: True, max_redirects=1,
        )

    assert get.call_count == 2


def test_an_aborted_download_leaves_a_trace_in_the_log(monkeypatch, caplog):
    _patch_get(monkeypatch, _respuesta([b"a", b"b", b"c"]))
    monkeypatch.setattr(http_limits, "_clock", _clock(0, 1, 11, 21))

    with caplog.at_level("WARNING", logger="core.http_limits"):
        with pytest.raises(requests.Timeout):
            fetch_limited("https://lenta.test/lista?k=secreto", max_bytes=100, timeout=5, deadline=15)

    message = " ".join(record.getMessage() for record in caplog.records)
    assert "lenta.test" in message
    assert "secreto" not in message


def test_the_deadline_does_not_discard_a_download_that_already_finished(monkeypatch):
    _patch_get(monkeypatch, _respuesta([b"a", b"b"]))
    # el último trozo llega pasado el plazo, pero ya no queda nada por descargar
    monkeypatch.setattr(http_limits, "_clock", _clock(0, 1, 5, 99, 99))

    assert fetch_limited("https://x.test/a", max_bytes=100, timeout=5, deadline=15) == b"ab"


def test_slow_download_warnings_are_limited_to_one_per_host_per_minute(monkeypatch, caplog):
    http_limits._last_slow_log.clear()
    for _ in range(3):
        _patch_get(monkeypatch, _respuesta([b"x"]))
        monkeypatch.setattr(http_limits, "_clock", _clock(0, 9, 9.5))
        with caplog.at_level("WARNING", logger="core.http_limits"):
            fetch_limited("https://cdn.lento.test/a.png", max_bytes=10, timeout=5)

    assert len([r for r in caplog.records if "cdn.lento.test" in r.getMessage()]) == 1
