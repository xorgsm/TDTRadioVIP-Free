"""Bombeo de eventos de Qt durante esperas largas en el hilo de la interfaz."""
from PySide6.QtCore import QEventLoop
from PySide6.QtWidgets import QApplication


def pump_events_without_input() -> None:
    """``QApplication.processEvents`` sin eventos de entrada del usuario.

    Mantiene la ventana repintándose (Windows no la marca "no responde")
    pero no entrega clics ni teclas: así, mientras se espera a que ffmpeg
    cierre una grabación, el usuario no puede volver a pulsar "grabar" o
    cerrar la ventana a mitad de la parada y reentrar en el mismo código.
    """
    QApplication.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
