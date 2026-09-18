"""
Sistema de licencias de TDT & Radio VIP.

El hardware ID se genera combinando datos únicos del PC del usuario
(número de serie del disco C:, UUID de la placa base y nombre del procesador).
El código de activación V2 se firma con RSA-2048 en el generador de licencias;
la aplicación solo contiene la clave pública para verificarlo. Así se pueden
generar licencias sin conexión ni base de datos sin distribuir una clave capaz
de emitirlas.

Coder By X@R
"""
import hashlib
import hmac
import json
import platform
import subprocess
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache
from pathlib import Path

from core.config import get_app_data_dir
from core.json_store import write_json_atomic
from core.logger import get_logger

log = get_logger(__name__)

# ── Clave secreta compartida entre license.py y keygen.py ──────────────────
# La app distribuida solo contiene esta clave pública; el keygen conserva la
# clave privada fuera del proyecto empaquetado.
_RSA_N = int.from_bytes(__import__("base64").b64decode(
    "sXdjzPGMBiZubTUwphp3ZeAACHYPCWgBKWctQXe2wzNcDIcVrKfnt6ImvxRZLWRRouLBqK6VO6tWxE877l+RaNAQIZipxUTVvF31SOHEkym5ITffYcyAJDayB6InQxSQmv+evSePhcDeUhpXXZCg0plBPWVswtEzVrx91qO7/GIS4wzFQMdCDfW5VSvVnK00vaV01zqOo9jkk0f1B/r4gMKATKt7L5nZBWpLAgLnRc7YP+Nj+VUVCRqvwryj6D68EPCLR3d7H/v5Wdiu09uV+xylCx5M7i9q/s2Zxe23IXoF5ohOYmUBNxMksAK0fbixxaJoPEYnBSgOGVBuTKSB0Q=="
), "big")
_RSA_E = 65537
_SHA256_DER_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")

LICENSE_FILE = "license.json"
CODE_LENGTH   = 20        # caracteres del código que ve el usuario (sin guiones)
BLOCK_SIZE    = 5         # para formatear como XXXXX-XXXXX-XXXXX-XXXXX


# ── Hardware ID ─────────────────────────────────────────────────────────────

def _wmic(alias: str, prop: str, where: str = "") -> str:
    """
    Ejecuta `wmic <alias> [where <where>] get <prop> /value` y devuelve el
    valor devuelto (o "" si wmic no está disponible o la consulta falla).

    Antes se montaba el comando como ["wmic"] + query.split() + ["get",
    "value"] a partir de una única cadena tipo "diskdrive where index=0
    SerialNumber" -- eso coloca la propiedad ANTES de "get" en vez de
    después (wmic diskdrive where index=0 SerialNumber get value, en vez
    de wmic diskdrive where index=0 get SerialNumber /value), sintaxis que
    WMIC no reconoce. El resultado práctico era que WMIC fallaba siempre
    en los tres componentes que lo usan, y el hardware ID dependía 100% del
    fallback de PowerShell aunque WMIC estuviera disponible y funcionando.
    """
    cmd = ["wmic", alias]
    if where:
        cmd += ["where", where]
    cmd += ["get", prop, "/value"]
    try:
        out = subprocess.check_output(
            cmd,
            stderr=subprocess.DEVNULL,
            creationflags=0x08000000,   # CREATE_NO_WINDOW
            timeout=3,
            text=True,
        )
        for line in out.splitlines():
            line = line.strip()
            if "=" in line:
                val = line.split("=", 1)[1].strip()
                if val:
                    return val
    except Exception:
        pass
    return ""


def _powershell(cmd: str) -> str:
    """Fallback PowerShell para cuando WMIC no está disponible."""
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", cmd],
            stderr=subprocess.DEVNULL,
            creationflags=0x08000000,
            timeout=3,
            text=True,
        )
        return out.strip()
    except Exception:
        return ""


def _get_disk_serial() -> str:
    serial = _wmic("diskdrive", "SerialNumber", where="index=0")
    if not serial:
        # Get-PhysicalDisk (módulo Storage) ya es la vía moderna aquí, no WMI
        # -- no depende de WMIC ni de Get-WmiObject/Get-CimInstance.
        serial = _powershell(
            "(Get-PhysicalDisk | Sort-Object DeviceId | Select-Object -First 1).SerialNumber"
        )
    return serial.strip() or "NODISK"


def _get_board_uuid() -> str:
    uuid = _wmic("csproduct", "UUID")
    if not uuid or uuid in ("None", "Not Settable", ""):
        # Get-CimInstance, no Get-WmiObject: Get-WmiObject está deprecado
        # desde 2016 igual que WMIC, y Get-CimInstance es su reemplazo
        # soportado (más rápido, y no depende del proveedor WMI heredado
        # que Microsoft está retirando junto con WMIC).
        uuid = _powershell(
            "(Get-CimInstance -ClassName Win32_ComputerSystemProduct).UUID"
        )
    return uuid.strip() or "NOUUID"


