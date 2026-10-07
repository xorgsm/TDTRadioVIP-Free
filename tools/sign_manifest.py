"""Genera la clave de firma de actualizaciones y firma manifest.json.

Herramienta del autor, solo de desarrollo: usa `cryptography` (ver
requirements-dev.txt); la app no la importa ni la necesita.

  python tools/sign_manifest.py keygen --out <carpeta fuera del repo>
  python tools/sign_manifest.py make --key <update_signing_key.pem> --installer <Setup.exe>
  python tools/sign_manifest.py sign --key <update_signing_key.pem> --manifest manifest.json
  python tools/sign_manifest.py verify <manifest.json | https://...> [--installer <Setup.exe>]

La contrasena de la clave se pide por terminal; para uso sin terminal se
lee de la variable de entorno TDT_SIGNING_PASSPHRASE.

La clave privada es lo unico que impide que alguien con acceso a la release
de GitHub publique un instalador malicioso: guardala fuera del repo y con
copia de seguridad. Si se pierde, ninguna version instalada podra verificar
actualizaciones nuevas.
"""
import argparse
import base64
import getpass
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))  # permite ejecutarlo desde cualquier directorio

from core import update_signature  # noqa: E402
from core.config import APP_VERSION  # noqa: E402
from core.updater import validate_download_manifest, validate_manifest_fields  # noqa: E402

KEY_FILENAME = "update_signing_key.pem"
PASSPHRASE_ENV = "TDT_SIGNING_PASSPHRASE"
UPDATE_SIGNATURE_PATH = REPO_ROOT / "core" / "update_signature.py"
RELEASE_URL_TEMPLATE = (
    "https://github.com/xorgsm/TDTRadioVIP-Free/releases/download/v{version}/{filename}"
)
INSTALLER_NAME_TEMPLATE = "TDTRadioVIP_Setup_v{version}.exe"
MAX_MANIFEST_BYTES = 64 * 1024
_FETCH_TIMEOUT_SECONDS = 15
_HASH_CHUNK_BYTES = 1024 * 1024
_KEY_BITS = 2048
_ENCRYPTED_MARKER = b"ENCRYPTED"
_SAFE_FILENAME_RE = re.compile(r"[A-Za-z0-9._-]+")
_EMBEDDED_KEY_RE = re.compile(r'^(UPDATE_PUBLIC_KEY_N_B64 = ")([^"]*)(")', re.MULTILINE)


class SigningError(Exception):
    """Error de uso de la herramienta, con un mensaje para el autor."""


def _is_inside(path: Path, root: Path) -> bool:
    resolved = path.resolve()
    return resolved == root or root in resolved.parents


