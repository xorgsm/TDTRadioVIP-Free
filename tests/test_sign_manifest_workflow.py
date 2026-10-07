"""
tools/sign_manifest.py: flujo de release (clave con contrasena, clave publica
embebida, `make` y `verify`).

Lo critico: una clave cifrada nunca se usa sin su contrasena, la clave publica
embebida no se pisa por accidente (dejaria sin verificar a las versiones ya
instaladas) y un manifiesto generado por `make` es el que la app acepta.
"""
import base64
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

pytest.importorskip("cryptography")

from core import update_signature, updater  # noqa: E402

_SPEC = importlib.util.spec_from_file_location(
    "sign_manifest_workflow",
    Path(__file__).resolve().parent.parent / "tools" / "sign_manifest.py",
)
sm = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(sm)

SigningError = sm.SigningError
PASSPHRASE = "contraseña de prueba"
INSTALLER_NAME = "TDTRadioVIP_Setup_v8.7.0.exe"
EMPTY_MODULE = 'import x\nUPDATE_PUBLIC_KEY_N_B64 = ""\nUPDATE_PUBLIC_KEY_E = 65537\n'


@pytest.fixture(autouse=True)
def isolated_embed_target(tmp_path, monkeypatch):
    """Ningun test puede escribir en el core/update_signature.py real."""
    monkeypatch.setattr(sm, "UPDATE_SIGNATURE_PATH", tmp_path / "update_signature.py")


@pytest.fixture
def plain_key(tmp_path, monkeypatch):
    modulus_b64 = sm.generate_keypair(tmp_path / "claves")
    monkeypatch.setattr(update_signature, "UPDATE_PUBLIC_KEY_N_B64", modulus_b64)
    return tmp_path / "claves" / sm.KEY_FILENAME


@pytest.fixture
def locked_key(tmp_path, monkeypatch):
    modulus_b64 = sm.generate_keypair(tmp_path / "claves", passphrase=PASSPHRASE)
    monkeypatch.setattr(update_signature, "UPDATE_PUBLIC_KEY_N_B64", modulus_b64)
    return tmp_path / "claves" / sm.KEY_FILENAME


@pytest.fixture
def installer(tmp_path):
    path = tmp_path / INSTALLER_NAME
    path.write_bytes(b"instalador de prueba")
    return path


def _target(tmp_path, text=EMPTY_MODULE):
    path = tmp_path / "update_signature.py"
    path.write_text(text, encoding="utf-8")
    return path


# --- clave con contrasena --------------------------------------------------

def test_a_passphrase_encrypts_the_private_key_on_disk(locked_key):
    contenido = locked_key.read_bytes()

    assert b"ENCRYPTED PRIVATE KEY" in contenido


def test_a_manifest_can_be_signed_with_a_locked_key_and_its_passphrase(
    tmp_path, locked_key
):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({
            "version": "8.7.0",
            "download_url": f"https://updates.test/{INSTALLER_NAME}",
            "sha256": "a" * 64,
        }),
        encoding="utf-8",
    )

    sm.sign_manifest_file(locked_key, manifest, passphrase=PASSPHRASE)

    firmado = json.loads(manifest.read_text(encoding="utf-8"))
    assert updater.has_valid_signature(firmado) is True


def test_a_locked_key_without_passphrase_is_rejected_with_a_clear_message(
    tmp_path, locked_key
):
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}", encoding="utf-8")

    with pytest.raises(SigningError, match="contraseña"):
        sm.sign_manifest_file(locked_key, manifest)


def test_a_wrong_passphrase_is_rejected(tmp_path, locked_key):
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}", encoding="utf-8")

    with pytest.raises(SigningError, match="contraseña"):
        sm.sign_manifest_file(locked_key, manifest, passphrase="otra")


def test_an_unlocked_key_still_signs_without_passphrase(tmp_path, plain_key):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({
            "version": "8.7.0",
            "download_url": f"https://updates.test/{INSTALLER_NAME}",
            "sha256": "b" * 64,
        }),
        encoding="utf-8",
    )

    sm.sign_manifest_file(plain_key, manifest)

    assert updater.has_valid_signature(json.loads(manifest.read_text(encoding="utf-8")))


