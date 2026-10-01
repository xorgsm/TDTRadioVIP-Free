# Manifiesto de actualización firmado — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que "Descargar y verificar" solo acepte instaladores cuyo manifiesto lleve una firma RSA-2048 válida, hecha con una clave privada que no está en GitHub.

**Architecture:** Un módulo nuevo `core/update_signature.py` verifica en Python puro (sin dependencias) una firma RSA PKCS#1 v1.5 con SHA-256 sobre `versión + nombre de archivo + sha256`. `core/updater.py` exige esa firma en `validate_download_manifest` y la interfaz solo ofrece la descarga segura si la firma es válida; si no, cae a "abrir la página de descarga". Una herramienta de desarrollo, `tools/sign_manifest.py`, genera la clave y firma el manifiesto al publicar.

**Tech Stack:** Python 3.12, `hashlib`/`hmac` de la librería estándar para verificar; `cryptography` solo como dependencia de desarrollo (tests y herramienta); pytest; PySide6 (controlador de la UI).

**Spec:** `docs/superpowers/specs/2026-10-01-signed-update-manifest-design.md`

## Global Constraints

- Firma: RSA-2048, PKCS#1 v1.5, SHA-256; `signature` en el manifiesto = 256 bytes en hexadecimal (512 caracteres).
- Mensaje firmado, UTF-8 sin salto de línea final: `TDTRadioVIP-update-v1\n<version>\n<filename>\n<sha256>`; `version` con `strip()`, `sha256` en minúsculas, ningún campo con `\n` ni `\r`.
- La app **no** añade dependencias nuevas: la verificación usa `pow()`, `hashlib` y `hmac`. `cryptography` solo va en `requirements-dev.txt` y en el job de CI.
- La verificación compara **el bloque completo de 256 bytes** con `hmac.compare_digest`, nunca un prefijo (misma invariante que `core/license.py`).
- La verificación **falla cerrado**: clave pública sin configurar, mal formada o de tamaño distinto de 2048 bits → `False`, nunca una excepción.
- La clave de actualizaciones es **distinta** de la de `core/license.py`; no se reutiliza.
- La clave privada nunca se escribe dentro del repositorio ni se sobrescribe una existente.
- Los tests usan una clave de prueba efímera; **nunca** la clave real.
- Las versiones ya instaladas no cambian (ignoran `signature`).
- Textos de la interfaz en español, como el resto de la app.
- Comentarios y docstrings en español; cada archivo nuevo empieza con un docstring de módulo corto, como el resto del proyecto.
- Cada commit con mensaje `tipo: descripción` (feat, fix, test, docs, chore), sin `Co-Authored-By`.

## Review Focus

Entradas y fallos que el spec implica pero que ningún test del spec nombra, de más a menos probable. Cada línea tiene su test en la tarea indicada.

- **Clave pública mal configurada** (cadena vacía, base64 inválido, módulo de otro tamaño): debe rechazar la firma sin lanzar excepción → Task 1.
- **`signature` con tipo equivocado** (`null`, número, lista, objeto, cadena vacía): se trata como "no firmado" sin que la app se caiga → Task 2.
- **`signature` en mayúsculas o con espacios alrededor**: un manifiesto editado a mano debe seguir verificando; la app normaliza igual que la herramienta → Task 2.
- **`version` numérica en el JSON** (`8.7` en vez de `"8.7"`) y **URL con query string** (`...exe?download=1`): la app y la herramienta deben normalizar igual el mensaje firmado, o una firma legítima fallaría → Task 2 y Task 4.
- **Firma válida, pero el servidor entrega otros bytes**: sigue fallando por SHA-256 y no deja `.part`; y con firma inválida **no se hace ninguna petición de red** → Task 2.

---

## File Structure

