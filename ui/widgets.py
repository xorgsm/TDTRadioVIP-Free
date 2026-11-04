"""
Widgets reutilizables para la interfaz moderna de TDT & Radio VIP.
"""
import hashlib
import random
from collections import OrderedDict, deque
from functools import lru_cache

import requests
from PySide6.QtCore import QRectF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QWidget

from core.config import get_app_data_dir
from core.http_limits import MAX_LOGO_BYTES, fetch_limited
from core.logger import get_logger
from core.net_safety import is_safe_download_url
from ui import palette
from ui.catalog_labels import humanize_group, split_name_tags
from ui.fetch_worker import FetchWorker
from ui.icons import icon_radio, icon_tv

log = get_logger(__name__)

ROLE_DATA = Qt.UserRole
ROLE_LOGO = Qt.UserRole + 1
ROLE_PLAYING = Qt.UserRole + 2
ROLE_FAV = Qt.UserRole + 3
ROLE_CUSTOM = Qt.UserRole + 4
ROLE_HEALTH = Qt.UserRole + 5
ROLE_LOGO_REQUESTED = Qt.UserRole + 6

# Logos: se piden por docenas al pintar el catálogo, así que un host lento no
# debe retener un hilo muchos segundos (el logo se reintenta al volver a verlo).
LOGO_TIMEOUT = (3.05, 6)
LOGO_DEADLINE_SECONDS = 20
LOGO_MAX_REDIRECTS = 3
# Lado máximo con que se guarda/decodifica un logo (el mayor uso es 150 px).
LOGO_MAX_SIDE = 256

# Paleta de acento por categoría (Deportes, Infantiles, Noticias...). No es
# un mapeo fijo nombre->color: con canales internacionales las categorías
# cambian de un país a otro y mantener esa lista a mano sería interminable.
# En vez de eso, cada nombre de categoría se hashea de forma determinista a
# un color de esta paleta, así que "Deportes" siempre sale del mismo color
# en cada sesión, sin tener que mantener un diccionario.
CATEGORY_PALETTE = (
    palette.ACCENT_CAST,  # verde azulado
    palette.ACCENT_INFO,  # azul cielo
    palette.ACCENT_HISTORY,  # lavanda
    palette.ACCENT_HOME,  # rosa
    palette.SUCCESS,  # verde
    palette.ACCENT_CATEGORY_ORANGE,  # naranja
    palette.ACCENT_DOWNLOAD,  # lima
    palette.ACCENT_FAVORITE,  # amarillo
)


@lru_cache(maxsize=256)
@lru_cache(maxsize=4096)
def _display_name(name: str) -> tuple[str, tuple[str, ...]]:
    """Nombre para pintar sin las etiquetas [Geo-blocked]/[Not 24/7] del
    catálogo, que pasan traducidas al subtítulo (ver ui/catalog_labels.py).
    Cacheado: paint() se llama por cada fila visible en cada repintado."""
    clean, tags = split_name_tags(name or "")
    return clean, tuple(tags)


@lru_cache(maxsize=1024)
def _display_group(group: str) -> str:
    return humanize_group(group)


def _category_hex(clave: str) -> str:
    idx = int(hashlib.md5(clave.encode("utf-8")).hexdigest(), 16) % len(CATEGORY_PALETTE)
    return CATEGORY_PALETTE[idx]



def _accent_tint(alpha: int) -> QColor:
    color = QColor(palette.ACCENT)
    color.setAlpha(alpha)
    return color

def category_color(name: str) -> QColor:
    """
    Color estable para una categoría dada (o gris neutro si no hay
    ninguna). El hash MD5 en sí se cachea (_category_hex) porque
    ChannelDelegate.paint() llama a esta función varias veces por fila en
    cada repintado (incluido cada frame de scroll) -- con listas de
    cientos de canales, recalcular el mismo hash para "Deportes" o
    "Generalistas" una y otra vez es trabajo repetido de sobra.

    Se cachea solo el resultado inmutable (el color en hexadecimal), no el
    QColor que se devuelve: el código que llama a esta función hace cosas
    como cat_color.setAlpha(...) sobre lo que le llega, y compartir la
    MISMA instancia de QColor entre llamadas dejaría ese cambio de
    opacidad "pegado" para todas las filas de esa categoría en vez de
    solo la que lo pidió.
    """
    if not name:
        return QColor(palette.TEXT_DIM)
    return QColor(_category_hex(name.strip().lower()))