# --- clave publica embebida -------------------------------------------------

def test_embedding_writes_the_public_key_into_the_module(tmp_path):
    target = _target(tmp_path)
    modulus_b64 = sm.generate_keypair(tmp_path / "claves")

    sm.embed_public_key(modulus_b64, target)

    texto = target.read_text(encoding="utf-8")
    assert f'UPDATE_PUBLIC_KEY_N_B64 = "{modulus_b64}"' in texto
    assert "import x" in texto and "UPDATE_PUBLIC_KEY_E = 65537" in texto  # resto intacto


def test_embedding_refuses_to_replace_an_existing_key(tmp_path):
    target = _target(tmp_path, 'UPDATE_PUBLIC_KEY_N_B64 = "AAAA"\n')
    antes = target.read_text(encoding="utf-8")
    modulus_b64 = sm.generate_keypair(tmp_path / "claves")

    with pytest.raises(SigningError, match="ya tiene una clave"):
        sm.embed_public_key(modulus_b64, target)

    assert target.read_text(encoding="utf-8") == antes


def test_embedding_replaces_an_existing_key_only_when_asked(tmp_path):
    target = _target(tmp_path, 'UPDATE_PUBLIC_KEY_N_B64 = "AAAA"\n')
    modulus_b64 = sm.generate_keypair(tmp_path / "claves")

    sm.embed_public_key(modulus_b64, target, replace=True)

    assert f'"{modulus_b64}"' in target.read_text(encoding="utf-8")


def test_embedding_fails_when_the_constant_is_missing(tmp_path):
    target = _target(tmp_path, "nada = 1\n")
    modulus_b64 = sm.generate_keypair(tmp_path / "claves")

    with pytest.raises(SigningError, match="UPDATE_PUBLIC_KEY_N_B64"):
        sm.embed_public_key(modulus_b64, target)


def test_embedding_rejects_a_modulus_that_is_not_2048_bits(tmp_path):
    target = _target(tmp_path)

    with pytest.raises(SigningError, match="2048"):
        sm.embed_public_key("AAAA", target)

    assert 'UPDATE_PUBLIC_KEY_N_B64 = ""' in target.read_text(encoding="utf-8")


def test_keygen_command_embeds_the_key_and_creates_a_locked_key(
    tmp_path, monkeypatch, capsys
):
    target = _target(tmp_path)
    monkeypatch.setattr(sm, "UPDATE_SIGNATURE_PATH", target)
    monkeypatch.setattr(sm.getpass, "getpass", lambda prompt="": PASSPHRASE)

    codigo = sm.main(["keygen", "--out", str(tmp_path / "claves")])

    key = tmp_path / "claves" / sm.KEY_FILENAME
    assert codigo == 0
    assert b"ENCRYPTED PRIVATE KEY" in key.read_bytes()
    assert 'UPDATE_PUBLIC_KEY_N_B64 = ""' not in target.read_text(encoding="utf-8")
    assert "PRIVATE KEY" not in capsys.readouterr().out


def test_keygen_command_stops_before_creating_a_key_if_embedding_is_not_allowed(
    tmp_path, monkeypatch, capsys
):
    target = _target(tmp_path, 'UPDATE_PUBLIC_KEY_N_B64 = "AAAA"\n')
    monkeypatch.setattr(sm, "UPDATE_SIGNATURE_PATH", target)

    codigo = sm.main(["keygen", "--out", str(tmp_path / "claves"), "--no-passphrase"])

    assert codigo == 2
    assert not (tmp_path / "claves" / sm.KEY_FILENAME).exists()
    assert "ya tiene una clave" in capsys.readouterr().err


