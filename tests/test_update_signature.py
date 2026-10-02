"""
Verificacion de la firma del manifiesto de actualizaciones.

La firma es lo unico que impide que quien comprometa la release de GitHub
cambie a la vez el instalador y su SHA-256. Estos tests fijan que solo una
firma hecha con la clave privada sobre (version, nombre, sha256) verifica, y
que ante cualquier duda la respuesta es "no verifica", nunca una excepcion.
"""
import base64
import hashlib

import pytest

import _signing
from core import update_signature
from core.update_signature import normalize_version, signed_message, verify_signature

VERSION = "8.7.0"
FILENAME = "TDTRadioVIP_Setup_v8.7.0.exe"
SHA = "a" * 64


@pytest.fixture
def signature(trusted_update_key):
    return _signing.sign(VERSION, FILENAME, SHA)


def test_a_valid_signature_verifies(signature):
    assert verify_signature(VERSION, FILENAME, SHA, signature) is True


@pytest.mark.parametrize("version,filename,sha256", [
    ("8.7.1", FILENAME, SHA),
    (VERSION, "Otro_Setup.exe", SHA),
    (VERSION, FILENAME, "b" * 64),
])
def test_changing_any_signed_field_invalidates_the_signature(signature, version, filename, sha256):
    assert verify_signature(version, filename, sha256, signature) is False


def test_uppercase_hex_signature_still_verifies(signature):
    assert verify_signature(VERSION, FILENAME, SHA, signature.upper()) is True


@pytest.mark.parametrize("bad", [
    "",
    None,
    123,
    ["aa"],
    "zz" * 256,        # no es hexadecimal
    "aa" * 255,        # 255 bytes
    "aa" * 257,        # 257 bytes
    " " + "aa" * 256,  # espacio delante: bytes.fromhex lo toleraria
])
def test_malformed_signatures_do_not_verify_and_do_not_raise(trusted_update_key, bad):
    assert verify_signature(VERSION, FILENAME, SHA, bad) is False


def test_a_signature_larger_than_the_modulus_does_not_verify(trusted_update_key):
    assert verify_signature(VERSION, FILENAME, SHA, "ff" * 256) is False


def test_loose_padding_with_trailing_garbage_does_not_verify(trusted_update_key):
    """Invariante de Bleichenbacher: se compara el bloque completo, no un
    prefijo. Un bloque con el DigestInfo correcto seguido de basura debe
    rechazarse aunque la operacion RSA sea valida."""
    message = signed_message(VERSION, FILENAME, SHA)
    digest_info = update_signature._SHA256_DER_PREFIX + hashlib.sha256(message).digest()
    relleno = b"\xff" * 8
    block = b"\x00\x01" + relleno + b"\x00" + digest_info
    block = block + b"garbage" + b"\x00" * (256 - len(block) - 7)
    assert len(block) == 256
    assert verify_signature(VERSION, FILENAME, SHA, _signing.raw_sign(block)) is False


def test_a_signature_made_over_another_domain_prefix_does_not_verify(trusted_update_key):
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding

    otro = f"OtroProposito\n{VERSION}\n{FILENAME}\n{SHA}".encode("utf-8")
    firma = _signing.private_key().sign(otro, padding.PKCS1v15(), hashes.SHA256()).hex()
    assert verify_signature(VERSION, FILENAME, SHA, firma) is False


@pytest.mark.parametrize("campo", [
    ("8.7.0\n9.9.9", FILENAME, SHA),
    (VERSION, "a\rb.exe", SHA),
    (VERSION, FILENAME, SHA + "\n"),
])
def test_fields_with_line_breaks_are_rejected(signature, campo):
    with pytest.raises(ValueError):
        signed_message(*campo)
    assert verify_signature(*campo, signature) is False


@pytest.mark.parametrize("n_b64", [
    "",                                       # sin configurar
    "esto no es base64!!",                    # base64 invalido
    base64.b64encode(b"\x01" * 128).decode(),  # modulo de 1024 bits
    base64.b64encode(b"\x01" * 300).decode(),  # modulo de 2400 bits
])
def test_a_misconfigured_public_key_fails_closed(monkeypatch, n_b64):
    """Sin clave valida la app no acepta ninguna actualizacion descargable,
    y tampoco se cae por ello."""
    firma = _signing.sign(VERSION, FILENAME, SHA)
    monkeypatch.setattr(update_signature, "UPDATE_PUBLIC_KEY_N_B64", n_b64)
    assert verify_signature(VERSION, FILENAME, SHA, firma) is False


def test_an_explicit_modulus_overrides_the_embedded_key():
    firma = _signing.sign(VERSION, FILENAME, SHA)
    assert verify_signature(
        VERSION, FILENAME, SHA, firma, modulus=_signing.public_modulus()
    ) is True


def test_the_shipped_public_key_is_not_the_test_key():
    """Los tests nunca deben depender de (ni filtrar) la clave real."""
    assert update_signature.UPDATE_PUBLIC_KEY_N_B64 != _signing.public_modulus_b64()


@pytest.mark.parametrize("valor,esperado", [
    ("8.7.0", "8.7.0"),
    ("  8.7.0 ", "8.7.0"),
    (8.7, "8.7"),
    (None, ""),
    (0, ""),
])
def test_normalize_version(valor, esperado):
    assert normalize_version(valor) == esperado