def _get_cpu_id() -> str:
    cpu = _wmic("cpu", "ProcessorId")
    if not cpu:
        # Antes caía directo a platform.processor() (que en Windows da el
        # nombre del modelo, no un ID único -- dos PCs con la misma CPU
        # devolverían el mismo valor). Con WMIC camino a desaparecer del
        # todo en 2026, este Get-CimInstance mantiene un ProcessorId real
        # y único como los otros tres componentes del hardware ID.
        cpu = _powershell(
            "(Get-CimInstance -ClassName Win32_Processor).ProcessorId"
        )
    if not cpu:
        cpu = platform.processor() or "NOCPU"
    return cpu.strip()


def _get_machine_guid() -> str:
    """
    MachineGuid es un identificador que Windows genera al instalar el
    sistema operativo y guarda en el registro. A diferencia de WMIC (que
    Windows 11 deshabilita por defecto desde 23H2/24H2, retira al pasar a
    25H2, y Microsoft ha anunciado que elimina del todo -- sin poder
    reinstalarlo como Feature on Demand -- en la próxima actualización de
    funciones de 2026: KB5067470) o de una consulta PowerShell (lanza un
    proceso nuevo cada vez, más lento), leer el registro es instantáneo y
    no depende de que ninguna herramienta externa siga existiendo.

    _get_disk_serial()/_get_board_uuid()/_get_cpu_id() ya tienen su propio
    fallback a PowerShell (Get-PhysicalDisk / Get-CimInstance, no el
    Get-WmiObject deprecado) para cuando WMIC falte, así que no dependen
    solo de este componente -- pero MachineGuid se añade igualmente como
    señal extra, no como sustituto: más señales distintas hacen el ID más
    difícil de falsificar y más resistente a que Microsoft retire alguna
    herramienta más adelante.
    """
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Cryptography",
            0,
            winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
        ) as key:
            value, _ = winreg.QueryValueEx(key, "MachineGuid")
            return str(value).strip()
    except Exception:
        return "NOGUID"


HARDWARE_ID_CACHE_FILE = "hardware_id_cache.json"


def _hardware_id_cache_path() -> Path:
    return get_app_data_dir() / HARDWARE_ID_CACHE_FILE


def _load_cached_hardware_id() -> str:
    try:
        data = json.loads(_hardware_id_cache_path().read_text(encoding="utf-8"))
        return data.get("hardware_id", "") if isinstance(data, dict) else ""
    except (OSError, json.JSONDecodeError, TypeError, AttributeError):
        return ""


def _save_cached_hardware_id(hw: str) -> None:
    try:
        write_json_atomic(_hardware_id_cache_path(), {"hardware_id": hw})
    except OSError:
        pass  # sin permisos o disco lleno: se recalculará en el próximo arranque


@lru_cache(maxsize=1)
def generate_hardware_id() -> str:
    """
    Devuelve el hardware ID de este PC como una cadena de 16 caracteres
    hexadecimales en mayúsculas, formateada en bloques de 4: XXXX-XXXX-XXXX-XXXX.

    Cacheado por proceso (lru_cache) Y en disco (hardware_id_cache.json en
    la carpeta de datos de la app). Medido en una máquina real: WMIC +
    hasta tres procesos powershell.exe en cadena (uno por componente que
    tiene que caer al fallback) tardó 4m35s de un arranque a otro --
    completamente inaceptable para algo que se repite en cada apertura de
    la app aunque el hardware no haya cambiado nunca. Con la caché en
    disco, ese coste se paga UNA sola vez por instalación; los arranques
    siguientes leen el archivo (instantáneo) y no lanzan ni un solo
    subproceso.

    Contrapartida de seguridad asumida a propósito: alguien con acceso de
    escritura a la carpeta de datos podría editar hardware_id_cache.json a
    mano para forzar un ID arbitrario, lo cual debilita el bloqueo por
    hardware de las licencias (un código+caché falsificados podrían
    copiarse a otro PC). Se acepta ese riesgo a cambio de arrancar en
    segundos en vez de minutos; si en el futuro hiciera falta cerrar ese
    hueco, la vía sería firmar/verificar el propio archivo de caché, no
    volver a la ruta sin caché.

    Si cambia el hardware real (disco, placa) tras el primer cálculo, el
    ID cacheado se sigue usando -- efecto secundario deseable en la
    práctica (la licencia sobrevive a un cambio de disco), aunque el ID ya
    no describa el hardware actual con exactitud. Para forzar un recálculo
    real basta con borrar ese archivo.
    """
    cached = _load_cached_hardware_id()
    if cached:
        return cached

    # Los tres componentes de abajo son independientes entre sí (cada uno
    # decide su propio fallback WMIC → PowerShell), así que se lanzan a la
    # vez en vez de uno detrás de otro: el peor caso pasa de "suma de los
    # tres" a "el más lento de los tres". _get_machine_guid() no entra en
    # el pool porque ya es una lectura de registro instantánea.
    with ThreadPoolExecutor(max_workers=3) as pool:
        disk_future = pool.submit(_get_disk_serial)
        board_future = pool.submit(_get_board_uuid)
        cpu_future = pool.submit(_get_cpu_id)
        disk_serial = disk_future.result()
        board_uuid = board_future.result()
        cpu_id = cpu_future.result()

    raw = "|".join([disk_serial, board_uuid, cpu_id, _get_machine_guid()])
    digest = hashlib.sha256(raw.encode("utf-8", errors="replace")).hexdigest()
    hw = digest[:16].upper()
    hw = "-".join(hw[i:i+4] for i in range(0, 16, 4))
    _save_cached_hardware_id(hw)
    return hw


