"""
Copia de seguridad de los datos del usuario en un solo archivo.

Reúne en un único JSON todo lo que vive normalmente repartido en varios
archivos dentro de %APPDATA%\\CoderByXOR\\TDTRadioVIP\\: ajustes (país,
EPG, carpeta de grabaciones...), favoritos, historial, y los canales o
emisoras que el usuario haya añadido a mano. Útil sobre todo al cambiar de
PC — como pasó justo antes de construir esto — para no tener que rehacer
todo eso desde cero.

Coder By X@R
"""
import json
from datetime import datetime, timedelta
from pathlib import Path

from core.config import get_app_data_dir, get_profile_data_dir, APP_VERSION
from core.json_store import replace_json_files_atomically, write_json_atomic

BACKUP_FORMAT_VERSION = 1
MAX_BACKUP_BYTES = 100 * 1024 * 1024

# Nombre de archivo -> clave bajo la que se guarda dentro del backup.
# settings.json es de la instalación entera (no cambia con el perfil);
# el resto son datos "de quién los usa" y viven en la carpeta del perfil
# activo (ver core.config.get_profile_data_dir) -- así, exportar/importar
# una copia de seguridad siempre opera sobre el perfil que esté activo en
# ese momento, igual que vería esos mismos archivos el resto de la app.
_ARCHIVOS_GLOBALES = {
    "settings.json": "settings",
}
_ARCHIVOS_PERFIL = {
    "favorites.json": "favorites",
    "history.json": "history",
    "tv_channels_custom.json": "custom_tv_channels",
    "radio_stations_custom.json": "custom_radio_stations",
    "tv_channels_hidden.json": "hidden_tv_channels",
    "radio_stations_hidden.json": "hidden_radio_stations",
    "tv_channels_failcount.json": "tv_channels_failcount",
    "radio_stations_failcount.json": "radio_stations_failcount",
    "stream_health.json": "stream_health",
    "torrent_history.json": "torrent_history",
    "epg_recordings.json": "epg_recordings",
    "epg_reminders.json": "epg_reminders",
    "recurring_recordings.json": "recurring_recordings",
    "recurring_recordings_sync.json": "recurring_recordings_sync",
}

# Claves cuyo contenido es un dict en vez de una lista -- el resto de
# _ARCHIVOS_PERFIL/_ARCHIVOS_GLOBALES son listas. Usado por import_backup()
# para validar el tipo de cada sección antes de escribirla a disco.
_CLAVES_DICT = {"settings", "stream_health", "recurring_recordings_sync",
                "tv_channels_failcount", "radio_stations_failcount"}


