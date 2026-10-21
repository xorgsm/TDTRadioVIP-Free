"""
Obtención y parseo de listas de canales de TDT en formato m3u/m3u8.

Fuente por defecto: listas públicas y gratuitas de iptv-org, mantenidas por
la comunidad: https://github.com/iptv-org/iptv — una por país.
"""
import hashlib
import os
import re
import functools
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional

import requests

from core.config import get_app_data_dir, get_profile_data_dir
from core.http_limits import MAX_PLAYLIST_BYTES, fetch_limited
from core.json_store import read_json, write_json_atomic

# (conexión, lectura): una conexión que no abre en pocos segundos suele ser DNS,
# VPN o proxy y no mejora esperando; el plazo total corta servidores que
# entregan la lista a gotas, ya que el timeout de lectura es por operación.
PLAYLIST_TIMEOUT = (4, 12)
PLAYLIST_DEADLINE_SECONDS = 45

# Pasado este tiempo la lista en caché se muestra igualmente al arrancar, pero
# se revalida contra la red en segundo plano (ver cache_is_stale).
CACHE_TTL_SECONDS = 12 * 3600

CUSTOM_FILE = "tv_channels_custom.json"
# Nombres de canales de la lista PÚBLICA (iptv-org/URL de país, no los
# personalizados) que el usuario ha pedido ocultar -- ver hide_channels()
# más abajo. A diferencia de tv_channels_custom.json, esto no guarda datos
# de ningún canal, solo su nombre: la lista pública se sigue descargando y
# cacheando entera como siempre, esto es un filtro que se aplica encima al
# combinarla con la personalizada (ver
# ui.catalog_load_controller.CatalogLoadController._on_tv_channels_loaded).
HIDDEN_FILE = "tv_channels_hidden.json"

IPTV_ORG_BASE = "https://iptv-org.github.io/iptv/countries"

EXTINF_RE = re.compile(
    r'#EXTINF:-?\d+(?P<attrs>(?:\s+[\w-]+="[^"]*")*)\s*,\s*(?P<name>.+)'
)
ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')


def playlist_url_for(country_code: str) -> str:
    """URL pública de iptv-org para la lista de un país (código ISO alfa-2)."""
    return f"{IPTV_ORG_BASE}/{(country_code or 'es').lower()}.m3u"


def _cache_path_for(playlist_url: str):
    """
    Un archivo de caché por URL (hash corto), no uno solo compartido.

    Con un único "tv_channels_cache.json" para todos los países, cambiar de
    país en Ajustes seguía mostrando la caché del país anterior hasta que
    tocaba "Actualizar canales". Cada URL (país, o una anulación manual de
    usuario avanzado) tiene ahora su propia caché independiente.
    """
    slug = hashlib.md5(playlist_url.encode("utf-8")).hexdigest()[:12]
    return get_app_data_dir() / "cache" / f"tv_channels_cache_{slug}.json"


@dataclass
class Channel:
    name: str
    url: str
    logo: str = ""
    group: str = ""
    tvg_id: str = ""
    alternate_urls: List[str] = field(default_factory=list)


def _channel_from_dict(data) -> Optional[Channel]:
    """Channel desde un dict leído de disco, o None si no encaja: campos
    desconocidos o que faltan, textos que no son str, o alternate_urls que
    no es una lista de str. La interfaz los usa tal cual (setText, VLC...)."""
    if not isinstance(data, dict):
        return None
    try:
        channel = Channel(**data)
    except TypeError:
        return None
    textos = (channel.name, channel.url, channel.logo, channel.group, channel.tvg_id)
    if not all(type(t) is str for t in textos) or not channel.name or not channel.url:
        return None
    alternativas = channel.alternate_urls
    if type(alternativas) is not list or not all(type(u) is str for u in alternativas):
        return None
    return channel


def _load_channel_list(path) -> List[Channel]:
    """Lista de canales guardada en ``path``, descartando solo las entradas
    inválidas. Antes, una sola entrada que no encajara (o un archivo que no
    fuera UTF-8 válido, que ni se capturaba) invalidaba la lista ENTERA --
    y en la personalizada, el siguiente add_custom_channel() guardaba
    encima esa lista vacía más el canal nuevo, perdiendo todos los demás."""
    data = read_json(path, [])
    if not isinstance(data, list):
        return []
    return [c for c in map(_channel_from_dict, data) if c is not None]


