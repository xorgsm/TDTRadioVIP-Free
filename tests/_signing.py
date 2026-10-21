"""Claves y firmas de prueba para los tests del manifiesto firmado.

Genera un par RSA-2048 efimero con `cryptography` (dependencia solo de
desarrollo, ver requirements-dev.txt). Nunca se usa la clave real.
"""
import base64
import hashlib

import pytest

pytest.importorskip("cryptography")

from cryptography.hazmat.primitives import hashes  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import padding, rsa  # noqa: E402

from core import update_signature  # noqa: E402

_private_key = None


def private_key():
    global _private_key
    if _private_key is None:
        _private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return _private_key


def public_modulus() -> int:
    return private_key().public_key().public_numbers().n


def public_modulus_b64() -> str:
    return base64.b64encode(public_modulus().to_bytes(256, "big")).decode("ascii")


def sign(version: str, filename: str, sha256: str, download_url: str) -> str:
    message = update_signature.signed_message(version, filename, sha256, download_url)
    return private_key().sign(message, padding.PKCS1v15(), hashes.SHA256()).hex()


def raw_sign(block: bytes) -> str:
    """RSA "en crudo" sobre un bloque de 256 bytes, para fabricar rellenos
    malos que una firma real nunca produciria."""
    exponent = private_key().private_numbers().d
    value = pow(int.from_bytes(block, "big"), exponent, public_modulus())
    return value.to_bytes(256, "big").hex()


def signed_manifest(
    payload: bytes = b"installer",
    *,
    version: str = "8.7.0",
    filename: str = "TDTRadioVIP_Setup_v8.7.0.exe",
    host: str = "https://updates.test",
) -> dict:
    sha256 = hashlib.sha256(payload).hexdigest()
    download_url = f"{host}/{filename}"
    return {
        "version": version,
        "download_url": download_url,
        "sha256": sha256,
        "signature": sign(version, filename, sha256, download_url),
    }
