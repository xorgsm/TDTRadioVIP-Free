"""
Atajos de teclado globales de la ventana principal.

`PRODUCT.md` compromete navegación por teclado, pero hasta ahora la ventana
solo registraba tres atajos (F11, Esc, Ctrl+K). Estos tests fijan el conjunto
completo y, sobre todo, la invariante que hace que sean usables:

**un atajo de una sola tecla no puede pisar la interacción normal del widget
con el foco.** Escribir en el buscador, recorrer la lista de canales con las
flechas, mover el slider de volumen o activar un botón con Espacio tienen que
seguir funcionando. Esto no es teórico: la primera implementación usaba
QShortcut y hacía que la flecha Abajo sobre la lista de canales bajase el
volumen en vez de cambiar de canal.
"""
import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSlider,
    QWidget,
)

from ui.keyboard_shortcuts import (
    SEEK_STEP_MS,
    SHORTCUT_SPECS,
    VOLUME_STEP,
    build_callbacks,
    describe_shortcuts,
    register_shortcuts,
    widget_reclama_la_tecla,
)


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


class _PlaybackDoble:
    """Registra qué acción de reproducción se invocó."""

    def __init__(self, volume_slider=None):
        self.llamadas = []
        self.volume_slider = volume_slider

    def toggle_play(self):
        self.llamadas.append("toggle_play")

    def toggle_mute(self):
        self.llamadas.append("toggle_mute")

    def play_next(self):
        self.llamadas.append("play_next")

    def play_prev(self):
        self.llamadas.append("play_prev")

    def stop_playback(self):
        self.llamadas.append("stop_playback")

    def toggle_favorite_current(self):
        self.llamadas.append("toggle_favorite_current")

    def seek(self, offset_ms):
        self.llamadas.append(("seek", offset_ms))

    def on_volume_changed(self, value):
        self.llamadas.append(("volumen", value))


# ---------------------------------------------------------------------------
# Coherencia de la tabla de atajos
# ---------------------------------------------------------------------------

def test_no_hay_atajos_duplicados():
    """Dos acciones con la misma tecla: una de las dos nunca se dispararía."""
    secuencias = [spec.sequence for spec in SHORTCUT_SPECS]
    duplicados = {s for s in secuencias if secuencias.count(s) > 1}
    assert not duplicados, f"atajos duplicados: {duplicados}"


def test_no_chocan_con_los_atajos_ya_existentes():
    """F11, Esc y Ctrl+K los registra MainWindow._registrar_atajos aparte."""
    ya_usados = {"F11", "Esc", "Ctrl+K"}
    nuestros = {spec.sequence for spec in SHORTCUT_SPECS}
    assert not (nuestros & ya_usados), f"colisión: {nuestros & ya_usados}"


def test_todas_las_secuencias_son_validas():
    for spec in SHORTCUT_SPECS:
        assert not QKeySequence(spec.sequence).isEmpty(), (
            f"{spec.sequence!r} no es una secuencia de teclas válida"
        )


def test_todas_tienen_descripcion():
    """describe_shortcuts alimenta la ayuda; ninguna acción puede ir sin texto."""
    for spec in SHORTCUT_SPECS:
        assert spec.description.strip(), f"{spec.sequence} sin descripción"


def test_las_teclas_simples_declaran_su_codigo_de_tecla():
    """El filtro de eventos busca por Qt.Key_*, no por texto."""
    for spec in SHORTCUT_SPECS:
        if spec.is_simple:
            assert spec.key is not None, f"{spec.sequence} sin Qt.Key_*"
        else:
            assert spec.sequence.startswith("Ctrl+")


def test_describe_shortcuts_devuelve_pares_legibles():
    filas = describe_shortcuts()
    assert len(filas) == len(SHORTCUT_SPECS)
    for tecla, descripcion in filas:
        assert isinstance(tecla, str) and tecla
        assert isinstance(descripcion, str) and descripcion


# ---------------------------------------------------------------------------
# La invariante: ceder la tecla al widget que la usa
# ---------------------------------------------------------------------------

def test_campo_de_texto_reclama_todas_las_teclas_simples(app):
    """Escribir 'space', 'n' o 'f' en el buscador no puede disparar acciones."""
    campo = QLineEdit()
    for spec in SHORTCUT_SPECS:
        if spec.is_simple:
            assert widget_reclama_la_tecla(campo, spec.key), (
                f"{spec.sequence} se le robaría a un campo de texto"
            )


def test_lista_de_canales_reclama_las_flechas(app):
    """La regresión concreta: Abajo debe cambiar de canal, no bajar volumen."""
    lista = QListWidget()
    for tecla in (Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right):
        assert widget_reclama_la_tecla(lista, tecla)


