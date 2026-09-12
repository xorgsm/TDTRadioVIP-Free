"""
Atajos de teclado globales de la ventana principal.

`PRODUCT.md` compromete navegación por teclado, pero la ventana solo tenía
F11 (pantalla completa), Esc (salir de ella) y Ctrl+K (búsqueda global). Este
módulo añade los controles de reproducción y el salto entre secciones.

Por qué un filtro de eventos y no `QShortcut` para las teclas simples
---------------------------------------------------------------------

Un `QShortcut` **consume** la pulsación antes de que llegue al widget con el
foco, y eso rompe la interfaz de formas que no dan ningún error visible:

- con el foco en la lista de canales, ``Abajo`` bajaba el volumen en vez de
  moverse al canal siguiente;
- con el foco en un botón, ``Espacio`` pausaba la reproducción en vez de
  pulsar el botón;
- con el foco en el slider de volumen, las flechas no lo movían.

Ninguno de los tres casos es aceptable: recorrer la lista con las flechas es
la forma principal de navegar por el catálogo. Por eso las teclas simples se
gestionan con un `eventFilter` que **cede la tecla** cuando el widget
enfocado la usa de forma nativa (campos de texto, listas, sliders, botones,
desplegables) y solo actúa cuando nadie más la reclama.

Las combinaciones con Ctrl sí se registran como `QShortcut` a nivel de
ventana: ningún widget estándar las consume, así que no hay conflicto.
"""
from dataclasses import dataclass
from typing import Callable

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QAbstractSlider,
    QAbstractSpinBox,
    QApplication,
    QComboBox,
    QLineEdit,
    QPlainTextEdit,
    QTextEdit,
    QWidget,
)

# Salto de los atajos de avance/retroceso. Coincide con los botones ⏪/⏩ de
# la barra de reproducción (ver PlaybackController.seek) para que teclado y
# ratón se comporten igual.
SEEK_STEP_MS = 30_000

# Paso de volumen por pulsación de flecha vertical.
VOLUME_STEP = 5

# Widgets que escriben texto: ceden TODAS las teclas simples, porque
# cualquiera de ellas puede formar parte de lo que el usuario está tecleando.
_WIDGETS_DE_TEXTO = (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox)

# Widgets que navegan con flechas: listas de canales, sliders y desplegables.
_WIDGETS_CON_FLECHAS = (QAbstractItemView, QAbstractSlider, QComboBox)

# Teclas de navegación que deben cederse a los widgets de arriba.
_TECLAS_DE_FLECHA = frozenset({Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right})


@dataclass(frozen=True)
class ShortcutSpec:
    """Un atajo: qué tecla, qué acción dispara y cómo se describe."""

    key: int | None          # Qt.Key_* para las teclas simples del filtro
    sequence: str            # texto de la combinación (para Ctrl+N y la ayuda)
    action: str
    description: str
    is_simple: bool = True   # False = combinación con Ctrl, va por QShortcut


_SECCIONES = ("Inicio", "Televisión", "Radio", "Favoritos", "Historial", "Descargas")

# Orden pensado para leerse tal cual en la ayuda: reproducción, navegación
# entre pistas, audio, y por último el salto entre secciones.
SHORTCUT_SPECS: tuple[ShortcutSpec, ...] = (
    ShortcutSpec(Qt.Key_Space, "Space", "toggle_play", "Reproducir o pausar"),
    ShortcutSpec(Qt.Key_S, "S", "stop_playback", "Detener"),
    ShortcutSpec(Qt.Key_Right, "Right", "seek_forward", "Avanzar 30 segundos"),
    ShortcutSpec(Qt.Key_Left, "Left", "seek_backward", "Retroceder 30 segundos"),
    ShortcutSpec(Qt.Key_N, "N", "play_next", "Siguiente de la lista"),
    ShortcutSpec(Qt.Key_P, "P", "play_prev", "Anterior de la lista"),
    ShortcutSpec(Qt.Key_Up, "Up", "volume_up", "Subir volumen"),
    ShortcutSpec(Qt.Key_Down, "Down", "volume_down", "Bajar volumen"),
    ShortcutSpec(Qt.Key_M, "M", "toggle_mute", "Silenciar o restaurar el sonido"),
    # F = pantalla completa, como en VLC, mpv y YouTube. Antes estaba
    # asignada a favorito, que chocaba con esa expectativa (y con el F11 que
    # la ventana ya registraba para lo mismo).
    ShortcutSpec(Qt.Key_F, "F", "toggle_fullscreen", "Pantalla completa"),
    # Favorito se va a Ctrl+D, la combinación de "marcador" de toda la vida.
    ShortcutSpec(None, "Ctrl+D", "toggle_favorite", "Marcar o desmarcar favorito", is_simple=False),
    *(
        ShortcutSpec(
            None,
            f"Ctrl+{numero}",
            f"go_to_section_{indice}",
            f"Ir a {titulo}",
            is_simple=False,
        )
        for indice, (numero, titulo) in enumerate(zip(range(1, 7), _SECCIONES))
    ),
)


def describe_shortcuts() -> list[tuple[str, str]]:
    """Pares (teclas, descripción) listos para mostrar en la ayuda."""
    return [
        (QKeySequence(spec.sequence).toString(QKeySequence.NativeText), spec.description)
        for spec in SHORTCUT_SPECS
    ]


