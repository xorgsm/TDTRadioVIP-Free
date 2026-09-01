"""
Controlador de envío a la TV (Chromecast / Google Cast / DLNA) de
TDT & Radio VIP: elegir dispositivo, conectar con el backend correcto y
enviarle la emisión en directo o un archivo local ya descargado.

Extraído de ui/main_window.py por el mismo motivo que
ui.playback_controller.PlaybackController y el resto de controladores —
ver el docstring de PlaybackController para la explicación completa del
porqué del patrón (estado en MainWindow, comportamiento aquí).

Coder By X@R
"""
import os

from PySide6.QtWidgets import QDialog, QMessageBox

from core.caster import guess_stream_content_type
from ui.cast_dialog import BACKEND_CHROMECAST, CastDeviceDialog


class CastController:
    """Selección de dispositivo y envío de la reproducción actual o un archivo local a la TV."""

    def __init__(self, window):
        self.win = window

    def _active_session(self):
        """Sesión de casting con un dispositivo conectado ahora mismo, o None."""
        win = self.win
        if win._cast_session.device is not None:
            return win._cast_session
        if win._dlna_session.device is not None:
            return win._dlna_session
        return None

    def on_cast_live_clicked(self):
        win = self.win
        sesion = self._active_session()
        if sesion is not None:
            sesion.disconnect()
            win.cast_btn.setChecked(False)
            win.statusBar().showMessage("Envío a la TV detenido.", 4000)
            return

        if not win.current_url:
            win.cast_btn.setChecked(False)
            QMessageBox.information(
                win, "Nada en reproducción", "Elige un canal o una emisora primero."
            )
            return

        content_type = guess_stream_content_type(win.current_url, win.current_type or "")
        self._open_picker_and_send(
            title=win.current_name or "", url=win.current_url, content_type=content_type
        )

    def cast_local_file(self, filepath: str, title: str):
        if not os.path.isfile(filepath):
            QMessageBox.warning(
                self.win, "Archivo no encontrado", "El archivo descargado ya no está en esa ubicación."
            )
            return
        self._open_picker_and_send(title=title, local_path=filepath)

    def _open_picker_and_send(
        self, *, title: str, url: str | None = None, local_path: str | None = None,
        content_type: str | None = None,
    ):
        win = self.win
        sesion_activa = self._active_session()
        if sesion_activa is not None:
            sesion_activa.disconnect()

        dialog = CastDeviceDialog(win)
        try:
            if dialog.exec() != QDialog.Accepted or not dialog.selected_name:
                win.cast_btn.setChecked(False)
                return

            backend = dialog.selected_backend
            worker = dialog.get_worker(backend)
            device = worker.device_by_name(dialog.selected_name) if worker else None
            if device is None:
                win.cast_btn.setChecked(False)
                QMessageBox.warning(
                    win, "Dispositivo no disponible", "No se pudo conectar con ese dispositivo."
                )
                return

            sesion = win._cast_session if backend == BACKEND_CHROMECAST else win._dlna_session
            try:
                sesion.connect(device)
                if local_path:
                    sesion.cast_local_file(local_path, title=title)
                else:
                    sesion.cast_url(url, content_type or "video/mp4", title=title)
                win.cast_btn.setChecked(True)
                win.statusBar().showMessage(f"Enviando «{title}» a {device.name}…", 6000)
            except Exception as exc:
                win.cast_btn.setChecked(False)
                sesion.disconnect()
                QMessageBox.warning(win, "Error al enviar a la TV", str(exc))
        finally:
            # Pase lo que pase (aceptar, cancelar o error), hay que cerrar el
            # explorador zeroconf: si no, cada búsqueda deja sockets abiertos.
            dialog.release_worker()