def dedupe_channels(channels: List[Channel]) -> List[Channel]:
    """
    Quita canales repetidos por nombre (sin distinguir mayúsculas ni
    espacios sobrantes), quedándose con la primera aparición. No es raro
    que una misma lista M3U pública traiga el mismo canal dos veces (varias
    URLs "de respaldo" bajo el mismo nombre), y tampoco que la lista del
    país por defecto y una lista personalizada importada compartan canales
    -- de ahí que esto se aplique tanto al final de parse_m3u() (dentro de
    una sola lista) como al combinar la lista del país con la personalizada
    (entre dos fuentes distintas).
    """
    vistos = {}
    # URLs ya conocidas por canal (la principal y las de respaldo): buscar en
    # la lista alternate_urls era cuadrático con muchas URLs bajo un nombre.
    urls_vistas: dict = {}
    resultado: List[Channel] = []
    for ch in channels:
        clave = ch.name.strip().casefold()
        if clave in vistos:
            original = resultado[vistos[clave]]
            conocidas = urls_vistas[clave]
            if ch.url and ch.url not in conocidas:
                conocidas.add(ch.url)
                original.alternate_urls.append(ch.url)
            continue
        vistos[clave] = len(resultado)
        urls_vistas[clave] = {ch.url, *ch.alternate_urls}
        resultado.append(ch)
    return resultado


def decode_playlist(data: bytes) -> str:
    """Texto de una lista M3U a partir de sus bytes: UTF-8 (con o sin BOM)
    y, si no lo es, Windows-1252 -- el "ANSI" con el que el Bloc de notas
    y muchas herramientas de Windows guardan las listas en español.

    Antes se leía con errors="ignore" (un archivo en ANSI perdía en
    silencio todas las letras acentuadas: "Canción" -> "Cancin"), o con
    resp.text de requests, que para un text/* sin charset supone
    ISO-8859-1 y convertía una lista UTF-8 en mojibake ("CanciÃ³n").
    """
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


def read_playlist_source(source: str, timeout: float = 15) -> str:
    """Texto de una lista M3U desde una URL http(s) o una ruta local,
    decodificado con decode_playlist(). Lanza requests.RequestException u
    OSError si no se puede leer -- quien llama decide cómo avisar."""
    if source.lower().startswith(("http://", "https://")):
        return decode_playlist(
            fetch_limited(source, max_bytes=MAX_PLAYLIST_BYTES, timeout=timeout)
        )
    return decode_playlist(Path(source).read_bytes())


def parse_m3u(text: str, *, deduplicate: bool = True) -> List[Channel]:
    # Un BOM que llegue hasta aquí (texto ya decodificado por otra vía)
    # haría que la primera línea no empezara por "#EXTINF" y se perdiera
    # el primer canal de una lista sin cabecera #EXTM3U.
    text = text.lstrip("﻿")
    lines = [raw.strip() for raw in text.splitlines() if raw.strip()]
    channels: List[Channel] = []
    pending: Channel | None = None
    for line in lines:
        if line.startswith("#EXTINF"):
            m = EXTINF_RE.match(line)
            if not m:
                pending = None
                continue
            attrs = dict(ATTR_RE.findall(m.group("attrs") or ""))
            pending = Channel(
                name=m.group("name").strip(),
                url="",
                logo=attrs.get("tvg-logo", ""),
                group=attrs.get("group-title", ""),
                tvg_id=attrs.get("tvg-id", ""),
            )
        elif line.startswith("#"):
            continue
        else:
            if pending is not None:
                pending.url = line
                channels.append(pending)
                pending = None
    return dedupe_channels(channels) if deduplicate else channels


# Desfase admitido entre la fecha del fichero de caché y el reloj del sistema.
_CACHE_CLOCK_SKEW_SECONDS = 5


def cache_is_stale(
    playlist_url: str, max_age: float = CACHE_TTL_SECONDS, *, missing: bool = True
) -> bool:
    """¿La caché de esta lista es más vieja que ``max_age`` segundos?

    ``missing`` es la respuesta si no hay caché. Una fecha futura (reloj
    atrasado, fichero copiado) cuenta como vieja: de otro modo nunca caduca.
    Se tolera un pequeño desfase: justo tras renovarla con os.utime, la
    fecha del fichero puede ir unas milésimas por delante de time.time().
    """
    try:
        age = time.time() - _cache_path_for(playlist_url).stat().st_mtime
    except OSError:
        return missing
    return age > max_age or age < -_CACHE_CLOCK_SKEW_SECONDS