def test_keygen_command_rejects_mismatched_passphrase_confirmation(
    tmp_path, monkeypatch, capsys
):
    target = _target(tmp_path)
    monkeypatch.setattr(sm, "UPDATE_SIGNATURE_PATH", target)
    respuestas = iter(["una", "otra"])
    monkeypatch.setattr(sm.getpass, "getpass", lambda prompt="": next(respuestas))

    codigo = sm.main(["keygen", "--out", str(tmp_path / "claves")])

    assert codigo == 2
    assert not (tmp_path / "claves" / sm.KEY_FILENAME).exists()
    assert "no coinciden" in capsys.readouterr().err


def test_keygen_command_no_passphrase_flag_creates_an_unlocked_key(tmp_path, monkeypatch):
    target = _target(tmp_path)
    monkeypatch.setattr(sm, "UPDATE_SIGNATURE_PATH", target)

    codigo = sm.main(["keygen", "--out", str(tmp_path / "claves"), "--no-passphrase"])

    key = tmp_path / "claves" / sm.KEY_FILENAME
    assert codigo == 0
    assert b"ENCRYPTED" not in key.read_bytes()


# --- make -------------------------------------------------------------------

def test_make_builds_a_signed_manifest_the_app_accepts(tmp_path, plain_key, installer):
    ruta = sm.build_manifest(plain_key, installer, version="8.7.0")

    datos = json.loads(ruta.read_text(encoding="utf-8"))
    assert ruta == installer.parent / "manifest.json"
    assert datos["version"] == "8.7.0"
    assert datos["sha256"] == hashlib.sha256(installer.read_bytes()).hexdigest()
    assert datos["download_url"] == (
        f"https://github.com/xorgsm/TDTRadioVIP-Free/releases/download/v8.7.0/{INSTALLER_NAME}"
    )
    assert updater.has_valid_signature(datos) is True
    assert updater.validate_download_manifest(datos)


def test_make_defaults_the_version_to_the_app_version(tmp_path, plain_key, monkeypatch):
    monkeypatch.setattr(sm, "APP_VERSION", "8.9.1")
    instalador = tmp_path / "TDTRadioVIP_Setup_v8.9.1.exe"
    instalador.write_bytes(b"x")

    ruta = sm.build_manifest(plain_key, instalador)

    assert json.loads(ruta.read_text(encoding="utf-8"))["version"] == "8.9.1"


def test_make_works_with_a_locked_key(tmp_path, locked_key, installer):
    ruta = sm.build_manifest(locked_key, installer, version="8.7.0", passphrase=PASSPHRASE)

    assert updater.has_valid_signature(json.loads(ruta.read_text(encoding="utf-8")))


def test_make_rejects_a_missing_installer(tmp_path, plain_key):
    with pytest.raises(SigningError, match="instalador"):
        sm.build_manifest(plain_key, tmp_path / "no_existe.exe", version="8.7.0")


def test_make_rejects_an_installer_that_is_not_an_exe(tmp_path, plain_key):
    zip_ = tmp_path / "setup.zip"
    zip_.write_bytes(b"x")

    with pytest.raises(SigningError, match="EXE"):
        sm.build_manifest(plain_key, zip_, version="8.7.0")


def test_make_keeps_an_existing_manifest_if_signing_fails(
    tmp_path, locked_key, installer
):
    previo = installer.parent / "manifest.json"
    previo.write_text('{"previo": true}', encoding="utf-8")

    with pytest.raises(SigningError, match="contraseña"):
        sm.build_manifest(locked_key, installer, version="8.7.0", passphrase="otra")

    assert previo.read_text(encoding="utf-8") == '{"previo": true}'
    assert [p.name for p in installer.parent.glob("manifest*")] == ["manifest.json"]


def test_make_rejects_an_installer_whose_name_is_not_the_expected_one(
    tmp_path, plain_key, installer
):
    with pytest.raises(SigningError, match="debe llamarse"):
        sm.build_manifest(plain_key, installer, version="8.7.0.1")

    assert not (installer.parent / "manifest.json").exists()


def test_make_rejects_an_installer_name_that_would_break_the_download_url(
    tmp_path, plain_key
):
    raro = tmp_path / "Setup v8.7.0 #1.exe"
    raro.write_bytes(b"x")

    with pytest.raises(SigningError, match="nombre del instalador"):
        sm.build_manifest(plain_key, raro, version="8.7.0")


