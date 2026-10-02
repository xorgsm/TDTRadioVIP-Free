"""
tools/sign_manifest.py: herramienta del autor para generar la clave y firmar.

Lo critico: la clave privada jamas acaba dentro del repositorio ni se pisa
una existente, y un manifiesto firmado por la herramienta es exactamente el
que la app acepta (mismos campos, misma normalizacion).
"""
import base64
import importlib.util
import json
import os
import subprocess
from pathlib import Path

import pytest

pytest.importorskip("cryptography")

import _signing  # noqa: E402
from core import update_signature, updater  # noqa: E402

_SPEC = importlib.util.spec_from_file_location(
    "sign_manifest",
    Path(__file__).resolve().parent.parent / "tools" / "sign_manifest.py",
)
sign_manifest = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(sign_manifest)

SigningError = sign_manifest.SigningError

MANIFEST = {
    "version": "8.7.0",
    "download_url": "https://updates.test/TDTRadioVIP_Setup_v8.7.0.exe",
    "sha256": "a" * 64,
}


@pytest.fixture
def keys(tmp_path, monkeypatch):
    """Clave recien generada e instalada como clave embebida de la app."""
    modulus_b64 = sign_manifest.generate_keypair(tmp_path / "claves")
    monkeypatch.setattr(update_signature, "UPDATE_PUBLIC_KEY_N_B64", modulus_b64)
    return tmp_path / "claves" / sign_manifest.KEY_FILENAME


def _write_manifest(tmp_path, data=None):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(MANIFEST if data is None else data), encoding="utf-8")
    return path


def test_keygen_writes_the_private_key_and_returns_the_public_modulus(tmp_path):
    modulus_b64 = sign_manifest.generate_keypair(tmp_path / "claves")

    assert (tmp_path / "claves" / sign_manifest.KEY_FILENAME).is_file()
    assert len(base64.b64decode(modulus_b64)) == 256


def test_keygen_refuses_to_write_inside_the_repository():
    destino = sign_manifest.REPO_ROOT / "claves_no_deben_existir"

    with pytest.raises(SigningError, match="repositorio"):
        sign_manifest.generate_keypair(destino)

    assert not destino.exists()


def test_keygen_never_overwrites_an_existing_key(tmp_path):
    sign_manifest.generate_keypair(tmp_path / "claves")
    antes = (tmp_path / "claves" / sign_manifest.KEY_FILENAME).read_bytes()

    with pytest.raises(SigningError, match="no se sobrescribe"):
        sign_manifest.generate_keypair(tmp_path / "claves")

    assert (tmp_path / "claves" / sign_manifest.KEY_FILENAME).read_bytes() == antes


def test_a_manifest_signed_by_the_tool_is_accepted_by_the_app(tmp_path, keys):
    manifest = _write_manifest(tmp_path)

    sign_manifest.sign_manifest_file(keys, manifest)

    firmado = json.loads(manifest.read_text(encoding="utf-8"))
    assert len(firmado["signature"]) == 512
    assert updater.has_valid_signature(firmado) is True
    assert firmado["sha256"] == MANIFEST["sha256"]  # no toca el resto


def test_a_numeric_version_is_signed_the_same_way_the_app_reads_it(tmp_path, keys):
    manifest = _write_manifest(tmp_path, {**MANIFEST, "version": 8.7})

    sign_manifest.sign_manifest_file(keys, manifest)

    assert updater.has_valid_signature(json.loads(manifest.read_text(encoding="utf-8"))) is True


def test_a_url_with_query_string_is_signed_over_the_bare_filename(tmp_path, keys):
    datos = {**MANIFEST, "download_url": MANIFEST["download_url"] + "?download=1"}
    manifest = _write_manifest(tmp_path, datos)

    sign_manifest.sign_manifest_file(keys, manifest)

    assert updater.has_valid_signature(json.loads(manifest.read_text(encoding="utf-8"))) is True


