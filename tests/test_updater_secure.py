import json
import hashlib
import os
import time

import pytest

import _signing
from core import updater
from core.updater import (
    UP_TO_DATE,
    check_for_update,
    check_for_update_if_due,
    cleanup_obsolete_updates,
    download_verified_update,
    validate_download_manifest,
)


class _Response:
    def __init__(self, payload):
        self.payload = payload
        self.closed = False

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        yield self.payload

    def close(self):
        self.closed = True


def test_verified_update_is_published_atomically(tmp_path, trusted_update_key):
    payload = b"signed installer bytes"
    manifest = _signing.signed_manifest(payload, filename="setup.exe")
    result = download_verified_update(
        manifest, tmp_path, request_get=lambda *args, **kwargs: _Response(payload)
    )
    assert result.read_bytes() == payload
    assert not result.with_suffix(".exe.part").exists()


def test_downloading_a_new_update_removes_previously_downloaded_installers(
    tmp_path, trusted_update_key
):
    """Cada 'Buscar actualizaciones' > 'Descargar y verificar' se quedaba
    acumulando un .exe nuevo sin borrar los anteriores (reportado: varios
    instaladores acumulados en la carpeta updates)."""
    old_installer = tmp_path / "TDTRadioVIP_Setup_v7.6.6.0.exe"
    old_installer.write_bytes(b"old installer")

    payload = b"new installer bytes"
    manifest = _signing.signed_manifest(
        payload, version="8.0", filename="TDTRadioVIP_Setup_v8.0.exe"
    )
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


def test_invalid_checksum_removes_partial_download(tmp_path, trusted_update_key):
    """Firma valida, pero el servidor entrega otros bytes: sigue fallando por
    SHA-256 y no deja el .part."""
    manifest = _signing.signed_manifest(b"good", filename="setup.exe")
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


# --------------------------------------------------------------------------
# Firma del manifiesto
# --------------------------------------------------------------------------

def test_manifest_without_signature_is_rejected(trusted_update_key):
    manifest = _signing.signed_manifest()
    del manifest["signature"]
    with pytest.raises(ValueError, match="firmado"):
        validate_download_manifest(manifest)


def test_unsigned_manifest_makes_no_network_request(tmp_path, trusted_update_key):
    manifest = _signing.signed_manifest()
    del manifest["signature"]

    def unexpected_request(*args, **kwargs):
        pytest.fail("un manifiesto sin firma no debe llegar a la red")

    with pytest.raises(ValueError):
        download_verified_update(manifest, tmp_path, request_get=unexpected_request)
    assert list(tmp_path.iterdir()) == []


def test_manifest_with_tampered_hash_is_rejected(trusted_update_key):
    manifest = _signing.signed_manifest(b"original")
    manifest["sha256"] = "0" * 64  # el atacante cambia el hash a conveniencia
    with pytest.raises(ValueError, match="firma"):
        validate_download_manifest(manifest)


def test_manifest_with_tampered_version_is_rejected(trusted_update_key):
    manifest = _signing.signed_manifest()
    manifest["version"] = "9.9.9"
    with pytest.raises(ValueError, match="firma"):
        validate_download_manifest(manifest)


@pytest.mark.parametrize("signature", [None, 123, ["aa"], {"a": 1}, ""])
def test_signature_of_the_wrong_type_is_treated_as_unsigned(trusted_update_key, signature):
    manifest = _signing.signed_manifest()
    manifest["signature"] = signature
    with pytest.raises(ValueError, match="firmado"):
        validate_download_manifest(manifest)


def test_uppercase_signature_with_spaces_is_accepted(trusted_update_key):
    manifest = _signing.signed_manifest()
    manifest["signature"] = "  " + manifest["signature"].upper() + " "
    clean = validate_download_manifest(manifest)
    assert clean["signature"] == manifest["signature"].strip().lower()


