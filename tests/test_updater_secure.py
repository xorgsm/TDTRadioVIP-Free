import hashlib

import pytest

from core import updater
from core.updater import (
    check_for_update,
    download_verified_update,
    validate_download_manifest,
)


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        yield self.payload


def test_verified_update_is_published_atomically(tmp_path):
    payload = b"signed installer bytes"
    manifest = {
        "download_url": "https://updates.test/setup.exe",
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    result = download_verified_update(
        manifest, tmp_path, request_get=lambda *args, **kwargs: _Response(payload)
    )
    assert result.read_bytes() == payload
    assert not result.with_suffix(".exe.part").exists()


def test_invalid_checksum_removes_partial_download(tmp_path):
    manifest = {"url": "https://updates.test/setup.exe", "sha256": "0" * 64}
    with pytest.raises(ValueError, match="SHA-256"):
        download_verified_update(
            manifest, tmp_path, request_get=lambda *args, **kwargs: _Response(b"bad")
        )
    assert list(tmp_path.iterdir()) == []


def test_manifest_rejects_insecure_url():
    with pytest.raises(ValueError, match="HTTPS"):
        validate_download_manifest({"url": "http://test/setup.exe", "sha256": "0" * 64})


@pytest.mark.parametrize("url", [
    "file:///C:/Windows/System32/calc.exe",
    "javascript:alert(1)",
    "https:///missing-host/setup.exe",
    "https://",
])
def test_manifest_rejects_non_web_or_hostless_urls(url):
    with pytest.raises(ValueError, match="HTTPS"):
        validate_download_manifest({"url": url, "sha256": "0" * 64})


class _ManifestResponse:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        return None

    def json(self):
        return self.data


def test_update_check_rejects_unsafe_release_url(monkeypatch):
    monkeypatch.setattr(
        updater.requests,
        "get",
        lambda *args, **kwargs: _ManifestResponse(
            {"version": "99.0", "url": "file:///C:/Windows/System32/calc.exe"}
        ),
    )
    assert check_for_update("https://updates.test/manifest.json", "7.6.1") is None


def test_update_check_does_not_crash_on_giant_version(monkeypatch):
    monkeypatch.setattr(
        updater.requests,
        "get",
        lambda *args, **kwargs: _ManifestResponse(
            {"version": "9" * 10_000, "url": "https://updates.test/download"}
        ),
    )
    assert check_for_update("https://updates.test/manifest.json", "7.6.1") is None