def test_make_does_not_leave_a_manifest_if_signing_fails(tmp_path, plain_key, installer, monkeypatch):
    monkeypatch.setattr(update_signature, "UPDATE_PUBLIC_KEY_N_B64", "")

    with pytest.raises(SigningError):
        sm.build_manifest(plain_key, installer, version="8.7.0")

    assert not (installer.parent / "manifest.json").exists()


def test_make_command_writes_the_manifest_and_prints_its_path(
    tmp_path, plain_key, installer, capsys
):
    codigo = sm.main(
        ["make", "--key", str(plain_key), "--installer", str(installer), "--version", "8.7.0"]
    )

    assert codigo == 0
    assert (installer.parent / "manifest.json").is_file()
    assert "manifest.json" in capsys.readouterr().out


def test_make_command_reads_the_passphrase_from_the_environment(
    tmp_path, locked_key, installer, monkeypatch
):
    monkeypatch.setenv(sm.PASSPHRASE_ENV, PASSPHRASE)

    codigo = sm.main(
        ["make", "--key", str(locked_key), "--installer", str(installer), "--version", "8.7.0"]
    )

    assert codigo == 0


def test_sign_command_asks_for_the_passphrase_only_when_the_key_is_locked(
    tmp_path, locked_key, monkeypatch
):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({
            "version": "8.7.0",
            "download_url": f"https://updates.test/{INSTALLER_NAME}",
            "sha256": "c" * 64,
        }),
        encoding="utf-8",
    )
    monkeypatch.delenv(sm.PASSPHRASE_ENV, raising=False)
    monkeypatch.setattr(sm.getpass, "getpass", lambda prompt="": PASSPHRASE)

    codigo = sm.main(["sign", "--key", str(locked_key), "--manifest", str(manifest)])

    assert codigo == 0
    assert updater.has_valid_signature(json.loads(manifest.read_text(encoding="utf-8")))


# --- verify -----------------------------------------------------------------

@pytest.fixture
def signed_manifest_file(tmp_path, plain_key, installer):
    return sm.build_manifest(plain_key, installer, version="8.7.0")


def test_verify_accepts_a_valid_local_manifest(signed_manifest_file):
    datos = sm.verify_manifest(str(signed_manifest_file))

    assert datos["version"] == "8.7.0"


def test_verify_checks_the_installer_hash_when_given(signed_manifest_file, installer):
    sm.verify_manifest(str(signed_manifest_file), installer=installer)  # no lanza

    installer.write_bytes(b"instalador manipulado")
    with pytest.raises(SigningError, match="SHA-256"):
        sm.verify_manifest(str(signed_manifest_file), installer=installer)


def test_verify_rejects_a_tampered_manifest(signed_manifest_file):
    datos = json.loads(signed_manifest_file.read_text(encoding="utf-8"))
    datos["sha256"] = "d" * 64
    signed_manifest_file.write_text(json.dumps(datos), encoding="utf-8")

    with pytest.raises(SigningError, match="firma"):
        sm.verify_manifest(str(signed_manifest_file))


def test_verify_rejects_an_unsigned_manifest(tmp_path):
    ruta = tmp_path / "manifest.json"
    ruta.write_text(
        json.dumps({
            "version": "8.7.0",
            "download_url": f"https://updates.test/{INSTALLER_NAME}",
            "sha256": "a" * 64,
        }),
        encoding="utf-8",
    )

    with pytest.raises(SigningError, match="firma"):
        sm.verify_manifest(str(ruta))


def test_verify_downloads_an_https_url(signed_manifest_file, monkeypatch):
    texto = signed_manifest_file.read_text(encoding="utf-8")
    pedidos = []
    monkeypatch.setattr(sm, "_fetch_manifest_text", lambda url: pedidos.append(url) or texto)

    datos = sm.verify_manifest("https://github.com/x/releases/latest/download/manifest.json")

    assert datos["version"] == "8.7.0"
    assert pedidos == ["https://github.com/x/releases/latest/download/manifest.json"]