| Archivo | Responsabilidad |
|---|---|
| `core/update_signature.py` (nuevo) | Mensaje firmado y verificación RSA. No sabe nada de manifiestos ni de red. |
| `core/updater.py` (modifica) | Valida el manifiesto (campos + firma) y descarga. Reparte la validación en `validate_manifest_fields` (sin firma, reutilizable) y `validate_download_manifest` (con firma). |
| `ui/update_check_controller.py` (modifica) | Decide si ofrecer descarga segura o abrir la página. |
| `tools/sign_manifest.py` (nuevo) | CLI del autor: `keygen` y `sign`. No lo importa la app. |
| `tests/_signing.py` (nuevo) | Clave RSA efímera y firmas de prueba, con `cryptography`. |
| `tests/conftest.py` (nuevo) | Fixture `trusted_update_key` que instala la clave de prueba como clave de actualizaciones. |
| `tests/test_update_signature.py`, `tests/test_sign_manifest.py` (nuevos), `tests/test_updater_secure.py`, `tests/test_update_check_controller.py` (modifican) | Pruebas. |
| `RELEASE.md`, `requirements-dev.txt`, `.gitignore`, `.github/workflows/ci.yml` (modifican) | Proceso, dependencias de desarrollo, defensa contra subir la clave, CI. |

---

### Task 1: Verificación de firma (`core/update_signature.py`)

**Files:**
- Create: `core/update_signature.py`
- Create: `tests/_signing.py`
- Create: `tests/conftest.py`
- Test: `tests/test_update_signature.py`

**Interfaces:**
- Consumes: nada de tareas anteriores.
- Produces (usadas por Task 2 y Task 4):
  - `core.update_signature.UPDATE_PUBLIC_KEY_N_B64: str` (vacía hasta que el autor la configure) y `UPDATE_PUBLIC_KEY_E: int = 65537`.
  - `normalize_version(value: object) -> str` → `str(value or "").strip()`.
  - `signed_message(version: str, filename: str, sha256: str) -> bytes` (lanza `ValueError` si algún campo contiene `\n`/`\r`).
  - `verify_signature(version: str, filename: str, sha256: str, signature_hex: object, *, modulus: int | None = None) -> bool` (nunca lanza; `modulus=None` usa la clave embebida).
  - `tests/_signing.py`: `private_key()`, `public_modulus_b64() -> str`, `sign(version, filename, sha256) -> str`, `raw_sign(block: bytes) -> str`, `signed_manifest(payload=b"installer", *, version="8.7.0", filename="TDTRadioVIP_Setup_v8.7.0.exe", host="https://updates.test") -> dict`.
  - Fixture `trusted_update_key` (en `tests/conftest.py`).

- [ ] **Step 1: Crear los ayudantes de test (clave y firmas de prueba)**

`tests/_signing.py`:

```python
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


def sign(version: str, filename: str, sha256: str) -> str:
    message = update_signature.signed_message(version, filename, sha256)
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
    return {
        "version": version,
        "download_url": f"{host}/{filename}",
        "sha256": sha256,
        "signature": sign(version, filename, sha256),
    }
```

`tests/conftest.py`:

```python
import pytest


@pytest.fixture
def trusted_update_key(monkeypatch):
    """Instala la clave publica de prueba como clave de actualizaciones."""
    import _signing
    from core import update_signature

    monkeypatch.setattr(
        update_signature, "UPDATE_PUBLIC_KEY_N_B64", _signing.public_modulus_b64()
    )
```

- [ ] **Step 2: Escribir los tests que fallan**

`tests/test_update_signature.py`:

```python
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
```

- [ ] **Step 3: Ejecutar los tests y comprobar que fallan**

Run: `python -m pytest tests/test_update_signature.py -v`
Expected: error de colección `ModuleNotFoundError: No module named 'core.update_signature'` (si falta `cryptography`, instala antes `python -m pip install "cryptography>=42"`).

- [ ] **Step 4: Implementar el módulo**

`core/update_signature.py`:

```python
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
_DOMAIN = "TDTRadioVIP-update-v1"
_SHA256_DER_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")


def normalize_version(value: object) -> str:
    """Version tal y como se firma: texto sin espacios alrededor."""
    return str(value or "").strip()


def signed_message(version: str, filename: str, sha256: str) -> bytes:
    """Mensaje exacto que se firma. Lanza ValueError si algun campo lleva
    saltos de linea, que harian ambiguo el limite entre campos."""
    for field in (version, filename, sha256):
        if "\n" in field or "\r" in field:
            raise ValueError("Los campos firmados no pueden contener saltos de línea.")
    return "\n".join((_DOMAIN, version, filename, sha256)).encode("utf-8")


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
    signature_hex: object,
    *,
    modulus: int | None = None,
) -> bool:
    """True solo si `signature_hex` es la firma del autor sobre los tres campos.

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
        message = signed_message(version, filename, sha256)
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
```