def test_numeric_version_in_the_json_is_normalised_like_the_tool_does(trusted_update_key):
    manifest = _signing.signed_manifest(version="8.7")
    manifest["version"] = 8.7  # el JSON trae un numero, no una cadena
    assert validate_download_manifest(manifest)["filename"] == "TDTRadioVIP_Setup_v8.7.0.exe"


def test_query_string_in_the_url_does_not_change_the_signed_filename(trusted_update_key):
    manifest = _signing.signed_manifest()
    manifest["download_url"] += "?download=1&token=abc"
    manifest["signature"] = _signing.sign(
        manifest["version"], "TDTRadioVIP_Setup_v8.7.0.exe", manifest["sha256"],
        manifest["download_url"],
    )
    clean = validate_download_manifest(manifest)
    assert clean["filename"] == "TDTRadioVIP_Setup_v8.7.0.exe"


def test_swapping_the_download_host_invalidates_the_signature(trusted_update_key):
    manifest = _signing.signed_manifest()
    manifest["download_url"] = "https://evil.test/TDTRadioVIP_Setup_v8.7.0.exe"
    with pytest.raises(ValueError, match="firma"):
        validate_download_manifest(manifest)


def test_without_a_configured_public_key_no_manifest_is_accepted(monkeypatch):
    manifest = _signing.signed_manifest()
    monkeypatch.setattr(updater.update_signature, "UPDATE_PUBLIC_KEY_N_B64", "")
    with pytest.raises(ValueError, match="firma"):
        validate_download_manifest(manifest)


def test_has_valid_signature_reports_without_raising(trusted_update_key):
    firmado = _signing.signed_manifest()
    sin_firma = {k: v for k, v in firmado.items() if k != "signature"}
    inseguro = {**firmado, "download_url": "http://updates.test/setup.exe"}

    assert updater.has_valid_signature(firmado) is True
    assert updater.has_valid_signature(sin_firma) is False
    assert updater.has_valid_signature(inseguro) is False
    assert updater.has_valid_signature(None) is False
    assert updater.has_valid_signature("no es un dict") is False


def test_validate_manifest_fields_does_not_look_at_the_signature():
    campos = updater.validate_manifest_fields(
        {"download_url": "https://updates.test/Setup_v8.7.0.exe", "sha256": "A" * 64}
    )
    assert campos == {
        "download_url": "https://updates.test/Setup_v8.7.0.exe",
        "sha256": "a" * 64,
        "filename": "Setup_v8.7.0.exe",
    }


class _ManifestResponse:
    """Doble de la respuesta HTTP en streaming que consume fetch_limited."""

    def __init__(self, data, *, raw=None):
        self.data = data
        self.raw = raw if raw is not None else json.dumps(data).encode("utf-8")
        self.headers = {}

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size=1):
        yield self.raw

    def close(self):
        return None


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


# --------------------------------------------------------------------------
# check_update_status: distinguir "al día" de "no se pudo comprobar"
# --------------------------------------------------------------------------

MANIFEST_URL = "https://updates.test/manifest.json"
NEWER = {"version": "8.7.0", "download_url": "https://updates.test/setup_v8.7.0.exe"}


def _serve(monkeypatch, data):
    monkeypatch.setattr(updater.requests, "get", lambda *a, **k: _ManifestResponse(data))


def test_update_status_returns_manifest_when_there_is_a_newer_version(monkeypatch):
    _serve(monkeypatch, NEWER)
    assert updater.check_update_status(MANIFEST_URL, "8.6.23") == NEWER


@pytest.mark.parametrize("remote", ["8.6.23", "8.6.1"])
def test_update_status_says_up_to_date_when_remote_is_not_newer(monkeypatch, remote):
    _serve(monkeypatch, {**NEWER, "version": remote})
    assert updater.check_update_status(MANIFEST_URL, "8.6.23") == UP_TO_DATE