def test_lista_de_canales_reclama_espacio(app):
    """Espacio activa la fila seleccionada."""
    assert widget_reclama_la_tecla(QListWidget(), Qt.Key_Space)


def test_slider_de_volumen_reclama_las_flechas(app):
    slider = QSlider(Qt.Horizontal)
    assert widget_reclama_la_tecla(slider, Qt.Key_Left)
    assert widget_reclama_la_tecla(slider, Qt.Key_Right)


def test_boton_reclama_espacio(app):
    """Espacio sobre un botón enfocado debe pulsarlo, no pausar."""
    assert widget_reclama_la_tecla(QPushButton("Aceptar"), Qt.Key_Space)


def test_desplegable_editable_reclama_las_letras(app):
    editable = QComboBox()
    editable.setEditable(True)
    assert widget_reclama_la_tecla(editable, Qt.Key_N)


def test_widget_neutro_no_reclama_nada(app):
    """Sobre un contenedor sin interacción propia, los atajos sí actúan."""
    neutro = QWidget()
    for tecla in (Qt.Key_Space, Qt.Key_N, Qt.Key_M, Qt.Key_F, Qt.Key_Up):
        assert not widget_reclama_la_tecla(neutro, tecla)


def test_sin_foco_no_reclama_nada():
    assert not widget_reclama_la_tecla(None, Qt.Key_Space)


def test_boton_no_reclama_las_letras(app):
    """Un botón se queda Espacio, pero N/M/F siguen siendo atajos."""
    boton = QPushButton("Aceptar")
    for tecla in (Qt.Key_N, Qt.Key_M, Qt.Key_F, Qt.Key_S):
        assert not widget_reclama_la_tecla(boton, tecla)


# ---------------------------------------------------------------------------
# Las acciones hacen lo que dicen
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("accion,metodo", [
    ("toggle_play", "toggle_play"),
    ("stop_playback", "stop_playback"),
    ("play_next", "play_next"),
    ("play_prev", "play_prev"),
    ("toggle_mute", "toggle_mute"),
    ("toggle_favorite", "toggle_favorite_current"),
])
def test_accion_invoca_el_metodo_de_reproduccion(accion, metodo):
    playback = _PlaybackDoble()
    build_callbacks(playback, lambda _i: None)[accion]()
    assert metodo in playback.llamadas


@pytest.mark.parametrize("accion,offset", [
    ("seek_forward", SEEK_STEP_MS),
    ("seek_backward", -SEEK_STEP_MS),
])
def test_seek_usa_el_paso_de_30_segundos(accion, offset):
    playback = _PlaybackDoble()
    build_callbacks(playback, lambda _i: None)[accion]()
    assert ("seek", offset) in playback.llamadas


def test_volumen_mueve_el_slider(app):
    slider = QSlider(Qt.Horizontal)
    slider.setRange(0, 100)
    slider.setValue(50)
    callbacks = build_callbacks(_PlaybackDoble(slider), lambda _i: None)

    callbacks["volume_up"]()
    assert slider.value() == 50 + VOLUME_STEP
    callbacks["volume_down"]()
    assert slider.value() == 50


@pytest.mark.parametrize("inicial,accion,esperado", [
    (98, "volume_up", 100),    # no pasa de 100
    (2, "volume_down", 0),     # no baja de 0
    (100, "volume_up", 100),
    (0, "volume_down", 0),
])
def test_volumen_respeta_los_limites(app, inicial, accion, esperado):
    slider = QSlider(Qt.Horizontal)
    slider.setRange(0, 100)
    slider.setValue(inicial)
    build_callbacks(_PlaybackDoble(slider), lambda _i: None)[accion]()
    assert slider.value() == esperado


def test_ctrl_numero_salta_a_cada_seccion():
    visitadas = []
    callbacks = build_callbacks(_PlaybackDoble(), visitadas.append)
    for indice in range(6):
        callbacks[f"go_to_section_{indice}"]()
    assert visitadas == [0, 1, 2, 3, 4, 5]


# ---------------------------------------------------------------------------
# Registro
# ---------------------------------------------------------------------------

def test_register_shortcuts_devuelve_filtro_y_qshortcuts(app):
    contenedor = QWidget()
    filtro, creados = register_shortcuts(contenedor, _PlaybackDoble(), lambda _i: None)

    assert filtro is not None, "el filtro debe devolverse para guardar la referencia"

    # Solo las combinaciones con Ctrl son QShortcut; las simples van al filtro.
    combinaciones = [spec for spec in SHORTCUT_SPECS if not spec.is_simple]
    assert len(creados) == len(combinaciones)
    secuencias = {s.key().toString() for s in creados}
    esperadas = {QKeySequence(spec.sequence).toString() for spec in combinaciones}
    assert secuencias == esperadas
