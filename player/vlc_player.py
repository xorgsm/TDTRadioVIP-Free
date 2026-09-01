"""
Widget de reproducción de vídeo/audio basado en libVLC.

Usa la libVLC empaquetada con la aplicación si viaja incluida; si no, la del
VLC instalado en el sistema (https://www.videolan.org/).
"""
import sys

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame

from core.logger import get_logger

log = get_logger(__name__)

try:
    import vlc
    VLC_IMPORT_ERROR = None
except Exception as _exc:  # ImportError, OSError al cargar libvlc.dll…
    vlc = None
    VLC_IMPORT_ERROR = str(_exc)

VLC_DOWNLOAD_URL = "https://www.videolan.org/vlc/download-windows.html"


def vlc_disponible_al_arrancar() -> str | None:
    """
    Comprobación temprana, antes de crear la ventana principal: ¿hay VLC
    utilizable? Devuelve None si todo está en orden, o un mensaje explicando
    el problema si no — para poder avisar al usuario con instrucciones
    claras nada más abrir la app, en vez de que descubra que no reproduce
    nada solo al hacer clic en un canal.
    """
    if vlc is None:
        return (
            "No se encontró VLC (o su versión de 64 bits) en este equipo.\n\n"
            f"Detalle técnico: {VLC_IMPORT_ERROR}\n\n"
            f"Descárgalo gratis desde:\n{VLC_DOWNLOAD_URL}\n\n"
            "Instálalo y vuelve a abrir la aplicación. Mientras tanto, "
            "puedes seguir navegando por los canales, pero no se podrá "
            "reproducir nada."
        )
    return None


