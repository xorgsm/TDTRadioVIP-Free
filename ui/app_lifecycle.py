"""
Arranque diferido (copia automática, reanudar última emisión, aviso de
VLC no disponible, onboarding) y cierre ordenado de MainWindow.

Extraído de ui/main_window.py por el mismo motivo que el resto de
controladores (ver ui/playback_controller.py).

Coder By X@R
"""
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox

from core import backup as backup_module
from core import config as cfg
from core import recording_schedule
from ui.fetch_worker import (
    FetchWorker,
    process_events_during_shutdown,
    shutdown_workers,
)
from ui.onboarding import OnboardingDialog


class AppLifecycle:
    """Arranque diferido y cierre ordenado de MainWindow (win.lifecycle)."""

    def __init__(self, window):
        self.win = window

    def schedule_startup_tasks(self):
        win = self.win
        if win.settings.get("automatic_backups_enabled", True):
            QTimer.singleShot(1500, self.run_automatic_backup)
        if win.settings.get("resume_last_stream", False):
            QTimer.singleShot(2200, self.resume_last_stream)

        if not win.player.disponible:
            # Antes esto reventaba en el arranque con un error críptico. Ahora
            # la app abre igual (descargas, listas, favoritos siguen usables)
            # y se explica qué falta.
            QTimer.singleShot(300, self.warn_vlc_unavailable)

        if not win.settings.get("onboarding_shown"):
            # Con un pequeño retraso, para que se vea primero la ventana
            # principal ya construida detrás en vez de un diálogo modal
            # tapándolo todo desde el primer frame.
            QTimer.singleShot(500, self.show_onboarding)

    def show_onboarding(self):
        win = self.win
        OnboardingDialog(win).exec()
        win.settings["onboarding_shown"] = True
        if not cfg.save_settings(win.settings):
            QMessageBox.warning(
                win,
                "No se pudieron guardar los ajustes",
                "No se pudieron guardar los ajustes. Inténtalo de nuevo.",
            )

    def warn_vlc_unavailable(self):
        win = self.win
        QMessageBox.warning(
            win,
            "Motor de vídeo no disponible",
            f"{win.player.motivo_no_disponible()}\n\n"
            "La reproducción de TV y radio no funcionará. El resto de la "
            "aplicación (descargas, listas y favoritos) sigue disponible.",
        )
        win.statusBar().showMessage("VLC no disponible: la reproducción está desactivada.")

    def run_automatic_backup(self):
        win = self.win
        if win._is_closing:
            return
        previous = getattr(win, "_backup_worker", None)
        if previous is not None and previous.isRunning():
            return
        try:
            worker = FetchWorker(
                backup_module.run_automatic_backup,
                cfg.get_app_data_dir() / "backups",
                interval_days=int(win.settings.get("automatic_backup_interval_days", 1)),
                retention=int(win.settings.get("automatic_backup_retention", 7)),
                app_data_dir=cfg.get_app_data_dir(),
                profile_data_dir=cfg.get_profile_data_dir(),
            )
        except (OSError, ValueError):
            win.statusBar().showMessage("No se pudo crear la copia automática.", 5000)
            return
        worker.done.connect(self._on_automatic_backup_done)
        win._backup_worker = worker
        worker.start()

    def _on_automatic_backup_done(self, result):
        win = self.win
        if win._is_closing:
            return
        if result is None:
            win.statusBar().showMessage("No se pudo crear la copia automática.", 5000)
        elif result:
            win.statusBar().showMessage("Copia de seguridad automática creada.", 4000)

    def resume_last_stream(self):
        win = self.win
        if win._is_closing or win.current_url or not win.history:
            return
        entry = win.history[0]
        if entry.get("url") and entry.get("type") in ("tv", "radio"):
            win.playback.play(
                entry["type"], entry.get("name", "Última emisión"), entry["url"],
                entry.get("tvg_id", ""), entry.get("logo", ""),
            )

    def shutdown(self):
        win = self.win
        win._is_closing = True
        FetchWorker.begin_shutdown()
        reminder_timer = getattr(win, "_reminder_timer", None)
        if reminder_timer is not None:
            reminder_timer.stop()
        win._tray_icon.hide()
        win._media_keys.stop()
        if win.recorder.is_recording:
            # on_wait bombea eventos sin entrada de usuario: sin esto, cerrar la app
            # con una grabación en curso bloqueaba el hilo de la interfaz
            # mientras ffmpeg terminaba de cerrar el archivo -- Windows
            # llegaba a marcar la ventana como "no responde" antes de que
            # terminara. Ver core.recorder.Recorder.stop().
            win.recorder.stop(on_wait=process_events_during_shutdown)
            if win._scheduled_recording_active is not None:
                rec = win._scheduled_recording_active
                recording_schedule.mark_done(rec.tvg_id, rec.title, rec.start)
                win._scheduled_recording_active = None
        win.player.stop()
        win.equalizer.stop()
        if win._cast_session is not None:
            win._cast_session.disconnect()
            win._dlna_session.disconnect()
        if win.download_panel is not None:
            # on_wait: se reenvía por compatibilidad con la firma anterior
            # (ver el comentario del recorder.stop() más arriba) -- con
            # libtorrent embebido en el proceso ya no hay un aria2c.exe
            # aparte que esperar a que se apague, así que en la práctica ya
            # no bloquea nada.
            win.download_panel.shutdown(on_wait=process_events_during_shutdown)
        win._taskbar.cleanup()
        # El diagnóstico automático de streams corre en un QThread propio
        # que no pasa por ActiveWorkerRegistry (StreamDiagnosticsWorker no
        # es un FetchWorker) -- sin cancelarlo y esperarlo aquí, cerrar la
        # app mientras seguía corriendo lo dejaba vivo destruyéndose la
        # ventana debajo, la misma clase de carrera que ya se corrigió para
        # Torrents/Soulseek (ver CHANGELOG).
        diagnostics_worker = win.catalog.cancel_background_diagnostics()
        workers = FetchWorker.active_workers()
        if diagnostics_worker is not None:
            workers = (*workers, diagnostics_worker)
        shutdown_workers(workers)
        win.player.release()