def test_verify_refuses_plain_http_urls(monkeypatch):
    monkeypatch.setattr(sm, "_fetch_manifest_text", lambda url: pytest.fail("no debe descargar"))

    with pytest.raises(SigningError, match="HTTPS"):
        sm.verify_manifest("http://example.test/manifest.json")


def test_verify_rejects_a_missing_file(tmp_path):
    with pytest.raises(SigningError, match="manifiesto"):
        sm.verify_manifest(str(tmp_path / "no_existe.json"))


def test_verify_rejects_invalid_json(tmp_path):
    ruta = tmp_path / "manifest.json"
    ruta.write_text("{no es json", encoding="utf-8")

    with pytest.raises(SigningError, match="manifiesto"):
        sm.verify_manifest(str(ruta))


def test_verify_command_returns_zero_for_a_valid_manifest(signed_manifest_file, capsys):
    codigo = sm.main(["verify", str(signed_manifest_file)])

    assert codigo == 0
    assert "8.7.0" in capsys.readouterr().out


def test_verify_command_returns_two_for_an_invalid_manifest(tmp_path, capsys):
    ruta = tmp_path / "manifest.json"
    ruta.write_text("[]", encoding="utf-8")

    codigo = sm.main(["verify", str(ruta)])

    assert codigo == 2
    assert "Error" in capsys.readouterr().err


def test_fetch_manifest_text_caps_the_response_size(monkeypatch):
    class Respuesta:
        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size):
            yield b"x" * (sm.MAX_MANIFEST_BYTES + 1)

        def close(self):
            pass

    monkeypatch.setattr(sm.requests, "get", lambda *a, **k: Respuesta())

    with pytest.raises(SigningError, match="demasiado grande"):
        sm._fetch_manifest_text("https://example.test/manifest.json")


def test_make_rejects_a_name_that_only_contains_the_version_as_a_substring(
    tmp_path, plain_key
):
    sneaky = tmp_path / "TDTRadioVIP_Setup_v18.7.0.exe"
    sneaky.write_bytes(b"x")

    with pytest.raises(SigningError, match="debe llamarse"):
        sm.build_manifest(plain_key, sneaky, version="8.7.0")


def test_make_refuses_to_overwrite_the_private_key_with_out(plain_key, installer):
    before = plain_key.read_bytes()

    with pytest.raises(SigningError, match="--out"):
        sm.build_manifest(plain_key, installer, version="8.7.0", out_path=plain_key)

    assert plain_key.read_bytes() == before


def test_make_refuses_to_overwrite_the_installer_with_out(plain_key, installer):
    with pytest.raises(SigningError, match="--out"):
        sm.build_manifest(plain_key, installer, version="8.7.0", out_path=installer)

    assert installer.read_bytes() == b"instalador de prueba"


def test_make_requires_a_json_out_path(plain_key, installer, tmp_path):
    with pytest.raises(SigningError, match=".json"):
        sm.build_manifest(
            plain_key, installer, version="8.7.0", out_path=tmp_path / "salida.pem"
        )


def test_verify_reports_a_missing_installer_as_a_signing_error(
    plain_key, installer, tmp_path
):
    manifest = sm.build_manifest(plain_key, installer, version="8.7.0")

    with pytest.raises(SigningError, match="instalador"):
        sm.verify_manifest(str(manifest), tmp_path / "no_existe.exe")


def test_embed_public_key_leaves_the_module_intact_if_the_write_fails(
    tmp_path, monkeypatch
):
    target = tmp_path / "update_signature.py"
    original = 'UPDATE_PUBLIC_KEY_N_B64 = ""' + chr(10)
    target.write_text(original, encoding="utf-8")

    def boom(*_args, **_kwargs):
        raise OSError("disco lleno")

    monkeypatch.setattr(sm.os, "replace", boom)
    with pytest.raises(OSError):
        sm.embed_public_key(base64.b64encode(b"" * 256).decode(), target)

    assert target.read_text(encoding="utf-8") == original
    assert [p.name for p in tmp_path.iterdir()] == ["update_signature.py"]