def test_update_status_is_none_when_there_is_no_connection(monkeypatch):
    """Antes Buscar actualizaciones decía "Ya tienes la versión más reciente"
    sin conexión: check_for_update() devolvía None en los dos casos."""
    def offline(*args, **kwargs):
        raise updater.requests.ConnectionError("sin red")

    monkeypatch.setattr(updater.requests, "get", offline)
    assert updater.check_update_status(MANIFEST_URL, "8.6.23") is None


@pytest.mark.parametrize("data", [
    ["no", "es", "un", "dict"],
    {"download_url": "https://updates.test/x.exe"},
    {"version": "8.7.0", "url": "file:///C:/Windows/System32/calc.exe"},
    {"version": "9" * 10_000, "url": "https://updates.test/download"},
])
def test_update_status_is_none_when_manifest_is_unusable(monkeypatch, data):
    _serve(monkeypatch, data)
    assert updater.check_update_status(MANIFEST_URL, "8.6.23") is None


def test_check_for_update_still_returns_none_when_up_to_date(monkeypatch):
    """La comprobación automática sigue sin distinguir: solo avisa si hay
    versión nueva."""
    _serve(monkeypatch, {**NEWER, "version": "8.6.23"})
    assert check_for_update(MANIFEST_URL, "8.6.23") is None


def test_check_for_update_if_due_runs_on_first_call(tmp_path, monkeypatch):
    """Sin marcador previo (primer arranque), debe comprobar ya mismo."""
    llamadas = []
    monkeypatch.setattr(
        updater, "check_for_update",
        lambda url, version: llamadas.append((url, version)) or {"version": "9.0"},
    )
    resultado = check_for_update_if_due("https://updates.test/manifest.json", tmp_path, "8.1.0")

    assert resultado == {"version": "9.0"}
    assert llamadas == [("https://updates.test/manifest.json", "8.1.0")]
    assert (tmp_path / ".last_check").exists()


def test_check_for_update_if_due_skips_when_checked_recently(tmp_path, monkeypatch):
    (tmp_path / ".last_check").touch()

    def no_debe_llamarse(*args, **kwargs):
        pytest.fail("no debe consultar la red si el marcador es reciente")

    monkeypatch.setattr(updater, "check_for_update", no_debe_llamarse)

    assert check_for_update_if_due(
        "https://updates.test/manifest.json", tmp_path, "8.1.0", min_interval_hours=24
    ) is None


def test_check_for_update_if_due_runs_again_after_interval(tmp_path, monkeypatch):
    marker = tmp_path / ".last_check"
    marker.touch()
    old = time.time() - (25 * 3600)
    os.utime(marker, (old, old))

    monkeypatch.setattr(updater, "check_for_update", lambda url, version: {"version": "9.0"})

    resultado = check_for_update_if_due(
        "https://updates.test/manifest.json", tmp_path, "8.1.0", min_interval_hours=24
    )

    assert resultado == {"version": "9.0"}


def test_check_for_update_if_due_tolerates_missing_marker_directory(tmp_path, monkeypatch):
    """El directorio de destino (p.ej. updates/) puede no existir todavía
    en una instalación nueva -- no debe reventar la comprobación al arrancar."""
    monkeypatch.setattr(updater, "check_for_update", lambda url, version: None)

    resultado = check_for_update_if_due(
        "https://updates.test/manifest.json", tmp_path / "updates-no-creado", "8.1.0"
    )

    assert resultado is None
    assert (tmp_path / "updates-no-creado" / ".last_check").exists()


def test_update_status_is_none_when_the_manifest_is_oversized(monkeypatch):
    """Un manifiesto de verdad pesa unos cientos de bytes: una respuesta
    enorme (servidor comprometido o redireccion) no debe cargarse entera."""
    huge = b'{"version": "8.7.0", "pad": "' + b"x" * (updater.MAX_MANIFEST_BYTES + 1) + b'"}'
    monkeypatch.setattr(updater.requests, "get", lambda *a, **k: _ManifestResponse(None, raw=huge))
    assert updater.check_update_status(MANIFEST_URL, "8.6.23") is None