- [ ] **Step 5: Ejecutar los tests y comprobar que pasan**

Run: `python -m pytest tests/test_update_signature.py -v`
Expected: todos PASS.

- [ ] **Step 6: Suite completa y commit**

Run: `python -m pytest -q`
Expected: todo en verde (los tests existentes no se tocan en esta tarea).

```bash
git add core/update_signature.py tests/_signing.py tests/conftest.py tests/test_update_signature.py
git commit -m "feat: verificacion de firma RSA del manifiesto de actualizaciones

Nuevo core/update_signature.py: verifica en Python puro una firma RSA-2048
PKCS#1 v1.5 con SHA-256 sobre version, nombre de archivo y sha256. Compara
el bloque completo y falla cerrado ante una clave sin configurar o mal
formada. Aun no se usa: la integracion llega en la siguiente tarea."
```

---

### Task 2: Exigir firma en el manifiesto (`core/updater.py`)

**Files:**
- Modify: `core/updater.py:14-24` (imports) y `core/updater.py:154-167` (`validate_download_manifest`)
- Modify: `tests/test_updater_secure.py` (tests de descarga existentes + tests nuevos)

**Interfaces:**
- Consumes (Task 1): `normalize_version`, `verify_signature`; en tests `_signing.signed_manifest`, fixture `trusted_update_key`.
- Produces (usadas por Task 3 y Task 4):
  - `validate_manifest_fields(data: dict) -> dict` → `{"download_url": str, "sha256": str, "filename": str}`; lanza `ValueError` ("HTTPS", "SHA-256", "EXE"). Sin mirar la firma.
  - `validate_download_manifest(data: dict) -> dict` → ahora también exige firma válida; lanza `ValueError("El manifiesto no está firmado.")` o `ValueError("La firma del manifiesto no es válida.")`. El dict devuelto incluye `signature` normalizada.
  - `has_valid_signature(data: object) -> bool` (nunca lanza).

- [ ] **Step 1: Adaptar los tests de descarga existentes a manifiestos firmados**

En `tests/test_updater_secure.py`, añade el import `import _signing` junto a los demás imports (tras `import pytest`) y sustituye estos tres tests por las versiones firmadas:

```python
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


def test_invalid_checksum_removes_partial_download(tmp_path, trusted_update_key):
    """Firma valida, pero el servidor entrega otros bytes: sigue fallando por
    SHA-256 y no deja el .part."""
    manifest = _signing.signed_manifest(b"good", filename="setup.exe")
    with pytest.raises(ValueError, match="SHA-256"):
        download_verified_update(
            manifest, tmp_path, request_get=lambda *args, **kwargs: _Response(b"bad")
        )
    assert list(tmp_path.iterdir()) == []
```

(Los tests `test_manifest_rejects_insecure_url` y `test_manifest_rejects_non_web_or_hostless_urls` no cambian: la comprobación HTTPS va antes que la de firma.)

- [ ] **Step 2: Añadir los tests nuevos que fallan**

Añade al final de la sección de tests de manifiesto (antes de `class _ManifestResponse`):

```python
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
    clean = validate_download_manifest(manifest)
    assert clean["filename"] == "TDTRadioVIP_Setup_v8.7.0.exe"


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
```

Los tests de clave sin configurar acceden a `updater.update_signature`, así que `core/updater.py` debe importar ese módulo con `from core import update_signature` (se hace en el Step 4).

- [ ] **Step 3: Ejecutar los tests y comprobar que fallan**

Run: `python -m pytest tests/test_updater_secure.py -v`
Expected: FAIL — `validate_manifest_fields`/`has_valid_signature` no existen y los manifiestos sin firma todavía se aceptan.

- [ ] **Step 4: Implementar en `core/updater.py`**

Imports: sustituye el bloque de imports de `core` por

```python
from core import update_signature  # noqa: F401  (los tests parchean updater.update_signature)
from core.config import APP_VERSION
from core.logger import get_logger
from core.update_signature import normalize_version, verify_signature
```

Sustituye `validate_download_manifest` completa por:

```python
def validate_manifest_fields(data: dict) -> dict:
    """URL HTTPS, SHA-256 y nombre .exe de un manifiesto, sin mirar la firma.

    Es lo que comparten la app y tools/sign_manifest.py para derivar los
    mismos `filename` y `sha256` que entran en el mensaje firmado.
    """
    if not isinstance(data, dict):
        raise ValueError("Manifiesto de actualización inválido.")
    url = str(data.get("download_url") or data.get("url") or "").strip()
    checksum = str(data.get("sha256") or "").strip().lower()
    if not _is_https_url(url):
        raise ValueError("La descarga de la actualización debe usar HTTPS.")
    if not SHA256_RE.fullmatch(checksum):
        raise ValueError("El manifiesto no incluye un SHA-256 válido.")
    filename = Path(url.split("?", 1)[0]).name or "TDTRadioVIP_Update.exe"
    if not filename.lower().endswith(".exe"):
        raise ValueError("La actualización debe ser un instalador EXE.")
    return {"download_url": url, "sha256": checksum, "filename": filename}


def validate_download_manifest(data: dict) -> dict:
    """Valida los campos y la firma antes de descargar un instalador.

    Sin firma válida del autor no se descarga nada: el SHA-256 viaja en el
    mismo manifiesto que la URL, así que por sí solo no prueba autenticidad.
    """
    fields = validate_manifest_fields(data)
    signature = data.get("signature")
    signature = signature.strip().lower() if isinstance(signature, str) else ""
    if not signature:
        raise ValueError("El manifiesto no está firmado.")
    version = normalize_version(data.get("version"))
    if not version or not verify_signature(
        version, fields["filename"], fields["sha256"], signature
    ):
        raise ValueError("La firma del manifiesto no es válida.")
    return {**data, **fields, "signature": signature}


def has_valid_signature(data: object) -> bool:
    """True si `data` es un manifiesto descargable con firma válida (no lanza)."""
    try:
        validate_download_manifest(data)
    except ValueError:
        return False
    return True
```

(`update_signature` se importa como módulo, con su `# noqa: F401`, para que los tests puedan parchear `updater.update_signature.UPDATE_PUBLIC_KEY_N_B64`.)

Actualiza también el docstring del módulo (líneas 1-13): añade el párrafo

```
La descarga automática exige además una firma del autor en el manifiesto
(ver core/update_signature.py): sin ella solo se ofrece abrir la página.
```

- [ ] **Step 5: Ejecutar los tests y comprobar que pasan**

Run: `python -m pytest tests/test_updater_secure.py tests/test_update_signature.py -v`
Expected: todos PASS.

- [ ] **Step 6: Suite completa, ruff y commit**

Run: `python -m pytest -q && python -m ruff check core tests`
Expected: todo en verde.

```bash
git add core/updater.py tests/test_updater_secure.py
git commit -m "feat: la descarga de actualizaciones exige un manifiesto con firma valida

validate_download_manifest() ahora rechaza manifiestos sin firma o con firma
invalida (version, nombre de archivo y sha256 firmados). La validacion de
campos se reparte en validate_manifest_fields() para reutilizarla en la
herramienta de firma. Nuevo has_valid_signature() que no lanza."
```

---

### Task 3: La interfaz solo ofrece la descarga segura con firma válida

**Files:**
- Modify: `ui/update_check_controller.py:15-21` (imports), `ui/update_check_controller.py:78-100`, `ui/update_check_controller.py:111-115`
- Modify: `tests/test_update_check_controller.py`

**Interfaces:**
- Consumes (Task 2): `updater.has_valid_signature(data) -> bool`; en tests `_signing.signed_manifest`, fixture `trusted_update_key`.
- Produces: nada que consuman otras tareas.

- [ ] **Step 1: Actualizar y añadir tests que fallan**

En `tests/test_update_check_controller.py`, añade `import _signing` tras `import pytest` y sustituye `test_new_version_offers_the_verified_download` por:

```python
def test_new_version_with_valid_signature_offers_the_verified_download(
    win, boxes, workers, trusted_update_key
):
    boxes.question.return_value = "yes"
    firmado = _signing.signed_manifest()

    UpdateCheckController(win).on_update_check_done(firmado)

    texto = boxes.question.call_args.args[2]
    assert "8.7.0" in texto
    assert "Descargar y verificar" in texto
    (worker,) = workers
    assert worker.func is ucc_module.updater.download_verified_update
    assert worker.args[0] == firmado
    worker.start.assert_called_once()
```