def export_backup(destino: str, *, app_data_dir=None, profile_data_dir=None) -> None:
    """
    Vuelca todos los archivos de datos del usuario que existan en un único
    JSON en `destino`. Los que no existan (p. ej. nunca se añadió ningún
    canal personalizado) simplemente no aparecen en el backup — no es un
    error, es lo esperable en una instalación nueva.
    """
    contenido = {
        "app": "TDT & Radio VIP",
        "backup_format_version": BACKUP_FORMAT_VERSION,
        "app_version_at_export": APP_VERSION,
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    app_data_dir = Path(app_data_dir) if app_data_dir is not None else get_app_data_dir()
    profile_data_dir = Path(profile_data_dir) if profile_data_dir is not None else get_profile_data_dir()
    for nombre_archivo, clave, carpeta in (
        *((n, c, app_data_dir) for n, c in _ARCHIVOS_GLOBALES.items()),
        *((n, c, profile_data_dir) for n, c in _ARCHIVOS_PERFIL.items()),
    ):
        ruta = carpeta / nombre_archivo
        if not ruta.exists():
            continue
        try:
            contenido[clave] = json.loads(ruta.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            # Un archivo de origen corrupto no debe tumbar todo el backup;
            # simplemente se omite esa pieza concreta.
            continue

    write_json_atomic(Path(destino), contenido, indent=2)


def import_backup(origen: str) -> list[str]:
    """
    Restaura un backup generado por export_backup(), sobrescribiendo los
    archivos actuales del perfil activo (y los ajustes globales). Devuelve
    la lista de qué se ha restaurado (para poder mostrarlo en la
    interfaz), y lanza ValueError si el archivo no tiene la pinta de ser
    un backup válido de esta app.
    """
    source_path = Path(origen)
    try:
        backup_size = source_path.stat().st_size
    except OSError:
        raise
    if backup_size > MAX_BACKUP_BYTES:
        raise ValueError("La copia de seguridad supera el tamaño máximo permitido.")
    with source_path.open("rb") as source:
        raw_backup = source.read(MAX_BACKUP_BYTES + 1)
    if len(raw_backup) > MAX_BACKUP_BYTES:
        raise ValueError("La copia de seguridad supera el tamaño máximo permitido.")
    datos = json.loads(raw_backup.decode("utf-8"))
    if (
        not isinstance(datos, dict)
        or datos.get("app") != "TDT & Radio VIP"
        or type(datos.get("backup_format_version")) is not int
        or datos.get("backup_format_version") != BACKUP_FORMAT_VERSION
    ):
        raise ValueError("Ese archivo no es una copia de seguridad de TDT & Radio VIP.")

    files = (
        *((n, c, get_app_data_dir()) for n, c in _ARCHIVOS_GLOBALES.items()),
        *((n, c, get_profile_data_dir()) for n, c in _ARCHIVOS_PERFIL.items()),
    )
    for _file_name, key, _directory in files:
        if key not in datos:
            continue
        expected_type = dict if key in _CLAVES_DICT else list
        if not isinstance(datos[key], expected_type):
            raise ValueError(f"La sección {key!r} no tiene un tipo válido.")

    values: dict[Path, object] = {}
    restored: list[str] = []
    for file_name, key, directory in files:
        if key not in datos:
            continue
        values[directory / file_name] = datos[key]
        restored.append(key)

    replace_json_files_atomically(values, indent=2)
    return restored


def sugerir_nombre_backup() -> str:
    """Nombre de archivo sugerido para el diálogo de guardar."""
    fecha = datetime.now().strftime("%Y-%m-%d")
    return f"TDTRadioVIP_backup_{fecha}.json"


def create_automatic_backup(
    directory: str | Path,
    *,
    interval_days: int = 1,
    retention: int = 7,
    now: datetime | None = None,
    app_data_dir: Path | None = None,
    profile_data_dir: Path | None = None,
) -> Path | None:
    """Crea como máximo una copia por intervalo y aplica retención."""
    if interval_days < 1 or retention < 1:
        raise ValueError("El intervalo y la retención deben ser positivos.")
    current = now or datetime.now()
    target_dir = Path(directory)
    target_dir.mkdir(parents=True, exist_ok=True)
    destination = target_dir / f"TDTRadioVIP_auto_{current:%Y-%m-%d_%H%M%S}.json"
    if destination.is_file():
        return None
    existing = sorted(
        (path for path in target_dir.glob("TDTRadioVIP_auto_*.json") if path.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if existing:
        latest = datetime.fromtimestamp(existing[0].stat().st_mtime)
        # Un reloj corregido hacia atrás o un archivo copiado con fecha futura
        # no debe desactivar las copias automáticas indefinidamente.
        if latest <= current and current - latest < timedelta(days=interval_days):
            return None
    source_dirs = {}
    if app_data_dir is not None:
        source_dirs["app_data_dir"] = app_data_dir
    if profile_data_dir is not None:
        source_dirs["profile_data_dir"] = profile_data_dir
    export_backup(str(destination), **source_dirs)
    existing = sorted(
        (path for path in target_dir.glob("TDTRadioVIP_auto_*.json") if path.is_file()),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for obsolete in existing[retention:]:
        obsolete.unlink(missing_ok=True)
    return destination


def run_automatic_backup(*args, **kwargs) -> bool:
    """Resultado para FetchWorker: True creada, False no toca, None si falla.

    Las excepciones las convierte FetchWorker en None. Las rutas capturadas
    antes de arrancar evitan mezclar perfiles si se cambia durante la copia.
    """
    return create_automatic_backup(*args, **kwargs) is not None