# -- Hallazgo #12: el instalador se recomprueba justo antes de abrirlo ------


def test_file_matches_sha256_is_true_for_the_expected_content(tmp_path):
    exe = tmp_path / "setup.exe"
    exe.write_bytes(b"instalador legitimo")

    assert updater.file_matches_sha256(exe, hashlib.sha256(b"instalador legitimo").hexdigest())


def test_file_matches_sha256_ignores_hash_case(tmp_path):
    exe = tmp_path / "setup.exe"
    exe.write_bytes(b"abc")

    assert updater.file_matches_sha256(exe, hashlib.sha256(b"abc").hexdigest().upper())


def test_file_matches_sha256_is_false_when_the_file_was_replaced(tmp_path):
    exe = tmp_path / "setup.exe"
    exe.write_bytes(b"instalador legitimo")
    esperado = hashlib.sha256(b"instalador legitimo").hexdigest()

    exe.write_bytes(b"otro programa")

    assert not updater.file_matches_sha256(exe, esperado)


def test_file_matches_sha256_is_false_for_a_missing_file(tmp_path):
    assert not updater.file_matches_sha256(tmp_path / "no_existe.exe", "a" * 64)


def test_file_matches_sha256_is_false_for_a_directory(tmp_path):
    assert not updater.file_matches_sha256(tmp_path, "a" * 64)


@pytest.mark.parametrize("malformado", [None, "", "abc", "z" * 64, "a" * 63])
def test_file_matches_sha256_is_false_for_a_malformed_expected_hash(tmp_path, malformado):
    exe = tmp_path / "setup.exe"
    exe.write_bytes(b"abc")

    assert not updater.file_matches_sha256(exe, malformado)


def test_file_matches_sha256_reads_large_files_in_chunks(tmp_path):
    exe = tmp_path / "grande.exe"
    contenido = b"x" * (3 * 1024 * 1024 + 17)
    exe.write_bytes(contenido)

    assert updater.file_matches_sha256(exe, hashlib.sha256(contenido).hexdigest())


# -- Hallazgo N5: la respuesta HTTP del instalador siempre se cierra --------


class _FailingBodyResponse(_Response):
    def iter_content(self, chunk_size):
        yield self.payload
        raise OSError("conexion cortada a mitad de la descarga")


class _HttpErrorResponse(_Response):
    def raise_for_status(self):
        raise RuntimeError("HTTP 500")


def _download(tmp_path, response, **kwargs):
    manifest = _signing.signed_manifest(b"good", filename="setup.exe")
    return download_verified_update(
        manifest, tmp_path, request_get=lambda *args, **kw: response, **kwargs
    )


def test_response_is_closed_after_a_successful_download(tmp_path, trusted_update_key):
    respuesta = _Response(b"good")

    _download(tmp_path, respuesta)

    assert respuesta.closed


def test_response_is_closed_when_the_size_limit_is_exceeded(tmp_path, trusted_update_key):
    respuesta = _Response(b"good")

    with pytest.raises(ValueError, match="tamaño"):
        _download(tmp_path, respuesta, max_bytes=2)

    assert respuesta.closed


def test_response_is_closed_when_the_checksum_does_not_match(tmp_path, trusted_update_key):
    respuesta = _Response(b"bad")

    with pytest.raises(ValueError, match="SHA-256"):
        _download(tmp_path, respuesta)

    assert respuesta.closed


def test_response_is_closed_when_the_body_fails_midway(tmp_path, trusted_update_key):
    respuesta = _FailingBodyResponse(b"go")

    with pytest.raises(OSError):
        _download(tmp_path, respuesta)

    assert respuesta.closed
    assert list(tmp_path.iterdir()) == []


def test_response_is_closed_when_the_status_is_an_error(tmp_path, trusted_update_key):
    respuesta = _HttpErrorResponse(b"good")

    with pytest.raises(RuntimeError):
        _download(tmp_path, respuesta)

    assert respuesta.closed