Añade estos tests (junto a `test_new_version_without_checksum_opens_the_download_page`):

```python
def test_new_version_with_checksum_but_no_signature_opens_the_download_page(
    win, boxes, workers, trusted_update_key
):
    """NEWER trae sha256 pero ninguna firma: antes se ofrecia la descarga
    segura; ahora solo abrir la pagina, y nunca se ejecuta nada sin verificar."""
    boxes.question.return_value = "yes"

    UpdateCheckController(win).on_update_check_done(NEWER)

    assert "página de descarga" in boxes.question.call_args.args[2]
    assert workers == []
    ucc_module.QDesktopServices.openUrl.assert_called_once()


def test_new_version_with_invalid_signature_opens_the_download_page(
    win, boxes, workers, trusted_update_key
):
    boxes.question.return_value = "yes"
    manipulado = _signing.signed_manifest()
    manipulado["sha256"] = "0" * 64

    UpdateCheckController(win).on_update_check_done(manipulado)

    assert workers == []
    ucc_module.QDesktopServices.openUrl.assert_called_once()


def test_without_a_configured_public_key_the_download_page_is_offered(
    win, boxes, workers, monkeypatch
):
    """App sin clave publica configurada: falla cerrado, no se rompe."""
    monkeypatch.setattr(ucc_module.updater.update_signature, "UPDATE_PUBLIC_KEY_N_B64", "")
    boxes.question.return_value = "yes"

    UpdateCheckController(win).on_update_check_done(_signing.signed_manifest())

    assert workers == []
    ucc_module.QDesktopServices.openUrl.assert_called_once()
```

Y amplía `test_verified_download_runs_the_installer_if_accepted` con una aserción al final:

```python
    assert "firma" in boxes.question.call_args.args[2]
```

- [ ] **Step 2: Ejecutar los tests y comprobar que fallan**

Run: `python -m pytest tests/test_update_check_controller.py -v`
Expected: FAIL en los tests de "sin firma" (hoy `secure_download` solo mira `sha256`) y en el texto "firma".

- [ ] **Step 3: Implementar en `ui/update_check_controller.py`**

Añade el import `from core.logger import get_logger` junto a los demás imports de `core`, y bajo los imports:

```python
log = get_logger(__name__)
```

Sustituye la línea `secure_download = bool(resultado.get("sha256") and enlace)` (línea 80) por:

```python
        secure_download = bool(enlace) and updater.has_valid_signature(resultado)
        if not secure_download and resultado.get("sha256"):
            log.warning(
                "El manifiesto de actualización no trae una firma válida; "
                "se ofrece la descarga manual"
            )
```

Y en `_on_update_download_done` cambia el texto:

```python
            "El instalador superó la verificación de firma y SHA-256.\n\n¿Ejecutarlo ahora?",
```

Actualiza también la línea 3-4 del docstring del módulo: `(SHA-256)` → `(firma y SHA-256)`.

- [ ] **Step 4: Ejecutar los tests y comprobar que pasan**

Run: `python -m pytest tests/test_update_check_controller.py -v`
Expected: todos PASS.

- [ ] **Step 5: Suite completa y commit**

Run: `python -m pytest -q`
Expected: todo en verde.

```bash
git add ui/update_check_controller.py tests/test_update_check_controller.py
git commit -m "feat: la UI solo ofrece descargar y verificar si el manifiesto tiene firma valida

Sin firma, con firma invalida o sin clave publica configurada se degrada al
flujo existente de abrir la pagina de descarga, y se registra un aviso. Nunca
se ofrece ejecutar un instalador sin verificar."
```

---

### Task 4: Herramienta del autor (`tools/sign_manifest.py`) y dependencias de desarrollo

**Files:**
- Create: `tools/sign_manifest.py`
- Test: `tests/test_sign_manifest.py`
- Modify: `requirements-dev.txt`, `.gitignore`, `.github/workflows/ci.yml:57`