# ── Generación y validación de código ───────────────────────────────────────

def validate_code(hardware_id: str, code: str) -> bool:
    """Verifica una licencia V2 usando solo la clave pública RSA."""
    if not isinstance(code, str) or not code.upper().startswith("V2."):
        return False
    try:
        signature = bytes.fromhex(code[3:].replace("-", ""))
    except ValueError:
        return False
    if len(signature) != 256:
        return False
    decoded = pow(int.from_bytes(signature, "big"), _RSA_E, _RSA_N).to_bytes(256, "big")
    clean = hardware_id.replace("-", "").replace(" ", "").upper()
    digest_info = _SHA256_DER_PREFIX + hashlib.sha256(clean.encode("ascii")).digest()
    expected = b"\x00\x01" + b"\xff" * (256 - len(digest_info) - 3) + b"\x00" + digest_info
    # Comparación en tiempo constante -- el resto del proyecto ya usa
    # hmac.compare_digest para comparaciones sensibles (downloader.py,
    # soulseek_client.py, updater.py); esta era la única que seguía usando
    # "==" normal, inconsistente con ese estándar propio.
    #
    # Nota de seguridad (revisión de core/license.py, 8.6.5): lo que
    # hace inviable falsificar un código NO es que esta comparación sea
    # de tiempo constante -- decoded/expected no son secretos (decoded
    # sale de una operación con la clave PÚBLICA, replicable por
    # cualquiera sin oráculo alguno) -- sino que es una comparación del
    # bloque completo de 256 bytes, byte a byte, nunca un prefijo ni una
    # subcadena. Ese es justo el hueco que explota el ataque clásico de
    # Bleichenbacher contra verificadores PKCS#1 v1.5 laxos (los que se
    # conforman con encontrar el DigestInfo en algún punto del bloque e
    # ignoran la basura sobrante). Si algún día se "simplifica" esto a un
    # startswith()/in sobre expected, se vuelve falsificable aunque se
    # conserve compare_digest -- la invariante a proteger es "todo el
    # bloque, nunca un prefijo", no el tiempo constante.
    return hmac.compare_digest(decoded, expected)


# ── Persistencia de la activación ───────────────────────────────────────────

def _license_path() -> Path:
    return get_app_data_dir() / LICENSE_FILE


def load_activation() -> dict:
    """
    Devuelve {'activated': bool, 'code': str}.

    Valida tipos, no solo que el JSON parsee: un license.json manipulado o
    corrompido a mano con "code" numérico o no-string haría explotar a
    validate_code() (usa str.replace) más adelante en is_activated(), justo
    en la ruta crítica de arranque del splash -- mejor tratarlo aquí como
    "no activado" que dejar reventar el arranque con un AttributeError.
    """
    path = _license_path()
    if not path.exists():
        return {"activated": False, "code": ""}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"activated": False, "code": ""}
    if not isinstance(data, dict) or not isinstance(data.get("code"), str):
        return {"activated": False, "code": ""}
    return {"activated": bool(data.get("activated")), "code": data["code"]}


def save_activation(code: str) -> bool:
    """
    Valida el código contra el hardware de este PC y, si es correcto,
    lo guarda en disco. Devuelve True solo si la activación quedó
    persistida de verdad -- si el código es válido pero no se pudo
    escribir license.json (disco lleno, permisos, antivirus...), se
    devuelve False en vez de reportar un éxito que no sobrevive a un
    reinicio de la app (is_activated() no encontraría el archivo y
    volvería a pedir el código, como si nunca se hubiera activado).
    """
    hw = generate_hardware_id()
    if not validate_code(hw, code):
        return False
    try:
        write_json_atomic(
            _license_path(), {"activated": True, "code": code.upper()}, indent=2
        )
    except OSError:
        log.exception("Código válido pero no se pudo guardar license.json")
        return False
    return True


def is_activated() -> bool:
    """
    Comprueba si la app está activada en este PC. Revalida el código
    guardado contra el hardware actual para evitar copiar el archivo de
    licencia de un PC a otro.
    """
    data = load_activation()
    if not data.get("activated") or not data.get("code"):
        return False
    hw = generate_hardware_id()
    return validate_code(hw, data["code"])