def rounded_pixmap(pixmap: QPixmap, size: int, radius: int) -> QPixmap:
    """Recorta y redondea un pixmap para usarlo como miniatura de tarjeta."""
    if pixmap.isNull():
        return pixmap
    scaled = pixmap.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    x = max(0, (scaled.width() - size) // 2)
    y = max(0, (scaled.height() - size) // 2)
    scaled = scaled.copy(x, y, size, size)

    rounded = QPixmap(size, size)
    rounded.fill(Qt.transparent)
    painter = QPainter(rounded)
    painter.setRenderHint(QPainter.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0, 0, size, size, radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, scaled)
    painter.end()
    return rounded





def _download_logo_bytes(url: str) -> bytes:
    """
    Descarga cruda con ``requests`` (mismo mecanismo que EPG/canales/radio/
    actualizaciones en vez de QNetworkAccessManager -- ver el porqué en el
    docstring de LogoLoader). FetchWorker.run() ya envuelve la llamada en
    try/except y convierte cualquier excepción en ``None`` para el
    callback, así que aquí no hace falta capturar nada a mano.

    El `tvg-logo` viene de listas que pueden ser ajenas y se pide solo al
    pintar el catálogo: se rechazan loopback, metadatos de nube y las
    redirecciones hacia ellos.
    """
    return fetch_limited(
        url, max_bytes=MAX_LOGO_BYTES, timeout=LOGO_TIMEOUT,
        deadline=LOGO_DEADLINE_SECONDS, max_redirects=LOGO_MAX_REDIRECTS,
        validate_url=is_safe_download_url,
    )


def _read_logo_image(url, cache_file):
    """Lee/descarga y decodifica fuera de la UI; nunca crea un QPixmap.

    En disco se guarda ya reducido a LOGO_MAX_SIDE: un logo de origen de
    miles de píxeles se decodificaba entero en cada arranque solo para
    pintarlo a 54 px, y ocupaba en la caché varias veces lo necesario.
    """
    image = QImage(str(cache_file)) if cache_file.is_file() else QImage()
    if image.isNull():
        try:
            data = _download_logo_bytes(url)
        except requests.RequestException as exc:
            # 404/429/timeouts de servidores de logos son normales; no
            # merecen un traceback entero en el log por cada uno.
            log.debug("Logo no disponible (%s): %s", url, exc)
            return None
        image = QImage.fromData(data)
        if image.isNull():
            return None
        if max(image.width(), image.height()) > LOGO_MAX_SIDE:
            image = image.scaled(LOGO_MAX_SIDE, LOGO_MAX_SIDE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        image.save(str(cache_file), "PNG")
    elif max(image.width(), image.height()) > LOGO_MAX_SIDE:
        # Caché antigua guardada a tamaño original.
        image = image.scaled(LOGO_MAX_SIDE, LOGO_MAX_SIDE, Qt.KeepAspectRatio, Qt.SmoothTransformation)
    return image


class LogoLoader:
    """
    Descarga logos de canales/emisoras en segundo plano y los cachea en
    disco, con un límite de descargas simultáneas.

    Sin ese límite, poblar una lista de tamaño medio (un país con varios
    cientos de canales) con la caché de logos vacía lanzaba una petición
    de red por canal DE GOLPE -- cientos de peticiones HTTP concurrentes
    al mismo servidor, que ralentizan tanto la red como la cola de señales
    del hilo de la interfaz mientras van llegando las respuestas. Es la
    misma familia de problema que podría causar un catálogo mundial de
    miles de canales, a menor escala pero real igualmente con listas de un
    solo país ya grandes.
    Las peticiones de más se encolan y se lanzan según van terminando las
    anteriores, sin cambiar nada de cara a quien llama a load().

    Cada descarga corre en su propio FetchWorker (QThread) en vez de por
    QNetworkAccessManager: con catálogos grandes, cientos de peticiones
    HTTPS concurrentes contra el backend TLS empaquetado de Qt
    (PySide6/plugins/tls/qopensslbackend.dll + libssl/libcrypto propios)
    terminaban crasheando la app entera con una violación de acceso
    (0xc0000005, llamada a través de un puntero de función nulo dentro de
    libssl/libcrypto) -- justo al arrancar, que es cuando se piden más
    logos de golpe. FetchWorker usa el módulo ssl de Python (el mismo
    stack que ya usan EPG/canales/radio/actualizaciones sin problema), y
    además ya se integra solo con el cierre ordenado de la app
    (shutdown_workers(FetchWorker.active_workers()) en MainWindow), cosa
    que las QNetworkReply sueltas de antes no hacían.
    """

    _MAX_CONCURRENTES = 8
    _MAX_CACHE_ENTRIES = 2048

    def __init__(self):
        self.cache_dir = get_app_data_dir() / "cache" / "logos"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._workers = []
        self._pendientes = deque()  # URLs únicas pendientes; popleft() es O(1)
        self._solicitudes = {}  # url -> (cache_file, [(callback, size), ...])
        self._en_vuelo = 0
        # Caché EN MEMORIA de logos ya decodificados y redondeados, por
        # (url, size). El caché en disco (cache_file de abajo) evita volver
        # a descargar, pero cada load() con acierto de caché en disco
        # todavía leía el PNG, lo decodificaba y le redondeaba la esquina
        # de cero -- con un catálogo grande eso se repite entero cada vez
        # que se repuebla la lista (al arrancar, al refrescar, al importar
        # más canales encima...), varias veces para los MISMOS canales.
        # Con listas de miles de canales y varios poblados seguidos
        # durante el arranque, esa redecodificación repetida es la que se
        # notaba como lentitud sostenida (no solo un pico al principio) --
        # con esto, la segunda vez que se pide el mismo logo al mismo
        # tamaño sale directo de memoria, sin tocar el disco.
        self._pixmap_cache = OrderedDict()

    def _get_cached_pixmap(self, cache_key):
        pixmap = self._pixmap_cache.get(cache_key)
        if pixmap is not None:
            self._pixmap_cache.move_to_end(cache_key)
        return pixmap

    def _cache_pixmap(self, cache_key, pixmap):
        self._pixmap_cache[cache_key] = pixmap
        self._pixmap_cache.move_to_end(cache_key)
        while len(self._pixmap_cache) > self._MAX_CACHE_ENTRIES:
            self._pixmap_cache.popitem(last=False)

    def load(self, url: str, callback, size: int = 44):
        if not url:
            return
        cache_key = (url, size)
        cached_pixmap = self._get_cached_pixmap(cache_key)
        if cached_pixmap is not None:
            callback(cached_pixmap)
            return

        cache_file = self.cache_dir / (hashlib.md5(url.encode("utf-8")).hexdigest() + ".png")
        solicitud = self._solicitudes.get(url)
        if solicitud is not None:
            solicitud[1].append((callback, size))
            return

        self._solicitudes[url] = (cache_file, [(callback, size)])
        if self._en_vuelo >= self._MAX_CONCURRENTES:
            self._pendientes.append(url)
            return
        self._lanzar(url)

    def _lanzar(self, url: str):
        cache_file, callbacks = self._solicitudes[url]
        self._en_vuelo += 1
        worker = FetchWorker(_read_logo_image, url, cache_file)
        self._workers.append(worker)

        def _on_finished(data):
            try:
                if data is not None and not data.isNull():
                    pix = QPixmap.fromImage(data)
                    redondeados = {}
                    for callback, size in callbacks:
                        logo = redondeados.get(size)
                        if logo is None:
                            logo = rounded_pixmap(pix, size, size // 4)
                            redondeados[size] = logo
                            self._cache_pixmap((url, size), logo)
                        try:
                            callback(logo)
                        except RuntimeError:
                            # Un consumidor eliminado no cancela los demás.
                            continue
            except RuntimeError:
                pass
            finally:
                self._solicitudes.pop(url, None)
                if worker in self._workers:
                    self._workers.remove(worker)
                self._en_vuelo -= 1
                self._lanzar_siguiente_pendiente()

        worker.done.connect(_on_finished)
        worker.start()

    def _lanzar_siguiente_pendiente(self):
        while self._pendientes and self._en_vuelo < self._MAX_CONCURRENTES:
            url = self._pendientes.popleft()
            solicitud = self._solicitudes.get(url)
            if solicitud is None:
                continue
            self._lanzar(url)

class EqualizerWidget(QWidget):
    """Ecualizador animado que sustituye al vídeo cuando se escucha radio."""

    # Fracción del salto hacia el nuevo objetivo aleatorio que se recorre en
    # cada frame: rápida al subir (ataque), lenta al bajar (caída) -- el
    # mismo comportamiento asimétrico de un VU-metro real, que es lo que
    # hace que el movimiento se lea como "picos que caen" en vez del
    # parpadeo uniforme y robótico de saltar directo al valor aleatorio
    # cada vez (como hacía antes esta clase).
    _ATAQUE = 0.55
    _CAIDA = 0.18

    def __init__(self, parent=None, bars: int = 9):
        super().__init__(parent)
        self.setObjectName("equalizerWidget")
        self.bars = bars
        self._heights = [0.15] * bars
        # Sin acceso al espectro real de audio (libVLC no lo expone sin
        # callbacks C de bajo nivel, arriesgado de meter sin poder probarlo
        # contra hardware real), el movimiento sigue siendo aleatorio -- pero
        # la AMPLITUD sí sigue al volumen/silencio de verdad (ver
        # set_intensity(), llamado desde PlaybackController en cada cambio
        # de volumen o al silenciar): con el volumen a 0 o en mute, las
        # barras quedan casi planas en vez de moviéndose igual que a
        # volumen alto, que es la señal visual que de verdad importa.
        self._intensity = 1.0
        self.timer = QTimer(self)
        self.timer.setInterval(90)
        self.timer.timeout.connect(self._animate)
        self.setMinimumHeight(200)

    def start(self):
        self.timer.start()

    def stop(self):
        self.timer.stop()
        self._heights = [0.12] * self.bars
        self.update()

    def set_intensity(self, level: float):
        """level: 0.0 (silenciado) a 1.0 (volumen máximo)."""
        self._intensity = max(0.0, min(1.0, level))

    def _animate(self):
        suelo = 0.08
        nuevas = []
        for h in self._heights:
            objetivo = suelo + (random.uniform(0.15, 1.0) - suelo) * self._intensity
            factor = self._ATAQUE if objetivo > h else self._CAIDA
            nuevas.append(h + (objetivo - h) * factor)
        self._heights = nuevas
        self.update()

    def paintEvent(self, _event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        margin = w * 0.12
        usable = w - 2 * margin
        bar_w = usable / (self.bars * 1.8)
        gap = bar_w * 0.8
        x = margin
        base_y = h * 0.78
        max_bar_h = h * 0.5

        for i, hf in enumerate(self._heights):
            bar_h = max_bar_h * hf
            rect = QRectF(x, base_y - bar_h, bar_w, bar_h)
            base_color = QColor(CATEGORY_PALETTE[i % len(CATEGORY_PALETTE)])
            gradient = QLinearGradient(0, base_y - bar_h, 0, base_y)
            gradient.setColorAt(0, base_color.lighter(115))
            gradient.setColorAt(1, base_color.darker(170))
            painter.setPen(Qt.NoPen)
            painter.setBrush(gradient)
            painter.drawRoundedRect(rect, bar_w / 2, bar_w / 2)
            x += bar_w + gap
        painter.end()


class ChannelGridDelegate(QStyledItemDelegate):
    """
    Tarjeta cuadrada para la vista en cuadrícula de TV y Radio (alternativa a
    ChannelDelegate en modo lista, ver el botón junto al filtro de
    categoría en la barra superior de Televisión). Mismo lenguaje visual
    (cristal esmerilado, halo dorado en la que suena) pero pensada para un
    QListWidget en IconMode en vez de una fila ancha.
    """

    CARD_SIZE = 168
    LOGO_RATIO = 0.55

    def sizeHint(self, option, index):
        return QSize(self.CARD_SIZE, self.CARD_SIZE)

    def paint(self, painter: QPainter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        rect = QRectF(option.rect.adjusted(8, 8, -8, -8))
        radius = 14
        data = index.data(ROLE_DATA) or {}
        is_playing = bool(index.data(ROLE_PLAYING))
        is_fav = bool(index.data(ROLE_FAV))
        is_hover = bool(option.state & QStyle.State_MouseOver)
        logo = index.data(ROLE_LOGO)

        card_path = QPainterPath()
        card_path.addRoundedRect(rect, radius, radius)

        if is_playing:
            fill, border = _accent_tint(56), QColor(palette.ACCENT)
        elif is_hover:
            fill, border = QColor(palette.BG_HOVER), QColor(palette.BORDER_STRONG)
        else:
            fill, border = QColor(palette.BG_CARD), QColor(palette.BG_CARD)

        painter.setPen(Qt.NoPen)
        painter.setBrush(fill)
        painter.drawPath(card_path)

        # Franja de color de categoría junto al borde inferior -- misma
        # idea que el borde de color por categoría de la vista de lista
        # (ChannelDelegate), como una franja horizontal en vez de vertical
        # para encajar mejor con una tarjeta cuadrada. Solo si no está
        # sonando ni en hover: esos dos estados ya tienen su propio
        # lenguaje visual (tinte de acento / resalte) y no deben competir
        # con el de categoría.
        categoria = data.get("group") or ""
        if categoria and not is_playing and not is_hover:
            cat_color = category_color(categoria)
            cat_color.setAlpha(190)
            alto_franja = 4
            franja = QRectF(
                rect.left() + radius * 0.6, rect.bottom() - alto_franja - 4,
                rect.width() - radius * 1.2, alto_franja,
            )
            painter.setPen(Qt.NoPen)
            painter.setBrush(cat_color)
            painter.drawRoundedRect(franja, alto_franja / 2, alto_franja / 2)

        painter.setPen(QPen(border, 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, radius, radius)

        logo_size = min(rect.width(), rect.height()) * self.LOGO_RATIO
        logo_rect = QRectF(rect.center().x() - logo_size / 2, rect.top() + 14, logo_size, logo_size)
        if isinstance(logo, QPixmap) and not logo.isNull():
            painter.drawPixmap(logo_rect.toRect(), logo)
            ring = QColor(palette.ACCENT) if is_playing else QColor(palette.BORDER)
            painter.setPen(QPen(ring, 1.2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(logo_rect, 10, 10)
        else:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(palette.BG_PANEL_ALT))
            painter.drawRoundedRect(logo_rect, 10, 10)
            icon_size = int(logo_size * 0.45)
            icon_pixmap = (
                icon_tv(palette.ACCENT_INFO, size=icon_size)
                if data.get("type") == "tv"
                else icon_radio(palette.ACCENT_CATEGORY_ORANGE, size=icon_size)
            ).pixmap(icon_size, icon_size)
            painter.drawPixmap(
                int(logo_rect.center().x() - icon_size / 2),
                int(logo_rect.center().y() - icon_size / 2),
                icon_pixmap,
            )

        name_rect = QRectF(rect.left() + 8, logo_rect.bottom() + 10, rect.width() - 16, 34)
        font = QFont(painter.font())
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)
        elided = painter.fontMetrics().elidedText(
            _display_name(data.get("name", ""))[0], Qt.ElideRight, int(name_rect.width())
        )
        painter.setPen(QColor(palette.ACCENT_LIGHTER) if is_playing else QColor(palette.TEXT_PRIMARY))
        painter.drawText(name_rect, Qt.AlignHCenter | Qt.AlignTop, elided)

        if is_fav:
            star_rect = QRectF(rect.right() - 26, rect.top() + 4, 20, 20)
            painter.setPen(QColor(palette.ACCENT_FAVORITE))
            star_font = QFont(painter.font())
            star_font.setPointSize(11)
            painter.setFont(star_font)
            painter.drawText(star_rect, Qt.AlignCenter, "★")

        painter.restore()


class ChannelDelegate(QStyledItemDelegate):
    """
    Pinta cada fila de canal/emisora como una tarjeta de cristal esmerilado:
    sombra suave por debajo, relleno translúcido con brillo superior, y un
    halo dorado alrededor de la que está sonando. Todo con QPainter puro
    (sin QGraphicsEffect, que no aplica a delegados) capa por capa.
    """

    # Filas densas y legibles como el catálogo de Pencil: más entradas por
    # pantalla sin sacrificar el logo, el estado de salud o el subtítulo.
    ROW_HEIGHT = 84
    LOGO_SIZE = 54

    def sizeHint(self, option, index):
        # Ancho mínimo, no el del viewport: en modo lista Qt estira cada
        # fila al ancho visible, y con setUniformItemSizes el primer ancho
        # devuelto se quedaba fijo -- al estrechar la ventana la fila seguía
        # siendo más ancha que la lista y salía una barra horizontal con
        # los nombres cortados.
        return QSize(1, self.ROW_HEIGHT)

    # ---------- capas de la tarjeta ----------


    @staticmethod
    def _draw_now_playing_badge(painter: QPainter, logo_rect: QRectF):
        """Circulito dorado con 3 barritas, en la esquina inferior derecha
        del logo, para marcar de un vistazo qué fila es la que suena."""
        size = 20
        badge_rect = QRectF(
            logo_rect.right() - size * 0.7, logo_rect.bottom() - size * 0.7, size, size
        )
        painter.setPen(QPen(QColor(palette.BG_CARD), 2))
        painter.setBrush(QColor(palette.ACCENT))
        painter.drawEllipse(badge_rect)

        bar_heights = (0.9, 0.5, 0.7)
        bar_w = size * 0.11
        gap = size * 0.08
        total_w = bar_w * 3 + gap * 2
        x = badge_rect.left() + (badge_rect.width() - total_w) / 2
        base_y = badge_rect.bottom() - size * 0.22
        max_h = size * 0.42
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(palette.INK))
        for h_frac in bar_heights:
            bar_h = max_h * h_frac
            painter.drawRoundedRect(QRectF(x, base_y - bar_h, bar_w, bar_h), bar_w / 2, bar_w / 2)
            x += bar_w + gap

    def paint(self, painter: QPainter, option, index):
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        # El margen derecho extra evita que, con scrollbar o el splitter
        # estrecho, la tarjeta se pinte por debajo del borde del viewport y
        # pierda su esquina redondeada (visible en la captura reducida).
        rect = QRectF(option.rect.adjusted(8, 5, -16, -6))
        radius = 11
        data = index.data(ROLE_DATA) or {}
        is_playing = bool(index.data(ROLE_PLAYING))
        is_fav = bool(index.data(ROLE_FAV))
        health_status = index.data(ROLE_HEALTH)
        is_hover = bool(option.state & QStyle.State_MouseOver)
        logo = index.data(ROLE_LOGO)

        # ---- sombra suave bajo la tarjeta (siempre, da profundidad) ----
        card_path = QPainterPath()
        card_path.addRoundedRect(rect, radius, radius)

        if is_playing:
            fill_c, border_c = _accent_tint(56), QColor(palette.ACCENT)
        elif is_hover:
            fill_c, border_c = QColor(palette.BG_HOVER), QColor(palette.BORDER_STRONG)
        else:
            fill_c, border_c = QColor(palette.BG_CARD), QColor(palette.BG_CARD)

        painter.fillPath(card_path, fill_c)
        painter.setPen(QPen(border_c, 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRoundedRect(rect, radius, radius)

        # ---- logo (o placeholder del color de su categoría) ----
        logo_rect = QRectF(
            rect.left() + 14, rect.center().y() - self.LOGO_SIZE / 2, self.LOGO_SIZE, self.LOGO_SIZE
        )
        if isinstance(logo, QPixmap) and not logo.isNull():
            painter.drawPixmap(logo_rect.toRect(), logo)
            ring = QColor(palette.ACCENT) if is_playing else QColor(palette.BORDER)
            painter.setPen(QPen(ring, 1.3))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(logo_rect, 10, 10)
        else:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(palette.BG_PANEL_ALT))
            painter.drawRoundedRect(logo_rect, 10, 10)
            category_name = data.get("group") or ""
            if category_name:
                # Tinte de color de categoría, translúcido, encima del cristal
                # base: da una pista visual de a qué categoría pertenece el
                # canal incluso antes de que cargue su logo real.
                tint = category_color(category_name)
                tint.setAlpha(120)
                painter.setBrush(tint)
                painter.drawRoundedRect(logo_rect, 10, 10)
            # Mismo icono dibujado que el resto de la app (ui/icons.py), con
            # el mismo color que su equivalente en el menú lateral.
            icon_size = int(self.LOGO_SIZE * 0.5)
            if data.get("type") == "tv":
                icon_pixmap = icon_tv(palette.ACCENT_INFO, size=icon_size).pixmap(icon_size, icon_size)
            else:
                icon_pixmap = icon_radio(palette.ACCENT_CATEGORY_ORANGE, size=icon_size).pixmap(icon_size, icon_size)
            icon_x = logo_rect.center().x() - icon_size / 2
            icon_y = logo_rect.center().y() - icon_size / 2
            painter.drawPixmap(int(icon_x), int(icon_y), icon_pixmap)

        # ---- insignia "sonando ahora": circulito con 3 barritas tipo
        # ecualizador sobre la esquina del logo, igual que el badge que
        # ponen Spotify/Apple Music en la carátula de lo que se está
        # reproduciendo. Se suma al halo dorado de la tarjeta -- ese ya
        # avisa de qué fila es, esto identifica de un vistazo qué logo. Se
        # deja estática (sin QTimer) porque un delegado no puede animarse
        # por sí solo sin forzar repintados constantes de toda la lista.
        if is_playing:
            self._draw_now_playing_badge(painter, logo_rect)

        # ---- textos ----
        text_x = logo_rect.right() + 14
        star_reserve = 28 if is_fav else 8
        text_rect = QRectF(text_x, rect.top(), rect.right() - text_x - star_reserve, rect.height())

        name_font = QFont(painter.font())
        name_font.setPointSize(11)
        name_font.setBold(True)
        painter.setFont(name_font)
        name_rect = QRectF(text_rect.left(), text_rect.top() + 10, text_rect.width(), 22)
        display_name, name_tags = _display_name(data.get("name", ""))
        elided = painter.fontMetrics().elidedText(display_name, Qt.ElideRight, int(name_rect.width()))
        painter.setPen(QColor(palette.ACCENT_LIGHTER) if is_playing else QColor(palette.TEXT_PRIMARY))
        painter.drawText(name_rect, Qt.AlignVCenter | Qt.AlignLeft, elided)

        # Punto de salud persistente: la comprobación se guarda aparte y
        # no dispara ninguna llamada de red al pintar una fila.
        health_colors = {
            "stable": QColor(palette.SUCCESS),
            "slow": QColor(palette.WARNING),
            "down": QColor(palette.DANGER),
            "restricted": QColor(palette.DANGER),
        }
        if health_status in health_colors:
            health_rect = QRectF(name_rect.right() - 8, name_rect.center().y() - 4, 8, 8)
            painter.setPen(QPen(QColor(palette.BG_CARD), 1))
            painter.setBrush(health_colors[health_status])
            painter.drawEllipse(health_rect)

        # "subtitle" antes de "group": los canales de TV ahora traen un
        # subtítulo ya compuesto ("Categoría · Ahora: Programa" o solo uno
        # de los dos, ver ChannelListsController._epg_now_text) que debe
        # ganar cuando existe. Radio/historial ya solo rellenaban
        # "subtitle" (bitrate, fecha...) y nunca "group", y Favoritos solo
        # rellena "group" (la carpeta) y nunca "subtitle" -- ninguno de los
        # dos cambia de comportamiento con el orden invertido.
        # El group-title del catálogo llega en inglés y a veces combinado
        # ("General;Public"): se muestra traducido; el valor real (para el
        # color de categoría y los filtros) no cambia.
        subtitle = data.get("subtitle") or (_display_group(data["group"]) if data.get("group") else "")
        if name_tags:
            subtitle = " · ".join(([subtitle] if subtitle else []) + list(name_tags))
        if subtitle:
            sub_font = QFont(painter.font())
            sub_font.setPointSize(8.5)
            sub_font.setBold(False)
            painter.setFont(sub_font)
            sub_rect = QRectF(text_rect.left(), text_rect.top() + 35, text_rect.width(), 16)

            dot_offset = 0
            if data.get("group"):
                dot_size = 6.0
                dot_rect = QRectF(
                    sub_rect.left(), sub_rect.center().y() - dot_size / 2, dot_size, dot_size
                )
                painter.setPen(Qt.NoPen)
                painter.setBrush(category_color(data["group"]))
                painter.drawEllipse(dot_rect)
                dot_offset = dot_size + 6

            text_sub_rect = QRectF(
                sub_rect.left() + dot_offset, sub_rect.top(), sub_rect.width() - dot_offset, sub_rect.height()
            )
            painter.setPen(QColor(palette.TEXT_MUTED))
            elided_sub = painter.fontMetrics().elidedText(subtitle, Qt.ElideRight, int(text_sub_rect.width()))
            painter.drawText(text_sub_rect, Qt.AlignVCenter | Qt.AlignLeft, elided_sub)

        # ---- estrella de favorito ----
        if is_fav:
            star_rect = QRectF(rect.right() - 26, rect.center().y() - 11, 20, 22)
            painter.setPen(QColor(palette.ACCENT_FAVORITE))
            star_font = QFont(painter.font())
            star_font.setPointSize(12)
            painter.setFont(star_font)
            painter.drawText(star_rect, Qt.AlignCenter, "\u2605")

        painter.restore()