def test_signing_fails_when_the_embedded_public_key_does_not_match(tmp_path, keys, monkeypatch):
    """Si el autor olvido pegar su clave publica en la app, el manifiesto
    firmado seria rechazado por todas las instalaciones: se avisa antes."""
    monkeypatch.setattr(update_signature, "UPDATE_PUBLIC_KEY_N_B64", _signing.public_modulus_b64())
    manifest = _write_manifest(tmp_path)
    antes = manifest.read_text(encoding="utf-8")

    with pytest.raises(SigningError, match="no coincide"):
        sign_manifest.sign_manifest_file(keys, manifest)

    assert manifest.read_text(encoding="utf-8") == antes


@pytest.mark.parametrize("cambio,mensaje", [
    ({"version": ""}, "version"),
    ({"download_url": "http://updates.test/Setup.exe"}, "HTTPS"),
    ({"sha256": "123"}, "SHA-256"),
    ({"download_url": "https://updates.test/Setup.zip"}, "EXE"),
])
def test_signing_rejects_invalid_manifests(tmp_path, keys, cambio, mensaje):
    manifest = _write_manifest(tmp_path, {**MANIFEST, **cambio})

    with pytest.raises(SigningError, match=mensaje):
        sign_manifest.sign_manifest_file(keys, manifest)


def test_signing_rejects_a_manifest_that_is_not_json_object(tmp_path, keys):
    manifest = tmp_path / "manifest.json"
    manifest.write_text("[1, 2]", encoding="utf-8")

    with pytest.raises(SigningError, match="objeto JSON"):
        sign_manifest.sign_manifest_file(keys, manifest)


def test_signing_rejects_a_missing_or_invalid_key(tmp_path):
    manifest = _write_manifest(tmp_path)

    with pytest.raises(SigningError, match="clave privada"):
        sign_manifest.sign_manifest_file(tmp_path / "no_existe.pem", manifest)


def test_main_returns_nonzero_and_writes_to_stderr_on_error(tmp_path, capsys):
    manifest = _write_manifest(tmp_path)

    codigo = sign_manifest.main(
        ["sign", "--key", str(tmp_path / "no_existe.pem"), "--manifest", str(manifest)]
    )

    assert codigo == 2
    assert "Error" in capsys.readouterr().err


def test_main_keygen_prints_the_public_key_but_never_the_private_one(tmp_path, capsys):
    codigo = sign_manifest.main(["keygen", "--out", str(tmp_path / "claves")])

    salida = capsys.readouterr().out
    assert codigo == 0
    assert "UPDATE_PUBLIC_KEY_N_B64" in salida
    assert "PRIVATE KEY" not in salida


@pytest.mark.skipif(os.name != "nt", reason="las ACL de archivo son cosa de Windows")
def test_keygen_leaves_the_private_key_readable_only_by_the_current_user(tmp_path):
    """En Windows 0o600 no toca la ACL: la clave heredaria los permisos de la
    carpeta (a menudo legible por todos los usuarios locales). Debe quedar
    una sola entrada de acceso, sin herencia."""
    sign_manifest.generate_keypair(tmp_path / "claves")
    key_path = tmp_path / "claves" / sign_manifest.KEY_FILENAME

    listado = subprocess.run(
        ["icacls", str(key_path)], capture_output=True, text=True, check=True
    ).stdout

    assert listado.count(":(") == 1
    assert "(I)" not in listado


@pytest.mark.skipif(os.name != "nt", reason="las ACL de archivo son cosa de Windows")
def test_keygen_leaves_no_key_behind_if_it_cannot_restrict_the_acl(tmp_path, monkeypatch):
    monkeypatch.setattr(
        sign_manifest.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 1, "", "denegado"),
    )

    with pytest.raises(SigningError, match="permisos"):
        sign_manifest.generate_keypair(tmp_path / "claves")

    assert not (tmp_path / "claves" / sign_manifest.KEY_FILENAME).exists()
