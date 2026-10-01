"""
redact_url: las URLs de streams IPTV suelen llevar credenciales o tokens
(usuario:clave@host, ?token=..., /live/usuario/clave/1.ts). No deben acabar
en app.log, que el usuario puede adjuntar a un informe de errores.
"""
import pytest

from core.logger import redact_url


@pytest.mark.parametrize("url,esperado", [
    ("https://host.test/live/user/pass/1.ts", "https://host.test/..."),
    ("http://user:secret@host.test:8080/stream.m3u8?token=abc#x", "http://host.test:8080/..."),
    ("https://host.test", "https://host.test/..."),
])
def test_redact_url_deja_solo_esquema_y_host(url, esperado):
    resultado = redact_url(url)
    assert resultado == esperado
    assert "secret" not in resultado and "token" not in resultado


@pytest.mark.parametrize("valor", ["", None, "no es una url", "ftp:///sin-host"])
def test_redact_url_no_lanza_con_entradas_raras(valor):
    assert isinstance(redact_url(valor), str)
    assert "secret" not in redact_url(valor)
