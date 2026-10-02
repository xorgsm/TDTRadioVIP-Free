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
import getpass
import json
import os
import subprocess
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