**Interfaces:**
- Consumes (Task 1 y 2): `update_signature.normalize_version`, `update_signature.signed_message`, `update_signature.verify_signature(..., modulus=)`, `updater.validate_manifest_fields`; en tests `_signing`.
- Produces:
  - `tools/sign_manifest.py`: `REPO_ROOT: Path`, `class SigningError(Exception)`, `generate_keypair(out_dir: Path, repo_root: Path = REPO_ROOT) -> str` (devuelve el módulo público en base64), `sign_manifest_file(key_path: Path, manifest_path: Path) -> None`, `main(argv: list[str] | None = None) -> int`.
  - CLI: `python tools/sign_manifest.py keygen --out <carpeta>` y `python tools/sign_manifest.py sign --key <pem> --manifest <manifest.json>`.

- [ ] **Step 1: Escribir los tests que fallan**

`tests/test_sign_manifest.py`:

```python
"""
tools/sign_manifest.py: herramienta del autor para generar la clave y firmar.

Lo critico: la clave privada jamas acaba dentro del repositorio ni se pisa
una existente, y un manifiesto firmado por la herramienta es exactamente el
que la app acepta (mismos campos, misma normalizacion).
"""
import base64
import importlib.util
import json
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
```

- [ ] **Step 2: Ejecutar los tests y comprobar que fallan**

Run: `python -m pytest tests/test_sign_manifest.py -v`
Expected: error de colección `FileNotFoundError` (no existe `tools/sign_manifest.py`).

- [ ] **Step 3: Implementar la herramienta**

`tools/sign_manifest.py`:

```python
"""Genera la clave de firma de actualizaciones y firma manifest.json.

Herramienta del autor, solo de desarrollo: usa `cryptography` (ver
requirements-dev.txt); la app no la importa ni la necesita.

  python tools/sign_manifest.py keygen --out <carpeta fuera del repo>
  python tools/sign_manifest.py sign --key <update_signing_key.pem> --manifest manifest.json

La clave privada es lo unico que impide que alguien con acceso a la release
de GitHub publique un instalador malicioso: guardala fuera del repo y con
copia de seguridad. Si se pierde, ninguna version instalada podra verificar
actualizaciones nuevas.
"""
import argparse
import base64
import json
import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))  # permite ejecutarlo desde cualquier directorio

from core import update_signature  # noqa: E402
from core.updater import validate_manifest_fields  # noqa: E402

KEY_FILENAME = "update_signing_key.pem"
_KEY_BITS = 2048


class SigningError(Exception):
    """Error de uso de la herramienta, con un mensaje para el autor."""


def _is_inside(path: Path, root: Path) -> bool:
    resolved = path.resolve()
    return resolved == root or root in resolved.parents


def _modulus_b64(modulus: int) -> str:
    return base64.b64encode(modulus.to_bytes(_KEY_BITS // 8, "big")).decode("ascii")


def generate_keypair(out_dir: Path, repo_root: Path = REPO_ROOT) -> str:
    """Crea la clave privada en `out_dir` y devuelve el modulo publico (base64)."""
    out_dir = Path(out_dir)
    if _is_inside(out_dir, repo_root):
        raise SigningError("La clave privada no puede guardarse dentro del repositorio.")
    key_path = out_dir / KEY_FILENAME
    if key_path.exists():
        raise SigningError(f"Ya existe una clave en {key_path}; no se sobrescribe.")
    out_dir.mkdir(parents=True, exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=_KEY_BITS)
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    descriptor = os.open(key_path, flags, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(pem)
    return _modulus_b64(key.public_key().public_numbers().n)


def _load_private_key(key_path: Path) -> rsa.RSAPrivateKey:
    try:
        key = serialization.load_pem_private_key(Path(key_path).read_bytes(), password=None)
    except (OSError, ValueError, TypeError) as exc:
        raise SigningError(f"No se pudo leer la clave privada: {exc}") from exc
    if not isinstance(key, rsa.RSAPrivateKey) or key.key_size != _KEY_BITS:
        raise SigningError("La clave privada debe ser RSA de 2048 bits.")
    return key


def sign_manifest_file(key_path: Path, manifest_path: Path) -> None:
    """Anade `signature` al manifiesto, tras comprobar que la app lo aceptara."""
    key = _load_private_key(key_path)
    manifest_path = Path(manifest_path)
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SigningError(f"No se pudo leer el manifiesto: {exc}") from exc
    if not isinstance(data, dict):
        raise SigningError("El manifiesto debe ser un objeto JSON.")

    try:
        fields = validate_manifest_fields(data)
    except ValueError as exc:
        raise SigningError(str(exc)) from exc
    version = update_signature.normalize_version(data.get("version"))
    if not version:
        raise SigningError("El manifiesto no incluye 'version'.")

    message = update_signature.signed_message(version, fields["filename"], fields["sha256"])
    signature = key.sign(message, padding.PKCS1v15(), hashes.SHA256()).hex()

    own_modulus = key.public_key().public_numbers().n
    if not update_signature.verify_signature(
        version, fields["filename"], fields["sha256"], signature, modulus=own_modulus
    ):
        raise SigningError("La firma recién creada no verifica (error interno).")
    if not update_signature.verify_signature(
        version, fields["filename"], fields["sha256"], signature
    ):
        raise SigningError(
            "La clave pública embebida en core/update_signature.py no coincide con "
            "esta clave privada: la app rechazaría este manifiesto."
        )

    manifest_path.write_text(
        json.dumps({**data, "signature": signature}, indent=2) + "\n", encoding="utf-8"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    keygen = commands.add_parser("keygen", help="genera el par de claves")
    keygen.add_argument("--out", required=True, type=Path, help="carpeta fuera del repo")
    sign = commands.add_parser("sign", help="firma un manifest.json")
    sign.add_argument("--key", required=True, type=Path)
    sign.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args(argv)

    try:
        if args.command == "keygen":
            modulus_b64 = generate_keypair(args.out)
            print(f"Clave privada guardada en {args.out / KEY_FILENAME}")
            print("Guárdala fuera del repo y haz copia de seguridad.")
            print("Pega esto en core/update_signature.py:")
            print(f'UPDATE_PUBLIC_KEY_N_B64 = "{modulus_b64}"')
        else:
            sign_manifest_file(args.key, args.manifest)
            print(f"Manifiesto firmado: {args.manifest}")
    except SigningError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Dependencias, `.gitignore` y CI**

`requirements-dev.txt`: añade al final la línea

```
cryptography>=42
```

`.gitignore`: añade al final

```

