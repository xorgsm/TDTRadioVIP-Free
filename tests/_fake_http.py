"""Respuestas HTTP falsas para tests que sustituyen ``requests.get``.

``core.http_limits.fetch_limited`` descarga en streaming (``iter_content``),
así que un simple ``Mock(content=...)`` ya no basta.
"""
from unittest.mock import Mock


def fake_response(content: bytes) -> Mock:
    resp = Mock()
    resp.content = content
    resp.headers = {}
    resp.iter_content = Mock(side_effect=lambda chunk_size=1: iter([content]))
    resp.raise_for_status = Mock()
    return resp
