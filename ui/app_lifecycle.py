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
from core import updater
from core import vpn_client, vpn_profiles
from core.logger import get_logger
from ui.fetch_worker import (
    FetchWorker,
    process_events_during_shutdown,
    shutdown_workers,
)
from ui.onboarding import OnboardingDialog
from ui.toast import show_toast

log = get_logger(__name__)


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

        # Limpieza de instaladores de actualización ya obsoletos (ver
        # core.updater.cleanup_obsolete_updates) -- sin prisa, al final de
        # la cola de arranque diferido; es solo higiene de disco, no algo
        # que el usuario esté esperando ver.
        QTimer.singleShot(4000, self.cleanup_old_updates)

        if win.settings.get("automatic_update_check", True):
            QTimer.singleShot(5000, self.check_update_automatically)

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

    def cleanup_old_updates(self):
        """Borra los instaladores de actualización ya obsoletos que hayan
        podido quedar acumulados en %APPDATA%/.../updates -- tanto los que
        deja atrás una descarga nueva (ver
        core.updater.download_verified_update, ya se limpia solo en ese
        momento) como los que se acumularon antes de que existiera esa
        limpieza, en instalaciones ya existentes."""
        win = self.win
        if win._is_closing:
            return
        try:
            updater.cleanup_obsolete_updates(cfg.get_app_data_dir() / "updates")
        except OSError:
            pass

    def check_update_automatically(self):
        """
        Comprobación silenciosa al arrancar (como mucho una vez al día, ver
        core.updater.check_for_update_if_due) -- si hay una versión nueva,
        avisa con un toast no bloqueante; si no la hay, si la URL está
        vacía o si ya se comprobó hoy, no hace nada visible. Nunca
        descarga ni instala sola -- ver _on_automatic_update_check_done()
        para lo que pasa si el usuario pulsa "Ver".
        """
        win = self.win
        if win._is_closing:
            return
        url = win.settings.get("update_check_url", "")
        if not url:
            return
        worker = FetchWorker(
            updater.check_for_update_if_due,
            url,
            cfg.get_app_data_dir() / "updates",
            cfg.APP_VERSION,
        )
        worker.done.connect(self._on_automatic_update_check_done)
        win._auto_update_check_worker = worker
        worker.start()

    def _on_automatic_update_check_done(self, resultado):
        win = self.win
        if win._is_closing or not resultado:
            return
        version = resultado.get("version", "?")
        show_toast(
            win, f"Hay una actualización disponible: {version}",
            undo_text="Ver",
            on_undo=lambda: win.updates.on_update_check_done(resultado),
            timeout_ms=12000,
        )

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

    def disconnect_vpn_profiles(self) -> None:
        """Corta cualquier túnel VPN que siga conectado al cerrar la app.

        Sin esto, openvpn-gui.exe sigue gestionando el túnel de forma
        totalmente independiente de la app -- cerrar TDT Radio VIP no lo
        tocaba, se quedaba conectado hasta desconectarlo a mano (en
        Ajustes o en la ventana propia de OpenVPN). No hace falta que el
        usuario pertenezca a ningún grupo especial para desconectar (ver
        core/vpn_client.py), así que es seguro intentarlo siempre que
        haya perfiles.

        `except Exception` a propósito, con log: esto corre dentro de
        closeEvent() y esta app no tiene manejador global de
        excepciones (ni consola, al ser un .exe sin ventana) -- un
        fallo aquí sin capturar (confirmado con un usuario real:
        openvpn-gui.exe sin responder a tiempo, subprocess.run()
        lanzando TimeoutExpired) desaparecía en silencio y cortaba el
        resto del cierre a medias, sin ningún rastro. Mejor un intento
        de best-effort por perfil que nunca bloquee cerrar la app."""
        if not vpn_client.is_openvpn_installed():
            return
        for entry in vpn_profiles.list_profiles():
            tunnel = entry["tunnel"]
            try:
                if vpn_client.status(tunnel):
                    vpn_client.disconnect(tunnel)
            except Exception:
                log.exception("Fallo al desconectar el perfil VPN %s al cerrar la app", tunnel)

    def shutdown(self):
        win = self.win
        win._is_closing = True
        self.disconnect_vpn_profiles()
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