def fetch_tv_channels(playlist_url: str, force_refresh: bool = False) -> List[Channel]:
    """Descarga la lista de canales; si falla, usa la caché local en disco."""
    cache_path = _cache_path_for(playlist_url)

    cached = _load_channel_list(cache_path)

    if not force_refresh and cached:
        return cached

    try:
        content = fetch_limited(
            playlist_url, max_bytes=MAX_PLAYLIST_BYTES,
            timeout=PLAYLIST_TIMEOUT, deadline=PLAYLIST_DEADLINE_SECONDS,
        )
        channels = parse_m3u(decode_playlist(content))
        if channels:
            # Reescribir con fsync una caché idéntica solo retrasa la entrega
            # del resultado (más con antivirus o un disco lento).
            try:
                if channels != cached:
                    write_json_atomic(cache_path, [asdict(c) for c in channels])
                else:
                    os.utime(cache_path)  # sigue vigente: renueva su antigüedad
            except OSError:
                pass  # no poder cachear no invalida la lista ya descargada
            return channels
    except requests.RequestException:
        pass

    return cached


# La carga combinada del catálogo corre en un worker y load_custom_channels()
# puede reescribir el fichero al autorrepararlo: todas las secuencias
# leer-modificar-escribir de la lista personalizada van serializadas para que
# una no pise a otra (p. ej. añadir un canal durante la carga inicial).
_CUSTOM_WRITE_LOCK = threading.RLock()