# Clave privada de firma de actualizaciones: jamas debe entrar en el repo.
# (tools/sign_manifest.py ya se niega a escribirla aqui; esto es defensa extra.)
*.pem
update_signing_key*
```

Antes de editar, comprueba que no hay ningún `.pem` ya versionado: `git ls-files "*.pem"` debe imprimir vacío.

`.github/workflows/ci.yml` línea 57: añade `"cryptography>=42"` a la lista de `pip install`:

```yaml
          python -m pip install "PySide6>=6.5" "requests>=2.31" "pytest>=7.4" "pytest-cov>=5.0" "ruff>=0.6" "cryptography>=42"
```

- [ ] **Step 5: Ejecutar los tests y comprobar que pasan**

Run: `python -m pytest tests/test_sign_manifest.py -v`
Expected: todos PASS.

- [ ] **Step 6: Suite completa, ruff y commit**

Run: `python -m pytest -q && python -m ruff check .`
Expected: todo en verde. (`ruff check .` incluye `tools/`; los `# noqa: E402` son necesarios por el `sys.path.insert` previo.)

```bash
git add tools/sign_manifest.py tests/test_sign_manifest.py requirements-dev.txt .gitignore .github/workflows/ci.yml
git commit -m "feat: herramienta tools/sign_manifest.py para generar la clave y firmar manifiestos

keygen crea la clave RSA-2048 fuera del repo (se niega a escribir dentro y a
sobrescribir) e imprime solo la clave publica. sign anade 'signature' a
manifest.json tras comprobar que la app lo aceptara, incluida la clave
publica embebida. cryptography queda como dependencia de desarrollo y se
instala en CI para que los tests de firma se ejecuten."
```

---

### Task 5: Documentar el proceso de publicación y cerrar

**Files:**
- Modify: `RELEASE.md` (bloque del manifiesto y nuevo apartado)
- Modify: `docs/superpowers/specs/2026-10-01-signed-update-manifest-design.md:3`

**Interfaces:**
- Consumes: la CLI de Task 4.
- Produces: nada.

- [ ] **Step 1: Actualizar el formato del manifiesto en `RELEASE.md`**

Sustituye el párrafo que empieza por «El manifiesto tiene que ser exactamente:» y su bloque JSON por:

