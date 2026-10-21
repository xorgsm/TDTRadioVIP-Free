"""
Ciclo de vida del ecualizador nativo de libVLC (AudioEqualizer), separado de
VLCPlayer.

Se extrajo porque la propiedad del objeto nativo estaba entrelazada con la
recreación del media_player (cada zapeo) y con el cierre de la app -- ese
mismo entrelazado ya causó una fuga real (7.6.2.1: el objeto nuevo quedaba
sin liberar cuando aplicarlo fallaba a medias). Aislar el ciclo de vida aquí
deja esa gestión en un solo sitio con sus propios tests.
"""
from core.logger import get_logger

log = get_logger(__name__)

try:
    import vlc
except Exception:  # ImportError, OSError al cargar libvlc.dll…
    vlc = None


class VLCEqualizer:
    """
    Ecualizador gráfico de libVLC (N bandas de frecuencia + preamplificación,
    -20.0 a +20.0 dB cada valor), aplicable en caliente sin cortar la
    reproducción. python-vlc lo expone como un objeto AudioEqualizer
    independiente de la Instance, que hay que "enganchar" a un media_player
    con set_equalizer() -- ver apply_to().
    """

    def __init__(self):
        self._enabled = False
        self._preamp = 0.0
        self._bands: list[float] = []
        self._native = None

    # ---------- descubrimiento de bandas/presets (consultas sin estado) ----------

    @staticmethod
    def band_count() -> int:
        return vlc.libvlc_audio_equalizer_get_band_count() if vlc else 0

    @staticmethod
    def band_frequency(index: int) -> float:
        return vlc.libvlc_audio_equalizer_get_band_frequency(index) if vlc else 0.0

    @staticmethod
    def preset_names() -> list[str]:
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

    @staticmethod
    def preset_values(index: int):
        """(preamp, [amplitud por banda]) de un preset de fábrica, sin aplicarlo todavía."""
        if vlc is None:
            return 0.0, []
        eq = vlc.libvlc_audio_equalizer_new_from_preset(index)
        if eq is None:
            return 0.0, []
        try:
            bandas = [eq.get_amp_at_index(i) for i in range(VLCEqualizer.band_count())]
            return eq.get_preamp(), bandas
        finally:
            # AudioEqualizer no tiene __del__: sin release() explícito, cada
            # preset que el usuario prueba desde el combo filtra el objeto
            # nativo -- este solo se usa para leer sus valores, nunca se
            # aplica (a diferencia de apply_to(), que sí lo deja "vivo").
            eq.release()

    # ---------- configurar / aplicar / desactivar / liberar ----------

    def configure(self, preamp: float, bands: list) -> None:
        """Guarda la preamplificación y amplitud por banda deseadas, en dB, y
        marca el ecualizador activo. No toca ningún media_player -- para eso
        está apply_to()."""
        self._enabled = True
        self._preamp = preamp
        self._bands = list(bands)

    def apply_to(self, media_player) -> None:
        """
        Construye un AudioEqualizer nativo nuevo a partir de la configuración
        actual y lo engancha a media_player. No hace nada si el ecualizador
        no está activo o si libVLC no está disponible.

        Se llama tanto tras configure() como después de recrear el
        media_player (un media_player nuevo no hereda el ecualizador del
        anterior).
        """
        if not self._enabled or media_player is None or vlc is None:
            return
        eq = None
        try:
            eq = vlc.AudioEqualizer()
            eq.set_preamp(self._preamp)
            for i, amp in enumerate(self._bands):
                eq.set_amp_at_index(amp, i)
            media_player.set_equalizer(eq)
            # Cada llamada crea un objeto nativo nuevo (arrastrar el slider
            # del ecualizador dispara esto docenas de veces por segundo):
            # hay que liberar el anterior antes de sustituir la referencia,
            # o cada ajuste filtra memoria nativa sin límite.
            self._release_native()
            # Referencia viva obligatoria: si "eq" se recolectara, libVLC se
            # quedaría con un puntero a un objeto ya liberado por Python.
            self._native = eq
            eq = None
        except Exception:
            log.warning("No se pudo aplicar el ecualizador", exc_info=True)
        finally:
            if eq is not None:
                try:
                    eq.release()
                except Exception:
                    log.warning("No se pudo liberar el ecualizador fallido", exc_info=True)

    def clear(self, media_player) -> None:
        """Desactiva el ecualizador: deja pasar la señal de audio sin
        procesar y libera el objeto nativo."""
        self._enabled = False
        if media_player is not None:
            try:
                media_player.set_equalizer(None)
            except Exception:
                log.warning("No se pudo desactivar el ecualizador", exc_info=True)
        self._release_native()

    def release(self) -> None:
        """Libera el objeto nativo sin tocar ningún media_player -- para el
        cierre ordenado de la app (ver VLCPlayer.release())."""
        self._release_native()

    def _release_native(self) -> None:
        """AudioEqualizer no tiene __del__ (confirmado en python-vlc): hay
        que llamar a release() a mano o el objeto nativo se queda filtrado
        para siempre, aunque Python recolecte la referencia de Python."""
        if self._native is not None:
            try:
                self._native.release()
            except Exception:
                log.warning("No se pudo liberar el ecualizador anterior", exc_info=True)
            self._native = None