def _custom_serialized(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        with _CUSTOM_WRITE_LOCK:
            return func(*args, **kwargs)
    return wrapper


def _save_custom(channels: List[Channel]) -> None:
    """Punto único de guardado de la lista personalizada."""
    path = get_profile_data_dir() / CUSTOM_FILE
    try:
        write_json_atomic(path, [asdict(c) for c in channels])
    except OSError:
        pass
    with _CUSTOM_NAMES_LOCK:
        _CUSTOM_NAMES_CACHE.pop(path, None)


@_custom_serialized
def load_custom_channels() -> List[Channel]:
    channels = _load_channel_list(get_profile_data_dir() / CUSTOM_FILE)

    # Auto-reparación: si esta lista se guardó antes de que parse_m3u()
    # quitara duplicados (importar la misma lista dos veces, o importar una
    # que ya traía el mismo canal repetido, dejaba entradas duplicadas
    # guardadas en disco para siempre -- dedupe_channels() en el import
    # solo evita añadir MÁS duplicados a partir de ahora, no limpia los que
    # ya estaban). Si al desduplicar cambia algo, se guarda ya limpio de
    # una vez -- así no hace falta ninguna acción manual del usuario.
    limpios = dedupe_channels(channels)
    if len(limpios) != len(channels):
        _save_custom(limpios)
    return limpios


# Nombres de la lista personalizada, memorizados por fecha y tamaño del
# fichero. Favoritos, historial y el poblado de TV solo necesitan saber QUÉ
# canales son propios, y releer un JSON de miles de canales cuesta decenas de
# milisegundos en el hilo de la interfaz cada vez.
_CUSTOM_NAMES_CACHE: dict = {}
_CUSTOM_NAMES_LOCK = threading.Lock()


def custom_channel_names() -> frozenset:
    path = get_profile_data_dir() / CUSTOM_FILE
    try:
        stat = path.stat()
    except OSError:
        return frozenset()
    stamp = (stat.st_mtime_ns, stat.st_size)
    with _CUSTOM_NAMES_LOCK:
        cached = _CUSTOM_NAMES_CACHE.get(path)
        if cached is not None and cached[0] == stamp:
            return cached[1]
    names = frozenset(channel.name for channel in load_custom_channels())
    with _CUSTOM_NAMES_LOCK:
        _CUSTOM_NAMES_CACHE[path] = (stamp, names)
    return names


@_custom_serialized
def add_custom_channel(channel: Channel) -> None:
    channels = load_custom_channels()
    channels.append(channel)
    _save_custom(channels)


@_custom_serialized
def add_custom_channels(channels: List[Channel]) -> None:
    """
    Añade varios canales de golpe con una sola lectura y una sola escritura
    del archivo, en vez de una por canal (ver add_custom_channel). Pensada
    para "Importar lista M3U…": con listas de cientos o miles de canales,
    llamar a add_custom_channel() en bucle relee y reescribe el JSON entero
    en cada iteración, cada vez más grande — aquí se acumula en memoria y
    se guarda una única vez al final.
    """
    if not channels:
        return
    actuales = load_custom_channels()
    actuales.extend(channels)
    _save_custom(actuales)


@_custom_serialized
def update_custom_channel(old_name: str, channel: Channel) -> None:
    _save_custom([channel if c.name == old_name else c for c in load_custom_channels()])


@_custom_serialized
def remove_custom_channel(name: str) -> None:
    _save_custom([c for c in load_custom_channels() if c.name != name])


@_custom_serialized
def remove_custom_channels(names) -> int:
    """
    Quita varios canales de golpe con una sola lectura y una sola escritura
    del archivo (ver add_custom_channels) -- pensada para el borrado múltiple
    del gestor de canales personalizados (ManageChannelsDialog), en vez de
    llamar a remove_custom_channel() en bucle, que releería y reescribiría
    el JSON entero por cada canal borrado. Devuelve cuántos se borraron de
    verdad (puede ser menos que len(names) si algún nombre ya no existía).
    """
    nombres = set(names)
    if not nombres:
        return 0
    actuales = load_custom_channels()
    restantes = [c for c in actuales if c.name not in nombres]
    borrados = len(actuales) - len(restantes)
    if borrados:
        _save_custom(restantes)
    return borrados


# ── Canales ocultos de la lista pública ─────────────────────────────────────
#
# Los personalizados (arriba) el usuario los añadió él mismo, así que
# borrarlos de verdad tiene sentido. Los de la lista pública (iptv-org o la
# URL de país que sea) se vuelven a descargar en cada "Actualizar canales",
# así que "borrarlos" no se sostendría -- volverían la próxima vez. En vez
# de eso se guarda solo el NOMBRE de los que no se quieren ver, y se filtran
# al combinar la lista pública con la personalizada. Reversible en cualquier
# momento desde ManageChannelsDialog ("Ocultados" -> Restaurar).

def _hidden_path():
    return get_profile_data_dir() / HIDDEN_FILE


def load_hidden_channel_names() -> set:
    data = read_json(_hidden_path(), [])
    if not isinstance(data, list):
        return set()
    return {nombre for nombre in data if isinstance(nombre, str)}


def _save_hidden(names: set) -> None:
    try:
        write_json_atomic(_hidden_path(), sorted(names))
    except OSError:
        pass


def hide_channels(names) -> int:
    """
    Añade nombres a la lista de ocultos. Devuelve cuántos son nuevos
    (nombres ya ocultos antes no cuentan). No comprueba que el nombre
    exista de verdad en ninguna lista pública -- solo guarda el filtro.
    """
    nuevos = set(names)
    if not nuevos:
        return 0
    actuales = load_hidden_channel_names()
    combinados = actuales | nuevos
    añadidos = len(combinados) - len(actuales)
    if añadidos:
        _save_hidden(combinados)
    return añadidos


def unhide_channels(names) -> int:
    """Quita nombres de la lista de ocultos (los vuelve a mostrar)."""
    quitar = set(names)
    if not quitar:
        return 0
    actuales = load_hidden_channel_names()
    restantes = actuales - quitar
    quitados = len(actuales) - len(restantes)
    if quitados:
        _save_hidden(restantes)
    return quitados


def filter_hidden(channels: List[Channel]) -> List[Channel]:
    """Quita de `channels` los que estén en la lista de ocultos."""
    ocultos = load_hidden_channel_names()
    if not ocultos:
        return channels
    return [c for c in channels if c.name not in ocultos]


# ── Fallos consecutivos por canal (aviso de auto-ocultar) ───────────────────
#
# PlaybackController cuenta cuántas veces seguidas falla un canal al
# reproducirse y, a partir de cierto número, ofrece ocultarlo (ver
# hide_channels() arriba) con un aviso no bloqueante en vez de asumir que
# es un fallo puntual de red. Se guarda por NOMBRE, no por URL: si cambia
# la URL de un canal personalizado es razonable que el contador arranque
# de cero. "Consecutivos" de verdad (no total histórico): cada vez que el
# canal responde bien se resetea, ver reset_channel_failures().

FAILCOUNT_FILE = "tv_channels_failcount.json"


def _failcount_path():
    return get_profile_data_dir() / FAILCOUNT_FILE


def _load_failcounts() -> dict:
    data = read_json(_failcount_path(), {})
    if not isinstance(data, dict):
        return {}
    # Solo contadores enteros de verdad (bool es subclase de int, fuera):
    # un valor raro haría que record_channel_failure() lanzara TypeError
    # desde el manejo de errores de reproducción.
    return {nombre: n for nombre, n in data.items() if type(n) is int}


def _save_failcounts(counts: dict) -> None:
    try:
        write_json_atomic(_failcount_path(), counts)
    except OSError:
        pass


def record_channel_failure(name: str) -> int:
    """Suma un fallo consecutivo para ese canal y devuelve el total acumulado."""
    if not name:
        return 0
    counts = _load_failcounts()
    counts[name] = counts.get(name, 0) + 1
    _save_failcounts(counts)
    return counts[name]


def reset_channel_failures(name: str) -> None:
    """Se llama cuando el canal responde bien -- limpia su contador si tenía alguno."""
    if not name:
        return
    counts = _load_failcounts()
    if name in counts:
        del counts[name]
        _save_failcounts(counts)