def _modulus_b64(modulus: int) -> str:
    return base64.b64encode(modulus.to_bytes(_KEY_BITS // 8, "big")).decode("ascii")


def _restrict_to_current_user(path: Path) -> None:
    """En Windows `0o600` no toca la ACL: quita la herencia y deja solo al
    usuario actual. En otros sistemas el modo 0o600 ya basta."""
    if os.name != "nt":
        return
    result = subprocess.run(
        ["icacls", str(path), "/inheritance:r", "/grant:r", f"{getpass.getuser()}:F"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise SigningError(
            "No se pudieron restringir los permisos de la clave privada "
            f"(icacls: {result.stderr.strip() or result.stdout.strip()})."
        )


def generate_keypair(
    out_dir: Path, repo_root: Path = REPO_ROOT, passphrase: str | None = None
) -> str:
    """Crea la clave privada en `out_dir` y devuelve el modulo publico (base64).

    Con `passphrase` el PEM se guarda cifrado; sin ella, en claro.
    """
    out_dir = Path(out_dir)
    if _is_inside(out_dir, repo_root):
        raise SigningError("La clave privada no puede guardarse dentro del repositorio.")
    key_path = out_dir / KEY_FILENAME
    if key_path.exists():
        raise SigningError(f"Ya existe una clave en {key_path}; no se sobrescribe.")
    out_dir.mkdir(parents=True, exist_ok=True)
    key = rsa.generate_private_key(public_exponent=65537, key_size=_KEY_BITS)
    encryption = (
        serialization.BestAvailableEncryption(passphrase.encode("utf-8"))
        if passphrase
        else serialization.NoEncryption()
    )
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, encryption
    )
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    descriptor = os.open(key_path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            # Se restringe el archivo vacio y solo despues se escribe la clave:
            # asi nunca existe en disco con los permisos heredados.
            _restrict_to_current_user(key_path)
            handle.write(pem)
    except BaseException:
        key_path.unlink(missing_ok=True)
        raise
    return _modulus_b64(key.public_key().public_numbers().n)


def _is_locked(key_path: Path) -> bool:
    """True si el PEM esta cifrado (hace falta contrasena para usarlo)."""
    try:
        return _ENCRYPTED_MARKER in Path(key_path).read_bytes()
    except OSError:
        return False


def _load_private_key(key_path: Path, passphrase: str | None = None) -> rsa.RSAPrivateKey:
    try:
        pem = Path(key_path).read_bytes()
    except OSError as exc:
        raise SigningError(f"No se pudo leer la clave privada: {exc}") from exc
    locked = _ENCRYPTED_MARKER in pem
    if locked and not passphrase:
        raise SigningError("La clave privada está protegida: falta la contraseña.")
    try:
        key = serialization.load_pem_private_key(
            pem, password=passphrase.encode("utf-8") if locked and passphrase else None
        )
    except (ValueError, TypeError) as exc:
        if locked:
            raise SigningError("La contraseña de la clave privada es incorrecta.") from exc
        raise SigningError(f"No se pudo leer la clave privada: {exc}") from exc
    if not isinstance(key, rsa.RSAPrivateKey) or key.key_size != _KEY_BITS:
        raise SigningError("La clave privada debe ser RSA de 2048 bits.")
    return key


def sign_manifest_file(
    key_path: Path, manifest_path: Path, passphrase: str | None = None
) -> None:
    """Anade `signature` al manifiesto, tras comprobar que la app lo aceptara."""
    key = _load_private_key(key_path, passphrase)
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

    message = update_signature.signed_message(
        version, fields["filename"], fields["sha256"], fields["download_url"]
    )
    signature = key.sign(message, padding.PKCS1v15(), hashes.SHA256()).hex()

    own_modulus = key.public_key().public_numbers().n
    if not update_signature.verify_signature(
        version, fields["filename"], fields["sha256"], fields["download_url"],
        signature, modulus=own_modulus
    ):
        raise SigningError("La firma recién creada no verifica (error interno).")
    if not update_signature.verify_signature(
        version, fields["filename"], fields["sha256"], fields["download_url"], signature
    ):
        raise SigningError(
            "La clave pública embebida en core/update_signature.py no coincide con "
            "esta clave privada: la app rechazaría este manifiesto."
        )

    manifest_path.write_text(
        json.dumps({**data, "signature": signature}, indent=2) + "\n", encoding="utf-8"
    )


def _ensure_embed_allowed(target: Path, replace: bool) -> None:
    """Falla si `target` no tiene la constante o ya lleva una clave que no
    se debe pisar: cambiarla deja sin verificar a las versiones instaladas."""
    try:
        text = Path(target).read_text(encoding="utf-8")
    except OSError as exc:
        raise SigningError(f"No se pudo leer {target}: {exc}") from exc
    found = _EMBEDDED_KEY_RE.search(text)
    if not found:
        raise SigningError(f"No se encontró UPDATE_PUBLIC_KEY_N_B64 en {target}.")
    if found.group(2) and not replace:
        raise SigningError(
            f"{Path(target).name} ya tiene una clave pública; usa --replace-embedded "
            "solo si sabes que las versiones instaladas dejarán de verificar."
        )


def embed_public_key(modulus_b64: str, target: Path, replace: bool = False) -> None:
    """Escribe la clave publica en la constante `UPDATE_PUBLIC_KEY_N_B64`."""
    try:
        valid = len(base64.b64decode(modulus_b64, validate=True)) == _KEY_BITS // 8
    except ValueError:
        valid = False
    if not valid:
        raise SigningError(f"El módulo público no es una clave RSA de {_KEY_BITS} bits.")
    _ensure_embed_allowed(target, replace)
    target = Path(target)
    text = target.read_text(encoding="utf-8")
    updated = _EMBEDDED_KEY_RE.sub(lambda m: m.group(1) + modulus_b64 + m.group(3), text, count=1)
    _write_text_atomic(target, updated)


def _write_text_atomic(target: Path, text: str) -> None:
    """Escribe en un temporal del mismo directorio y lo mueve sobre `target`:
    un fallo a medias nunca deja el archivo truncado."""
    pending = target.with_name(target.name + ".tmp")
    try:
        pending.write_text(text, encoding="utf-8")
        os.replace(pending, target)
    except BaseException:
        pending.unlink(missing_ok=True)
        raise


def _sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(_HASH_CHUNK_BYTES), b""):
                digest.update(chunk)
    except OSError as exc:
        raise SigningError(f"No se pudo leer el instalador: {exc}") from exc
    return digest.hexdigest()


def _ensure_out_is_safe(manifest_path: Path, key_path: Path, installer_path: Path) -> None:
    """`--out` nunca puede pisar la clave ni el instalador."""
    target = manifest_path.resolve()
    for protected in (Path(key_path), installer_path):
        if target == protected.resolve():
            raise SigningError(f"--out no puede coincidir con {protected}.")
    if manifest_path.suffix.lower() != ".json":
        raise SigningError("El manifiesto de salida debe ser un archivo .json.")


def build_manifest(
    key_path: Path,
    installer_path: Path,
    version: str | None = None,
    passphrase: str | None = None,
    out_path: Path | None = None,
) -> Path:
    """Crea y firma el manifiesto de `installer_path`; devuelve su ruta.

    Si la firma falla no queda ningun manifiesto a medio escribir.
    """
    installer_path = Path(installer_path)
    if not installer_path.is_file():
        raise SigningError(f"No se encuentra el instalador: {installer_path}")
    if installer_path.suffix.lower() != ".exe":
        raise SigningError("El instalador debe ser un archivo EXE.")
    if not _SAFE_FILENAME_RE.fullmatch(installer_path.name):
        raise SigningError("El nombre del instalador solo puede tener letras, números, '.', '_' y '-'.")
    version = update_signature.normalize_version(version or APP_VERSION)
    expected_name = INSTALLER_NAME_TEMPLATE.format(version=version)
    if installer_path.name != expected_name:
        raise SigningError(
            f"El instalador debe llamarse {expected_name}: la URL de descarga "
            "apuntaría a una release que no existe (usa --version)."
        )
    manifest_path = Path(out_path) if out_path else installer_path.parent / "manifest.json"
    _ensure_out_is_safe(manifest_path, key_path, installer_path)
    data = {
        "version": version,
        "download_url": RELEASE_URL_TEMPLATE.format(
            version=version, filename=installer_path.name
        ),
        "sha256": _sha256_of(installer_path),
    }
    # Se firma un temporal y solo al final sustituye al manifiesto: un fallo
    # (p. ej. contrasena incorrecta) nunca pisa ni borra uno anterior.
    pending_path = manifest_path.with_name(manifest_path.name + ".tmp")
    pending_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    try:
        sign_manifest_file(key_path, pending_path, passphrase)
        os.replace(pending_path, manifest_path)
    except BaseException:
        pending_path.unlink(missing_ok=True)
        raise
    return manifest_path


def _fetch_manifest_text(url: str) -> str:
    """Descarga el manifiesto publicado, con tope de tamano."""
    try:
        response = requests.get(url, timeout=_FETCH_TIMEOUT_SECONDS, stream=True)
        try:
            response.raise_for_status()
            body = b""
            for chunk in response.iter_content(chunk_size=8192):
                body += chunk
                if len(body) > MAX_MANIFEST_BYTES:
                    raise SigningError("El manifiesto descargado es demasiado grande.")
        finally:
            response.close()
    except requests.RequestException as exc:
        raise SigningError(f"No se pudo descargar el manifiesto: {exc}") from exc
    return body.decode("utf-8", errors="replace")


def verify_manifest(source: str, installer: Path | None = None) -> dict:
    """Valida un manifiesto (ruta o URL HTTPS) como lo haria la app.

    Con `installer` comprueba ademas que su SHA-256 coincide con el publicado.
    """
    if re.match(r"^https?://", source, re.IGNORECASE):
        if not source.lower().startswith("https://"):
            raise SigningError("El manifiesto debe descargarse por HTTPS.")
        text = _fetch_manifest_text(source)
    else:
        try:
            text = Path(source).read_text(encoding="utf-8")
        except OSError as exc:
            raise SigningError(f"No se pudo leer el manifiesto: {exc}") from exc
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise SigningError(f"El manifiesto no es JSON válido: {exc}") from exc
    try:
        validated = validate_download_manifest(data)
    except ValueError as exc:
        raise SigningError(str(exc)) from exc
    if installer is not None and _sha256_of(Path(installer)) != validated["sha256"]:
        raise SigningError("El SHA-256 del instalador no coincide con el del manifiesto.")
    return validated


def _prompt_passphrase(confirm: bool = False) -> str:
    passphrase = getpass.getpass("Contraseña de la clave: ")
    if confirm:
        if not passphrase:
            raise SigningError("La contraseña no puede estar vacía; usa --no-passphrase.")
        if getpass.getpass("Repite la contraseña: ") != passphrase:
            raise SigningError("Las contraseñas no coinciden.")
    return passphrase


def _passphrase_for(key_path: Path) -> str | None:
    """Contrasena para usar la clave: del entorno o de la terminal, solo si
    la clave esta cifrada."""
    if not _is_locked(key_path):
        return None
    return os.environ.get(PASSPHRASE_ENV) or _prompt_passphrase()


def _run_keygen(args: argparse.Namespace) -> None:
    _ensure_embed_allowed(UPDATE_SIGNATURE_PATH, args.replace_embedded)
    passphrase = None
    if args.no_passphrase:
        print("Aviso: la clave privada se guarda SIN cifrar.", file=sys.stderr)
    else:
        passphrase = os.environ.get(PASSPHRASE_ENV) or _prompt_passphrase(confirm=True)
    modulus_b64 = generate_keypair(args.out, passphrase=passphrase)
    print(f"Clave privada guardada en {args.out / KEY_FILENAME}")
    print("Guárdala fuera del repo y haz copia de seguridad (y de la contraseña).")
    embed_public_key(modulus_b64, UPDATE_SIGNATURE_PATH, replace=args.replace_embedded)
    print(f"Clave pública escrita en {UPDATE_SIGNATURE_PATH}: publica una versión con ese cambio.")
    print(f'UPDATE_PUBLIC_KEY_N_B64 = "{modulus_b64}"')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    keygen = commands.add_parser("keygen", help="genera el par de claves")
    keygen.add_argument("--out", required=True, type=Path, help="carpeta fuera del repo")
    keygen.add_argument("--no-passphrase", action="store_true", help="clave sin cifrar")
    keygen.add_argument(
        "--replace-embedded", action="store_true", help="pisa la clave pública ya embebida"
    )
    sign = commands.add_parser("sign", help="firma un manifest.json")
    sign.add_argument("--key", required=True, type=Path)
    sign.add_argument("--manifest", required=True, type=Path)
    make = commands.add_parser("make", help="crea y firma el manifest.json de un instalador")
    make.add_argument("--key", required=True, type=Path)
    make.add_argument("--installer", required=True, type=Path)
    make.add_argument("--version", help="por defecto APP_VERSION")
    make.add_argument("--out", type=Path, help="por defecto manifest.json junto al instalador")
    verify = commands.add_parser("verify", help="valida un manifiesto como la app")
    verify.add_argument("source", help="ruta o URL HTTPS del manifest.json")
    verify.add_argument("--installer", type=Path, help="comprueba también su SHA-256")
    args = parser.parse_args(argv)

    try:
        if args.command == "keygen":
            _run_keygen(args)
        elif args.command == "sign":
            sign_manifest_file(args.key, args.manifest, _passphrase_for(args.key))
            print(f"Manifiesto firmado: {args.manifest}")
        elif args.command == "make":
            path = build_manifest(
                args.key, args.installer, args.version, _passphrase_for(args.key), args.out
            )
            print(f"Manifiesto firmado: {path}")
        else:
            data = verify_manifest(args.source, args.installer)
            print(f"Manifiesto válido: versión {data.get('version')}, firma correcta.")
    except SigningError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
