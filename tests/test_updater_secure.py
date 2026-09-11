import hashlib

import pytest

from core import updater
from core.updater import (
    check_for_update,
    cleanup_obsolete_updates,
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


def test_downloading_a_new_update_removes_previously_downloaded_installers(tmp_path):
    """Cada 'Buscar actualizaciones' > 'Descargar y verificar' se quedaba
    acumulando un .exe nuevo sin borrar los anteriores (reportado: varios
    instaladores acumulados en la carpeta updates)."""
    old_installer = tmp_path / "TDTRadioVIP_Setup_v7.6.6.0.exe"
    old_installer.write_bytes(b"old installer")

    payload = b"new installer bytes"
    manifest = {
        "download_url": "https://updates.test/TDTRadioVIP_Setup_v8.0.exe",
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    download_verified_update(
        manifest, tmp_path, request_get=lambda *args, **kwargs: _Response(payload)
    )

    remaining = sorted(p.name for p in tmp_path.iterdir())
    assert remaining == ["TDTRadioVIP_Setup_v8.0.exe"]


def test_cleanup_obsolete_updates_removes_installers_already_installed(tmp_path):
    for name in (
        "TDTRadioVIP_Setup_v7.6.3.1.exe", "TDTRadioVIP_Setup_v7.6.6.0.exe",
        "TDTRadioVIP_Setup_v8.0.exe",
    ):
        (tmp_path / name).write_bytes(b"x")

    removed = cleanup_obsolete_updates(tmp_path, current_version="8.0")

    assert removed == 3
    assert list(tmp_path.iterdir()) == []


def test_cleanup_obsolete_updates_keeps_installers_newer_than_current(tmp_path):
    (tmp_path / "TDTRadioVIP_Setup_v7.6.6.0.exe").write_bytes(b"x")
    (tmp_path / "TDTRadioVIP_Setup_v9.0.exe").write_bytes(b"x")

    removed = cleanup_obsolete_updates(tmp_path, current_version="8.0")

    assert removed == 1
    assert [p.name for p in tmp_path.iterdir()] == ["TDTRadioVIP_Setup_v9.0.exe"]


def test_cleanup_obsolete_updates_ignores_unrecognized_filenames(tmp_path):
    (tmp_path / "algo_que_no_es_nuestro.exe").write_bytes(b"x")

    removed = cleanup_obsolete_updates(tmp_path, current_version="8.0")

    assert removed == 0
    assert (tmp_path / "algo_que_no_es_nuestro.exe").exists()


def test_cleanup_obsolete_updates_tolerates_missing_directory(tmp_path):
    assert cleanup_obsolete_updates(tmp_path / "no-existe", current_version="8.0") == 0


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


@pytest.mark.parametrize("url", [
    "http://updates.test/manifest.json",
    "file:///C:/Windows/System32/manifest.json",
    "https:///missing-host/manifest.json",
])
def test_update_check_rejects_unsafe_manifest_url_before_request(monkeypatch, url):
    def unexpected_request(*args, **kwargs):
        pytest.fail("an unsafe manifest URL must not reach the network client")

    monkeypatch.setattr(updater.requests, "get", unexpected_request)
    assert check_for_update(url, "7.6.1") is None


def test_update_check_does_not_crash_on_giant_version(monkeypatch):
    monkeypatch.setattr(
        updater.requests,
        "get",
        lambda *args, **kwargs: _ManifestResponse(
            {"version": "9" * 10_000, "url": "https://updates.test/download"}
        ),
    )
    assert check_for_update("https://updates.test/manifest.json", "7.6.1") is None