class VLCPlayer(QFrame):
    """
    Reproductor de streams. Si libVLC no puede cargarse, el widget sigue
    existiendo pero informa del problema mediante error_occurred, en vez de
    tumbar la aplicación entera al arrancar.
    """

    # Señales públicas: se emiten SIEMPRE en el hilo de la interfaz.
    error_occurred = Signal(str)
    end_reached = Signal()
    # Título "now playing" que algunos streams de radio (ICY/Shoutcast)
    # emiten dentro del propio flujo -- canción o programa actual, cuando el
    # servidor lo manda. Cadena vacía si el stream deja de mandarlo o no lo
    # soporta; quien escuche esta señal debe tratar "" como "sin dato", no
    # como una emisión con título vacío.
    meta_changed = Signal(str)

    # Señales internas: las emiten los callbacks de libVLC desde sus propios
    # hilos. Se reenvían a las públicas con conexión en cola (ver __init__).
    _error_desde_vlc = Signal(str)
    _fin_desde_vlc = Signal()
    _vout_desde_vlc = Signal()
    _meta_desde_vlc = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_NativeWindow)
        self.setStyleSheet("background-color: black;")

        self.instance = None
        self.media_player = None
        self._media_actual = None
        self._salida_asignada = False

        # Estado del ecualizador (ver la sección "ecualizador" más abajo):
        # se guarda aquí, no solo en el objeto AudioEqualizer de libVLC,
        # porque _recrear_media_player() sustituye el media_player en cada
        # cambio de canal/emisora y un media_player nuevo no hereda el
        # ecualizador del anterior.
        self._eq_enabled = False
        self._eq_preamp = 0.0
        self._eq_bands = []
        self._eq_object = None

        # Qt ya encola solo estas emisiones (al comparar la afinidad de hilo
        # del receptor, la conexión automática se resuelve como en cola), así
        # que esto no corrige ningún fallo previo. Se declara explícitamente
        # como red de seguridad: deja la garantía por escrito y evita que una
        # conexión directa añadida en el futuro acabe ejecutando el manejador
        # dentro del callback de libVLC, que sí está prohibido por su API.
        self._error_desde_vlc.connect(self.error_occurred, Qt.QueuedConnection)
        self._fin_desde_vlc.connect(self.end_reached, Qt.QueuedConnection)
        self._vout_desde_vlc.connect(self._on_vout_ready, Qt.QueuedConnection)
        self._meta_desde_vlc.connect(self.meta_changed, Qt.QueuedConnection)

        self._crear_instancia()

    # ---------- arranque ----------

    def _crear_instancia(self):
        if vlc is None:
            return
        args = ["--no-xlib"] if sys.platform.startswith("linux") else []
        args += [
            "--no-video-title-show",  # no superponer el título sobre el vídeo
            "--quiet",                # no ensuciar la consola
            # Los streams públicos (IPTV/radio) tienen jitter y micro-cortes de
            # red normales. Con el caching por defecto de libVLC (~300ms) esos
            # baches se interpretan como error y disparan el auto-salto al
            # siguiente canal aunque el stream siga vivo. Un buffer más
            # generoso absorbe esos baches sin llegar a marcar error.
            "--network-caching=3000",
            # Reintenta la conexión HTTP a nivel de libVLC antes de rendirse,
            # en vez de que cada corte de red suba directo como error a la UI.
            "--http-reconnect",
        ]
        try:
            self.instance = vlc.Instance(args)
            if self.instance is None:
                return
            self.media_player = self.instance.media_player_new()
            self._attach_events()
        except Exception:
            log.exception("No se pudo inicializar libVLC (Instance/media_player_new)")
            # Sin release() aquí, un fallo justo en _attach_events() (tras
            # haber creado instance/media_player con éxito) los dejaba
            # huérfanos: la referencia de Python se descarta abajo pero el
            # objeto nativo de libVLC nunca se liberaba.
            if self.media_player is not None:
                try:
                    self.media_player.release()
                except Exception:
                    pass
            if self.instance is not None:
                try:
                    self.instance.release()
                except Exception:
                    pass
            self.instance = None
            self.media_player = None

    @property
    def disponible(self) -> bool:
        return self.media_player is not None

    def motivo_no_disponible(self) -> str:
        if vlc is None:
            return (
                "No se pudo cargar libVLC.\n\n"
                f"Detalle: {VLC_IMPORT_ERROR}"
            )
        return "No se pudo inicializar el motor de vídeo de VLC."

    def _attach_events(self):
        events = self.media_player.event_manager()
        events.event_attach(vlc.EventType.MediaPlayerEncounteredError, self._on_vlc_error)
        events.event_attach(vlc.EventType.MediaPlayerEndReached, self._on_vlc_end_reached)
        events.event_attach(vlc.EventType.MediaPlayerVout, self._on_vlc_vout)

    def _detach_events(self):
        """Contraparte de _attach_events(): desregistra los callbacks a
        nivel de libVLC (no solo en el lado Python), para que el
        media_player que se va a liberar no pueda emitir ya ningún evento
        más -- ver el comentario en _recrear_media_player()."""
        if self.media_player is None:
            return
        try:
            events = self.media_player.event_manager()
            events.event_detach(vlc.EventType.MediaPlayerEncounteredError)
            events.event_detach(vlc.EventType.MediaPlayerEndReached)
            events.event_detach(vlc.EventType.MediaPlayerVout)
        except Exception:
            log.warning("No se pudieron desenganchar los eventos del media_player anterior", exc_info=True)

    # ---------- callbacks de libVLC (se ejecutan en hilos de libVLC) ----------

    def _on_vlc_error(self, _event):
        self._error_desde_vlc.emit("No se pudo conectar con el servidor del stream.")

    def _on_vlc_end_reached(self, _event):
        self._fin_desde_vlc.emit()

    def _on_vlc_vout(self, _event):
        self._vout_desde_vlc.emit()

    def _on_vlc_meta_changed(self, _event):
        try:
            texto = self._media_actual.get_meta(vlc.Meta.NowPlaying) if self._media_actual else None
        except Exception:
            texto = None
        self._meta_desde_vlc.emit((texto or "").strip())

    def _on_vout_ready(self):
        """
        Se dispara cuando libVLC ya tiene una salida de vídeo real (evento
        MediaPlayerVout), que es más tarde que "play() ya se llamó" — play()
        arranca la reproducción de forma asíncrona, y si video_set_scale()
        se llama antes de que exista el vout, la llamada no tiene efecto y el
        vídeo se queda a su tamaño nativo en vez de ajustarse al widget.
        """
        try:
            self.media_player.video_set_scale(0)
        except Exception:
            log.warning("video_set_scale(0) falló tras el evento MediaPlayerVout", exc_info=True)

    # ---------- salida de vídeo ----------

    def _attach_output(self):
        """Asocia la superficie de dibujo del widget al reproductor (una vez)."""
        if self._salida_asignada or self.media_player is None:
            return
        win_id = int(self.winId())
        if not win_id:
            return  # el widget aún no tiene ventana nativa; se reintenta luego
        if sys.platform.startswith("win"):
            self.media_player.set_hwnd(win_id)
        elif sys.platform == "darwin":
            self.media_player.set_nsobject(win_id)
        else:
            self.media_player.set_xwindow(win_id)
        self._salida_asignada = True

    # ---------- control ----------

    def play(self, url: str):
        if not self.disponible:
            self.error_occurred.emit(self.motivo_no_disponible())
            return
        self._recrear_media_player()
        if self.media_player is None:
            self.error_occurred.emit(self.motivo_no_disponible())
            return
        # A diferencia de casi todo lo demás en este archivo, esta ruta no
        # llevaba try/except: cualquier fallo de libVLC/ctypes aquí se
        # propagaba sin control en vez de convertirse en error_occurred (lo
        # que el resto de la app espera para reaccionar), y si el fallo
        # ocurría entre media_new() y _media_actual, el objeto Media recién
        # creado quedaba huérfano sin liberar.
        media = None
        try:
            media = self.instance.media_new(url)
            # El "now playing" (ICY/Shoutcast) es del STREAM anterior hasta
            # que este medio nuevo mande el suyo propio (o nunca, si no lo
            # soporta) -- se limpia aquí para no dejar el título de la
            # emisora vieja pegado en la interfaz durante el cambio.
            self._meta_desde_vlc.emit("")
            media.event_manager().event_attach(vlc.EventType.MediaMetaChanged, self._on_vlc_meta_changed)
            self.media_player.set_media(media)
            # set_media se queda con su propia referencia del medio. Si no
            # soltamos la nuestra, cada zapeo deja un objeto Media sin
            # liberar y la memoria crece sin parar, que es justo el uso
            # habitual de esta aplicación.
            self._liberar_media_anterior()
            self._media_actual = media
            media = None  # ya asumida por _media_actual; no liberarla abajo
            self._attach_output()
            self.media_player.play()
            # El escalado a "ajustar ventana" se aplica en _on_vout_ready(),
            # que dispara con el evento MediaPlayerVout — más fiable que
            # hacerlo aquí mismo, porque en este punto la salida de vídeo
            # todavía puede no existir (play() es asíncrono).
        except Exception:
            log.exception("Fallo al arrancar la reproducción de %s", url)
            if media is not None:
                try:
                    media.release()
                except Exception:
                    pass
            self.error_occurred.emit(self.motivo_no_disponible())

    def technical_info(self) -> dict:
        """Devuelve datos técnicos disponibles sin asumir que VLC los ofrece."""
        if not self.media_player:
            return {}
        info = {}
        try:
            width, height = self.media_player.video_get_size(0)
            if width and height:
                info["resolution"] = f"{width} × {height}"
        except Exception:
            pass
        for key, getter in (
            ("volume", self.media_player.audio_get_volume),
            ("audio_tracks", self.media_player.audio_get_track_count),
            ("subtitle_tracks", self.media_player.video_get_spu_count),
        ):
            try:
                info[key] = max(0, getter())
            except Exception:
                pass
        try:
            info["state"] = str(self.media_player.get_state()).split(".")[-1]
        except Exception:
            pass
        try:
            stats = self._media_actual.get_stats() if self._media_actual else None
            if isinstance(stats, dict):
                info["input_bitrate"] = float(stats.get("input_bitrate", 0) or 0)
                info["demux_bitrate"] = float(stats.get("demux_bitrate", 0) or 0)
        except Exception:
            pass
        return info

    def _recrear_media_player(self):
        """
        Sustituye el media_player por uno nuevo de la misma Instance (barato:
        no reinicia libVLC entero, solo el objeto que lleva el pipeline de
        decodificación/audio de UN stream) en vez de reutilizar indefinidamente
        el mismo durante toda la sesión.

        Motivo: zapear muchos canales seguidos sobre un único media_player de
        larga vida puede dejar su pipeline de salida de audio en un estado
        degradado con el tiempo -- sobre todo en Windows, alternando entre
        canales con códecs de audio distintos (AC3/AAC/MP2...). El síntoma es
        justo "el vídeo se sigue viendo pero el audio deja de sonar, sin
        ningún error visible", y hasta ahora hacía falta reiniciar la app
        para que volviera. Reconstruir el media_player en cada cambio de
        canal arranca de un pipeline de audio limpio siempre.

        Se preservan volumen y silencio de antes de recrear, porque esos dos
        son propiedades del media_player (no de la Instance ni del Media) y
        se perderían igual que el resto de su estado.
        """
        if self.instance is None or self.media_player is None:
            return
        try:
            volumen = self.media_player.audio_get_volume()
        except Exception:
            volumen = -1
        try:
            muted = self.media_player.audio_get_mute() == 1
        except Exception:
            muted = False

        try:
            # Sin desengancharlos primero, el media_player VIEJO puede
            # seguir emitiendo eventos (error, fin de stream) desde su
            # propio hilo de libVLC mientras el NUEVO ya está reproduciendo
            # -- como las señales van en cola a Qt, ese evento tardío se
            # procesaría después del cambio de canal y mostraría un error
            # falso (o dispararía un auto-salto) sobre el canal nuevo.
            # Zapear dos veces muy rápido, justo cuando el primer canal
            # estaba fallando, era el escenario que lo disparaba.
            self._detach_events()
            self.media_player.stop()
            self._liberar_media_anterior()
            self.media_player.release()
        except Exception:
            log.warning("Fallo liberando el media_player anterior al recrearlo", exc_info=True)

        try:
            self.media_player = self.instance.media_player_new()
            self._attach_events()
            self._salida_asignada = False  # el nuevo media_player necesita su propia asignación de ventana
            if volumen >= 0:
                self.media_player.audio_set_volume(volumen)
            self.media_player.audio_set_mute(muted)
            self._aplicar_equalizer()
        except Exception:
            log.exception("No se pudo recrear el media_player (media_player_new)")
            # Mismo motivo que en _crear_instancia(): sin release() aquí, un
            # fallo tras haber creado el media_player con éxito (p. ej. en
            # _attach_events()) lo dejaría huérfano a nivel de libVLC aunque
            # la referencia de Python se descarte abajo.
            if self.media_player is not None:
                try:
                    self.media_player.release()
                except Exception:
                    pass
            self.media_player = None

    def _liberar_media_anterior(self):
        if self._media_actual is not None:
            try:
                self._media_actual.release()
            except Exception:
                log.warning("Fallo liberando el objeto Media anterior (posible fuga de memoria)", exc_info=True)
            self._media_actual = None

    def stop(self):
        if self.media_player is not None:
            self.media_player.stop()

    def pause_toggle(self):
        if self.media_player is None:
            return
        if self.media_player.is_playing():
            self.media_player.pause()
        else:
            self.media_player.play()

    def set_volume(self, value: int):
        if self.media_player is not None:
            self.media_player.audio_set_volume(max(0, min(100, value)))

    def set_muted(self, muted: bool):
        if self.media_player is not None:
            self.media_player.audio_set_mute(muted)

    def set_video_enabled(self, enabled: bool) -> None:
        """
        Activa o desactiva la pista de vídeo del stream actual sin tocar
        el audio -- para el modo "solo audio" de TV (ver
        PlaybackController.toggle_audio_only_tv), pensado para ahorrar
        CPU/batería en portátiles cuando solo se quiere escuchar. -1 es el
        valor que usa libVLC para "ninguna pista de vídeo"; al reactivar,
        se elige la primera pista de vídeo real disponible en vez de
        asumir que su id es 0 (no siempre lo es).
        """
        if self.media_player is None:
            return
        try:
            if enabled:
                reales = [tid for tid, _ in self.video_tracks() if tid != -1]
                self.media_player.video_set_track(reales[0] if reales else -1)
            else:
                self.media_player.video_set_track(-1)
        except Exception:
            log.warning("No se pudo cambiar la pista de vídeo (modo solo audio)", exc_info=True)

    def is_playing(self) -> bool:
        return bool(self.media_player.is_playing()) if self.media_player else False

    def get_state(self):
        return self.media_player.get_state() if self.media_player else None

    # ---------- avance rápido / retroceso ----------
    #
    # Solo tiene efecto real en contenido que libVLC pueda posicionar (VOD,
    # ficheros locales, streams con ventana de time-shift); un canal de TV
    # o una emisora de radio en directo "puro" no es_seekable() y set_time()
    # ahí no hace nada -- por eso seek_relative() comprueba is_seekable()
    # antes de tocar nada, en vez de fallar en silencio o mover un contador
    # que no se refleja en el audio/vídeo real.

    def is_seekable(self) -> bool:
        return bool(self.media_player.is_seekable()) if self.media_player else False

    def get_time(self) -> int:
        """Posición actual en ms, o -1 si no se puede determinar."""
        return self.media_player.get_time() if self.media_player else -1

    def get_length(self) -> int:
        """Duración total en ms, o <= 0 si no se conoce (típico en directo)."""
        return self.media_player.get_length() if self.media_player else -1

    def seek_relative(self, offset_ms: int) -> None:
        """Adelanta (offset_ms > 0) o retrasa (offset_ms < 0) la reproducción."""
        if self.media_player is None or not self.media_player.is_seekable():
            return
        actual = self.media_player.get_time()
        if actual < 0:
            return
        nuevo = max(0, actual + offset_ms)
        length = self.media_player.get_length()
        if length and length > 0:
            nuevo = min(nuevo, max(0, length - 500))
        self.media_player.set_time(nuevo)

    # ---------- pistas de audio / subtítulos ----------
    #
    # libVLC devuelve las pistas como una lista enlazada en C (ctypes
    # POINTER a una struct con .id/.name/.next) -- python-vlc no la
    # envuelve en una lista Python normal, hay que recorrerla a mano. Se
    # protege con try/except porque este recorrido depende de detalles de
    # la struct que pueden variar entre versiones de libVLC/python-vlc; si
    # algo no encaja, es mejor devolver una lista vacía (el menú de
    # pistas se oculta solo, ver ui/main_window._build_tracks_menu) que
    # reventar la reproducción por esto.

    def _walk_track_descriptions(self, descs):
        """
        Recorre la lista enlazada en C y la libera con
        libvlc_track_description_list_release() antes de devolver el
        resultado -- audio_get_track_description(), video_get_track_description()
        y video_get_spu_description() (los tres llamantes) documentan que
        quien recibe la lista es responsable de liberarla; sin esto, cada
        apertura del menú de pistas (o cada cambio de canal, que lo repuebla)
        filtraba la lista C entera -- justo la clase de fuga de memoria de
        libVLC que este proyecto ya tuvo que arreglar una vez.
        """
        tracks = []
        node = descs
        while node:
            try:
                item = node.contents
            except ValueError:
                break
            nombre = item.name.decode("utf-8", "replace") if item.name else str(item.id)
            tracks.append((item.id, nombre))
            node = item.next
        if descs:
            try:
                vlc.libvlc_track_description_list_release(descs)
            except Exception:
                log.warning("No se pudo liberar la lista de descripciones de pistas", exc_info=True)
        return tracks

    def audio_tracks(self):
        """Lista de (id, nombre) de pistas de audio disponibles en el stream actual."""
        if self.media_player is None:
            return []
        try:
            return self._walk_track_descriptions(self.media_player.audio_get_track_description())
        except Exception:
            log.warning("No se pudieron listar las pistas de audio", exc_info=True)
            return []

    def video_tracks(self):
        """Lista de (id, nombre) de pistas de vídeo disponibles en el stream actual."""
        if self.media_player is None:
            return []
        try:
            return self._walk_track_descriptions(self.media_player.video_get_track_description())
        except Exception:
            log.warning("No se pudieron listar las pistas de vídeo", exc_info=True)
            return []

    def current_audio_track(self) -> int:
        return self.media_player.audio_get_track() if self.media_player else -1

    def set_audio_track(self, track_id: int) -> None:
        if self.media_player is None:
            return
        try:
            self.media_player.audio_set_track(track_id)
        except Exception:
            log.warning("No se pudo cambiar la pista de audio a %s", track_id, exc_info=True)

    def subtitle_tracks(self):
        """Lista de (id, nombre) de pistas de subtítulos disponibles (-1 = 'Desactivados')."""
        if self.media_player is None:
            return []
        try:
            return self._walk_track_descriptions(self.media_player.video_get_spu_description())
        except Exception:
            log.warning("No se pudieron listar las pistas de subtítulos", exc_info=True)
            return []

    def current_subtitle_track(self) -> int:
        return self.media_player.video_get_spu() if self.media_player else -1

    def set_subtitle_track(self, track_id: int) -> None:
        if self.media_player is None:
            return
        try:
            self.media_player.video_set_spu(track_id)
        except Exception:
            log.warning("No se pudo cambiar la pista de subtítulos a %s", track_id, exc_info=True)

    # ---------- ecualizador ----------
    #
    # libVLC trae de fábrica un ecualizador gráfico (N bandas de frecuencia
    # + preamplificación, -20.0 a +20.0 dB cada valor) aplicable en caliente
    # sin cortar la reproducción. python-vlc lo expone como un objeto
    # AudioEqualizer independiente de la Instance, que se "engancha" al
    # media_player con set_equalizer() -- ver _aplicar_equalizer() y el
    # comentario de _recrear_media_player() sobre por qué hay que reaplicarlo
    # en cada zapeo.

    def equalizer_band_count(self) -> int:
        return vlc.libvlc_audio_equalizer_get_band_count() if vlc else 0

    def equalizer_band_frequency(self, index: int) -> float:
        return vlc.libvlc_audio_equalizer_get_band_frequency(index) if vlc else 0.0

    def equalizer_preset_names(self) -> list[str]:
        """Nombres de los presets de fábrica de libVLC (Rock, Pop, Jazz...)."""
        if vlc is None:
            return []
        total = vlc.libvlc_audio_equalizer_get_preset_count()
        nombres = []
        for i in range(total):
            nombre = vlc.libvlc_audio_equalizer_get_preset_name(i)
            if isinstance(nombre, bytes):
                nombre = nombre.decode("utf-8", "replace")
            nombres.append(nombre or f"Preset {i}")
        return nombres

    def equalizer_preset_values(self, index: int):
        """(preamp, [amplitud por banda]) de un preset de fábrica, sin aplicarlo todavía."""
        if vlc is None:
            return 0.0, []
        eq = vlc.libvlc_audio_equalizer_new_from_preset(index)
        if eq is None:
            return 0.0, []
        try:
            bandas = [eq.get_amp_at_index(i) for i in range(self.equalizer_band_count())]
            return eq.get_preamp(), bandas
        finally:
            # AudioEqualizer no tiene __del__: sin release() explícito, cada
            # preset que el usuario prueba desde el combo filtra el objeto
            # nativo -- este solo se usa para leer sus valores, nunca se
            # aplica (ver set_equalizer para el que sí queda "vivo").
            eq.release()

    def set_equalizer(self, preamp: float, bandas: list) -> None:
        """Activa (o actualiza, si ya estaba activo) el ecualizador con esta preamplificación y amplitud por banda, en dB."""
        self._eq_enabled = True
        self._eq_preamp = preamp
        self._eq_bands = list(bandas)
        self._aplicar_equalizer()

    def clear_equalizer(self) -> None:
        """Desactiva el ecualizador: deja pasar la señal de audio sin procesar."""
        self._eq_enabled = False
        if self.media_player is not None:
            try:
                self.media_player.set_equalizer(None)
            except Exception:
                log.warning("No se pudo desactivar el ecualizador", exc_info=True)
        self._liberar_eq_object()

    def _liberar_eq_object(self) -> None:
        """AudioEqualizer no tiene __del__ (confirmado en python-vlc): hay
        que llamar a release() a mano o el objeto nativo se queda filtrado
        para siempre, aunque Python recolecte la referencia de Python."""
        if self._eq_object is not None:
            try:
                self._eq_object.release()
            except Exception:
                log.warning("No se pudo liberar el ecualizador anterior", exc_info=True)
            self._eq_object = None

    def _aplicar_equalizer(self) -> None:
        if not self._eq_enabled or self.media_player is None or vlc is None:
            return
        eq = None
        try:
            eq = vlc.AudioEqualizer()
            eq.set_preamp(self._eq_preamp)
            for i, amp in enumerate(self._eq_bands):
                eq.set_amp_at_index(amp, i)
            self.media_player.set_equalizer(eq)
            # Cada llamada crea un objeto nativo nuevo (arrastrar el slider
            # del ecualizador dispara esto docenas de veces por segundo):
            # hay que liberar el anterior antes de sustituir la referencia,
            # o cada ajuste filtra memoria nativa sin límite.
            self._liberar_eq_object()
            # Referencia viva obligatoria: si "eq" se recolectara, libVLC se
            # quedaría con un puntero a un objeto ya liberado por Python.
            self._eq_object = eq
            eq = None
        except Exception:
            log.warning("No se pudo aplicar el ecualizador", exc_info=True)
        finally:
            if eq is not None:
                try:
                    eq.release()
                except Exception:
                    log.warning("No se pudo liberar el ecualizador fallido", exc_info=True)

    # ---------- cierre ordenado ----------

    def release(self):
        """
        Libera reproductor e instancia al cerrar la aplicación. Sin esto,
        los hilos internos de libVLC pueden quedar vivos y retrasar o colgar
        el cierre del proceso.
        """
        try:
            self._liberar_eq_object()
            if self.media_player is not None:
                self.media_player.stop()
                self._liberar_media_anterior()
                self.media_player.release()
                self.media_player = None
            if self.instance is not None:
                self.instance.release()
                self.instance = None
        except Exception:
            log.warning("Fallo liberando recursos de VLC al cerrar", exc_info=True)
