"""
Controlador de comprobación de actualizaciones de TDT & Radio VIP: consulta
manual desde Ayuda > Buscar actualizaciones, y descarga/verificación segura
(SHA-256) del instalador si el usuario lo pide.

Extraído de ui/main_window.py por el mismo motivo que
ui.playback_controller.PlaybackController y el resto de controladores —
ver el docstring de PlaybackController para la explicación completa del
porqué del patrón (estado en MainWindow, comportamiento aquí).

Coder By X@R
"""
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox

from core import config as cfg
from core import updater
from ui.fetch_worker import FetchWorker


class UpdateCheckController:
    """Comprobación manual de actualizaciones y descarga verificada del instalador."""

    def __init__(self, window):
        self.win = window

    def check_for_update(self):
        """
        Comprobación manual desde Ayuda > Buscar actualizaciones. Solo
        avisa y ofrece abrir la página de descarga -- no descarga ni
        reemplaza nada sola (ver core/updater.py para el porqué).
        """
        win = self.win
        if win._is_closing:
            return
        url = win.settings.get("update_check_url", "")
        if not url:
            QMessageBox.information(
                win, "Buscar actualizaciones",
                "La comprobación de actualizaciones no está configurada en esta instalación.",
            )
            return
        win.statusBar().showMessage("Comprobando actualizaciones…", 4000)
        worker = FetchWorker(updater.check_for_update, url, cfg.APP_VERSION)
        worker.done.connect(self._on_update_check_done)
        win._update_check_worker = worker
        worker.start()

    def _on_update_check_done(self, resultado):
        win = self.win
        if win._is_closing:
            return
        if not resultado:
            QMessageBox.information(
                win, "Buscar actualizaciones", "Ya tienes la versión más reciente."
            )
            return
        version = resultado.get("version", "?")
        enlace = resultado.get("download_url") or resultado.get("url", "")
        secure_download = bool(resultado.get("sha256") and enlace)
        respuesta = QMessageBox.question(
            win, "Actualización disponible",
            f"Hay una versión nueva disponible: {version} "
            f"(la instalada es {cfg.APP_VERSION}).\n\n"
            + ("¿Descargar y verificar el instalador?" if secure_download
               else "¿Abrir la página de descarga?"),
        )
        if respuesta == QMessageBox.Yes and enlace:
            if secure_download:
                worker = FetchWorker(
                    updater.download_verified_update,
                    resultado,
                    cfg.get_app_data_dir() / "updates",
                )
                worker.done.connect(self._on_update_download_done)
                win._update_download_worker = worker
                win.statusBar().showMessage("Descargando actualización segura…")
                worker.start()
            else:
                QDesktopServices.openUrl(QUrl(enlace))

    def _on_update_download_done(self, path):
        win = self.win
        if win._is_closing:
            return
        if not path:
            QMessageBox.warning(
                win, "Actualización", "No se pudo descargar o verificar la actualización."
            )
            return
        if QMessageBox.question(
            win, "Actualización verificada",
            "El instalador superó la verificación SHA-256.\n\n¿Ejecutarlo ahora?",
        ) == QMessageBox.Yes:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