````markdown
El manifiesto tiene que ser exactamente:
```json
{
  "version": "X.Y.Z.W",
  "download_url": "https://github.com/xorgsm/TDTRadioVIP-Free/releases/download/vX.Y.Z.W/TDTRadioVIP_Setup_vX.Y.Z.W.exe",
  "sha256": "<sha256 en minúsculas, 64 hex>",
  "signature": "<firma RSA-2048, 512 hex>"
}
```

**La firma es obligatoria** para que la app ofrezca "Descargar y verificar":
sin ella (o con una firma inválida) solo ofrece abrir la página de descarga.
Se añade con `tools/sign_manifest.py` (ver el apartado siguiente); no se
escribe a mano.
````

- [ ] **Step 2: Añadir el apartado "Firmar el manifiesto"**

Inserta, justo antes de `## Antes de nada: sincronizar el fix a los 3 repos`:

````markdown
## Firmar el manifiesto

El SHA-256 viaja en el mismo `manifest.json` que la URL, así que no prueba
por sí solo que el manifiesto lo haya publicado el autor. La firma, hecha con
una clave privada que **no** está en GitHub, sí (ver
`docs/superpowers/specs/2026-10-01-signed-update-manifest-design.md`).

**Una sola vez — generar la clave** (necesita `pip install -r requirements-dev.txt`):

```bash
python tools/sign_manifest.py keygen --out "D:/ruta/fuera/del/repo/claves-tdt"
```

Imprime la línea `UPDATE_PUBLIC_KEY_N_B64 = "..."`: pégala en
`core/update_signature.py` y publica una versión con ese cambio **antes** de
firmar manifiestos. La clave privada queda en
`update_signing_key.pem`: haz copia de seguridad fuera del PC y de GitHub.
La herramienta se niega a guardarla dentro del repo o a sobrescribir otra.

> **Si pierdes la clave privada**, ninguna versión instalada podrá verificar
> actualizaciones nuevas: habría que publicar a mano un instalador con otra
> clave pública. **Si se filtra**, cualquiera puede firmar instaladores que
> las versiones instaladas aceptarán: misma salida (versión manual con clave
> nueva). No es la clave de licencias (`core/license.py`); no las mezcles.

**En cada release — firmar el manifiesto** antes de subirlo:

```bash
python tools/sign_manifest.py sign --key "D:/ruta/fuera/del/repo/claves-tdt/update_signing_key.pem" --manifest installer_output/manifest.json
```

Valida los campos, añade `signature` y comprueba que la app lo aceptará
(incluida la clave pública embebida). Sube el `manifest.json` ya firmado a la
release de `TDTRadioVIP-Free`.
````

- [ ] **Step 3: Marcar el spec como implementado**

En `docs/superpowers/specs/2026-10-01-signed-update-manifest-design.md`, línea 3, sustituye

```
**Estado:** Diseño aprobado en conversación (2026-10-01); spec pendiente de revisión.
```

por

```
**Estado:** Diseño aprobado e implementado (2026-10-01). Pendiente del autor: generar la clave real y pegar la clave pública (ver `RELEASE.md`, "Firmar el manifiesto").
```

- [ ] **Step 4: Verificación final de todo el trabajo**

Run: `python -m pytest -q && python -m ruff check .`
Expected: todo en verde.

Run: `git status --short`
Expected: solo `RELEASE.md` y el spec modificados.

- [ ] **Step 5: Commit**

```bash
git add RELEASE.md docs/superpowers/specs/2026-10-01-signed-update-manifest-design.md
git commit -m "docs: proceso de publicacion con manifiesto firmado en RELEASE.md"
```

---

## Después de implementar (lo hace el autor, no el agente)

La app queda con `UPDATE_PUBLIC_KEY_N_B64 = ""`: **falla cerrado** y ninguna versión nueva descargará actualizaciones automáticamente hasta completar estos pasos, en este orden:

1. `python tools/sign_manifest.py keygen --out <carpeta fuera del repo>` y copia de seguridad de `update_signing_key.pem`.
2. Pegar la línea `UPDATE_PUBLIC_KEY_N_B64 = "..."` en `core/update_signature.py` y hacer commit.
3. Publicar la versión con la verificación.
4. Desde entonces, firmar cada `manifest.json` con `sign` antes de subirlo.
5. Llevar estos cambios a `TDTRadioVIP-Free` (sincronización manual, ver `RELEASE.md`) para que la edición Free también verifique firmas.