def widget_reclama_la_tecla(widget: QWidget | None, key: int) -> bool:
    """
    ¿El widget con el foco usa esta tecla para lo suyo?

    Es la regla que evita que un atajo global pise la interacción normal:
    escribir en un campo, recorrer la lista de canales con las flechas, mover
    un slider o activar un botón con Espacio.
    """
    if widget is None:
        return False

    # Un campo de texto se queda con cualquier tecla simple.
    if isinstance(widget, _WIDGETS_DE_TEXTO):
        return True

    # Un desplegable editable lleva dentro un QLineEdit.
    if isinstance(widget, QComboBox) and widget.isEditable():
        return True

    if key in _TECLAS_DE_FLECHA and isinstance(widget, _WIDGETS_CON_FLECHAS):
        return True

    # Espacio activa el elemento con el foco: botón, casilla o fila de lista.
    if key == Qt.Key_Space and isinstance(widget, (QAbstractButton, QAbstractItemView)):
        return True

    return False


def _volume_delta(playback, delta: int) -> None:
    """Ajusta el volumen respetando el rango del slider y dejándolo en sync."""
    slider = getattr(playback, "volume_slider", None)
    if slider is None:
        window = getattr(playback, "win", None)
        slider = getattr(window, "volume_slider", None)

    if slider is not None:
        # setValue dispara valueChanged, ya conectado a on_volume_changed:
        # mover el slider basta y mantiene la interfaz coherente con lo que
        # se oye.
        slider.setValue(max(0, min(100, slider.value() + delta)))
        return

    # Sin slider (tests, o una ventana a medio construir) se llama al
    # controlador directamente para no perder la acción.
    on_volume_changed = getattr(playback, "on_volume_changed", None)
    if callable(on_volume_changed):
        on_volume_changed(max(0, min(100, delta)))


def build_callbacks(
    playback,
    go_to_section: Callable[[int], None],
    toggle_fullscreen: Callable[[], None] | None = None,
) -> dict:
    """Mapa acción -> función a ejecutar."""
    callbacks = {
        "toggle_play": lambda: playback.toggle_play(),
        "stop_playback": lambda: playback.stop_playback(),
        "seek_forward": lambda: playback.seek(SEEK_STEP_MS),
        "seek_backward": lambda: playback.seek(-SEEK_STEP_MS),
        "play_next": lambda: playback.play_next(),
        "play_prev": lambda: playback.play_prev(),
        "volume_up": lambda: _volume_delta(playback, VOLUME_STEP),
        "volume_down": lambda: _volume_delta(playback, -VOLUME_STEP),
        "toggle_mute": lambda: playback.toggle_mute(),
        "toggle_favorite": lambda: playback.toggle_favorite_current(),
    }
    if toggle_fullscreen is not None:
        callbacks["toggle_fullscreen"] = lambda: toggle_fullscreen()
    for indice in range(6):
        # indice=indice fija el valor en la definición: sin eso las seis
        # lambdas compartirían la última variable del bucle.
        callbacks[f"go_to_section_{indice}"] = lambda indice=indice: go_to_section(indice)
    return callbacks


class PlaybackShortcutFilter(QObject):
    """
    Filtro de teclas simples que cede el paso al widget con el foco.

    Se instala en la QApplication para ver la pulsación antes de que la
    consuma nadie, pero solo actúa si la ventana asociada está activa y el
    widget enfocado no reclama esa tecla.
    """

    def __init__(self, window: QWidget, callbacks: dict):
        super().__init__(window)
        self._window = window
        self._callbacks = callbacks
        self._por_tecla = {
            spec.key: spec.action for spec in SHORTCUT_SPECS if spec.is_simple
        }

    def eventFilter(self, obj, event):
        if event.type() != QEvent.KeyPress:
            return super().eventFilter(obj, event)

        accion = self._por_tecla.get(event.key())
        if accion is None:
            return super().eventFilter(obj, event)

        # Con modificadores (Ctrl+S, Alt+F...) la tecla no es nuestra.
        if event.modifiers() not in (Qt.NoModifier, Qt.KeypadModifier):
            return super().eventFilter(obj, event)

        # Solo actuamos sobre nuestra ventana: con un diálogo modal abierto
        # encima, sus teclas son suyas.
        ventana = self._window.window()
        if obj is not None and isinstance(obj, QWidget) and obj.window() is not ventana:
            return super().eventFilter(obj, event)

        if widget_reclama_la_tecla(ventana.focusWidget(), event.key()):
            return super().eventFilter(obj, event)

        callback = self._callbacks.get(accion)
        if callback is None:
            return super().eventFilter(obj, event)

        callback()
        return True  # consumida: no debe llegar a nadie más


def register_shortcuts(
    container: QWidget,
    playback,
    go_to_section: Callable[[int], None],
    toggle_fullscreen: Callable[[], None] | None = None,
) -> tuple[PlaybackShortcutFilter, list[QShortcut]]:
    """
    Instala los atajos y devuelve ``(filtro, lista de QShortcut)``.

    Ambos deben guardarse en la ventana: si se descartan, el recolector de
    basura se los lleva y los atajos dejan de responder sin error visible.
    """
    callbacks = build_callbacks(playback, go_to_section, toggle_fullscreen)

    # El filtro va en la QApplication para ver la pulsación antes de que la
    # consuma cualquier widget; él mismo comprueba que la ventana sea la suya.
    filtro = PlaybackShortcutFilter(container, callbacks)
    destino = QApplication.instance() or container
    destino.installEventFilter(filtro)

    creados: list[QShortcut] = []
    for spec in SHORTCUT_SPECS:
        if spec.is_simple:
            continue  # lo gestiona el filtro
        accion = callbacks.get(spec.action)
        if accion is None:
            continue
        atajo = QShortcut(QKeySequence(spec.sequence), container)
        atajo.setContext(Qt.WindowShortcut)
        atajo.activated.connect(accion)
        creados.append(atajo)

    return filtro, creados
