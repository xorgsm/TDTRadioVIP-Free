"""Verificacion de la firma del manifiesto de actualizaciones.

El SHA-256 del instalador viaja en el mismo manifiesto que su URL, asi que
quien comprometa la release de GitHub cambia ambos a la vez. La firma RSA,
hecha con una clave privada que no esta en GitHub, es lo que prueba que el
manifiesto lo publico el autor. Se verifica en Python puro, con la clave
publica embebida, para no anadir dependencias a la app.

La clave es distinta de la de licencias (core/license.py): reutilizarla
permitiria a quien firme actualizaciones generar licencias validas.
"""
import base64
import binascii
import hashlib
import hmac

from core.logger import get_logger

log = get_logger(__name__)

# Modulo RSA-2048 en base64. Vacio hasta que el autor genere su clave con
# `python tools/sign_manifest.py keygen` y pegue aqui la clave publica; mientras
# este vacio la verificacion falla cerrado y la app no acepta descargas.
UPDATE_PUBLIC_KEY_N_B64 = ""
UPDATE_PUBLIC_KEY_E = 65537

SIGNATURE_BYTES = 256
_MODULUS_BITS = 2048
_DOMAIN = "TDTRadioVIP-update-v2"
_SHA256_DER_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")


def normalize_version(value: object) -> str:
    """Version tal y como se firma: texto sin espacios alrededor."""
    return str(value or "").strip()


def signed_message(version: str, filename: str, sha256: str, download_url: str) -> bytes:
    """Mensaje exacto que se firma. Incluye la URL completa de descarga: sin
    ella, quien controle el manifiesto podria apuntar a otro host conservando
    nombre, hash y firma. Lanza ValueError si algun campo lleva saltos de
    linea, que harian ambiguo el limite entre campos."""
    for field in (version, filename, sha256, download_url):
        if "\n" in field or "\r" in field:
            raise ValueError("Los campos firmados no pueden contener saltos de línea.")
    return "\n".join((_DOMAIN, version, filename, sha256, download_url)).encode("utf-8")


def _embedded_modulus() -> int | None:
    if not UPDATE_PUBLIC_KEY_N_B64:
        log.warning("No hay clave pública de actualizaciones configurada")
        return None
    try:
        return int.from_bytes(base64.b64decode(UPDATE_PUBLIC_KEY_N_B64, validate=True), "big")
    except (binascii.Error, ValueError):
        log.warning("La clave pública de actualizaciones no es base64 válido")
        return None


def verify_signature(
    version: str,
    filename: str,
    sha256: str,
    download_url: str,
    signature_hex: object,
    *,
    modulus: int | None = None,
) -> bool:
    """True solo si `signature_hex` es la firma del autor sobre los cuatro campos.

    Nunca lanza: ante cualquier entrada rara o clave mal configurada devuelve
    False. `modulus` permite a la herramienta de firma verificar con la clave
    que acaba de usar; por defecto se usa la clave embebida en la app.
    """
    if modulus is None:
        modulus = _embedded_modulus()
    if modulus is None or modulus.bit_length() != _MODULUS_BITS:
        return False
    if not isinstance(signature_hex, str) or len(signature_hex) != SIGNATURE_BYTES * 2:
        return False
    try:
        signature = bytes.fromhex(signature_hex)
        message = signed_message(version, filename, sha256, download_url)
    except ValueError:
        return False
    value = int.from_bytes(signature, "big")
    if value >= modulus:
        return False
    decoded = pow(value, UPDATE_PUBLIC_KEY_E, modulus).to_bytes(SIGNATURE_BYTES, "big")
    digest_info = _SHA256_DER_PREFIX + hashlib.sha256(message).digest()
    expected = b"\x00\x01" + b"\xff" * (SIGNATURE_BYTES - len(digest_info) - 3) + b"\x00" + digest_info
    # Se compara el bloque completo de 256 bytes, nunca un prefijo: es la
    # invariante que evita el ataque de Bleichenbacher (ver core/license.py).
    return hmac.compare_digest(decoded, expected)
