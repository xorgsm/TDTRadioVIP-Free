"""
Apertura de diálogos modales que se destruyen al cerrarse.

Un QDialog con padre (la ventana principal) no se destruye al terminar
exec(): solo se oculta, y sigue vivo con todos sus widgets y datos hasta
que se cierra la app. Cada apertura de la guía EPG, el editor M3U, la
multivista... dejaba así otra copia completa en memoria.

No usar con diálogos que dejen QThreads propios corriendo al cerrarse
(p. ej. VpnDialog): destruirlos con el hilo vivo abortaría la app.

Coder By X@R
"""
from PySide6.QtWidgets import QDialog


def run_modal(dialog: QDialog) -> int:
    """exec() del diálogo y deleteLater() al volver; devuelve el resultado de exec()."""
    try:
        return dialog.exec()
    finally:
        dialog.deleteLater()
