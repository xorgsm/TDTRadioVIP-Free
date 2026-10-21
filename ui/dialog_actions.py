"""
Apertura de diálogos y paneles secundarios de MainWindow (preferencias,
acerca de, activación VIP, diagnóstico, paleta de comandos, grabaciones
recurrentes/programadas, multivista, estadísticas, ecualizador, carpeta
de logs).

Extraído de ui/main_window.py por el mismo motivo que el resto de
controladores (ver ui/playback_controller.py) — toda esta lógica abre
un diálogo modal y reacciona a su resultado, sin relación directa con
cómo se construye o pinta la ventana.

Coder By X@R
"""
import os

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from core import config as cfg
from core import channels as tv_channels
from core import recorder as rec_module
from core.logger import log_file_path
from ui import palette
from ui.command_palette import CommandPalette
from ui.dialogs import SettingsDialog
from ui.equalizer_dialog import EqualizerDialog
from ui.mosaic_view import MosaicView
from ui.keyboard_shortcuts import describe_shortcuts
from ui.nav_sections import NAV_DOWNLOAD, NAV_FAV, NAV_HIST, NAV_HOME, NAV_RADIO, NAV_TV
from ui.recurring_dialog import RecurringRecordingsDialog
from ui.scheduled_recordings_dialog import ScheduledRecordingsDialog
from ui.stats_dialog import StatsDialog
from ui.stream_diagnostics_dialog import StreamDiagnosticsDialog
from ui.style import build_style
from ui.title_bar import update_edition_badge


class DialogActionsController:
    """Apertura de diálogos secundarios de MainWindow (win.dialogs)."""

    def __init__(self, window):
        self.win = window

    def open_equalizer_dialog(self):
        EqualizerDialog(self.win).exec()

    def open_vpn_dialog(self):
        """VPN (edición VIP con licencia activada): ver el docstring de
        ui.dialogs.vpn_dialog para por qué se extrajo de Ajustes a su
        propio diálogo, con entrada directa en el menú "Más ▾" (ver
        ui.more_menu._build_settings_menu, que solo la añade cuando
        win.activated and not win.es_version_free)."""
        from ui.dialogs import VpnDialog

        VpnDialog(self.win).exec()

    def open_activation_dialog(self):
        """
        Configuración > Activar VIP…: reabre el diálogo de activación para
        quien entró en modo gratuito. Si la activación es correcta, las
        funciones VIP se desbloquean en la misma sesión: los accesos a
        Descargas y la paleta de comandos ya consultan win.activated al
        vuelo, así que solo hay que actualizar lo que se decidió al
        construir la ventana (el botón de enviar a TV y esta entrada de menú).

        Import local (no arriba del módulo): esta ruta solo se conecta a un
        menú cuando not win.es_version_free (ver
        ui.more_menu.build_more_menu_button), así que ui.splash -- y
        core.license, que importa a su vez -- no hace falta que se carguen
        nunca en la edición free. Mismo motivo que core.caster/
        ui.download_panel en MainWindow.__init__.
        """
        from ui.splash import SplashDialog

        win = self.win
        dialog = SplashDialog(win, show_profile_selector=False)
        dialog.exec()
        if dialog.activated and not win.activated:
            win.activated = True
            win.cast_btn.setVisible(True)
            win.activate_vip_action.setVisible(False)
            update_edition_badge(win)
            win.statusBar().showMessage("Funciones VIP activadas. ¡Gracias!", 6000)

    def open_stream_diagnostics(self):
        win = self.win
        dialog = StreamDiagnosticsDialog(win.tv_channels_data, win.radio_stations_data, win)
        dialog.exec()
        # El guardado del diagnóstico va en un worker: se refresca otra vez
        # cuando termine, por si al cerrar aún no había acabado.
        persist_worker = getattr(dialog, "_persist_worker", None)
        if persist_worker is not None:
            persist_worker.done.connect(
                lambda _recorded: None if win._is_closing else win.home.refresh_home_health()
            )
        win.home.refresh_home_health()
        if dialog.catalog_changed and not win._is_closing:
            win.catalog.load_tv_channels()
            win.catalog.load_radio_stations()

    def open_command_palette(self):
        """
        Búsqueda global (Ctrl+K / menú Archivo). Las "acciones rápidas" se
        arman aquí, no dentro de CommandPalette, para que ese módulo no
        tenga que importar NAV_HOME/NAV_TV/etc. de ui.nav_sections (crearía
        un import circular si CommandPalette importara de aquí y aquí se
        importara CommandPalette).
        """
        win = self.win
        acciones = [
            ("Preferencias…", self.open_settings),
            ("Ir a Inicio", lambda: win.nav_group.button(NAV_HOME).click()),
            ("Ir a Televisión", lambda: win.nav_group.button(NAV_TV).click()),
            ("Ir a Radio", lambda: win.nav_group.button(NAV_RADIO).click()),
            ("Ir a Favoritos", lambda: win.nav_group.button(NAV_FAV).click()),
            ("Ir a Historial", lambda: win.nav_group.button(NAV_HIST).click()),
            ("Añadir canal o emisora…", win.library.open_add_entry_dialog),
            ("Importar lista M3U…", win.library.open_import_playlist_dialog),
            ("Añadir lista pública de TV…", win.library.open_add_public_tv_list_dialog),
            ("Gestionar canales personalizados…", lambda: win.library.open_manage_channels_dialog()),
        ]
        if win.activated and not win.es_version_free:
            acciones.append(("Ir a Descargas", lambda: win.nav_group.button(NAV_DOWNLOAD).click()))

        dialog = CommandPalette(win, acciones)
        dialog.show_centered()

    def open_recurring_dialog(self):
        win = self.win
        RecurringRecordingsDialog(win, win.tv_channels_data).exec()

    def open_scheduled_recordings_dialog(self):
        ScheduledRecordingsDialog(self.win).exec()

    def open_mosaic_view(self):
        win = self.win
        if not win.tv_channels_data:
            QMessageBox.information(
                win, "Multivista", "Espera a que carguen los canales de TV."
            )
            return

        # La multivista abre hasta 4 instancias de VLC en paralelo (ver
        # ui/mosaic_view.py) -- sumadas a la del reproductor principal, son
        # 5 streams compitiendo a la vez por el dispositivo de audio, que en
        # Windows es lo que dejaba mudo al canal principal al cerrar la
        # multivista (seguía "reproduciendo" pero sin sonido, y hacía falta
        # reiniciar la app). Se para del todo mientras el diálogo está
        # abierto -- no se ve de todas formas, tapa la ventana entera -- y
        # se retoma desde cero (media_player limpio, ver VLCPlayer.play) al
        # cerrarlo.
        reanudar = None
        if win.current_url:
            reanudar = (
                win.current_type, win.current_name, win.current_url,
                win.current_tvg_id, win.current_logo, list(win._current_alternate_urls),
            )
            win.player.stop()
            win.equalizer.stop()

        MosaicView(win, win.tv_channels_data).exec()

        if reanudar is not None:
            win.playback.play(*reanudar)

    def open_stats_dialog(self):
        StatsDialog(self.win).exec()

    def open_settings(self):
        win = self.win
        old_tv_url = win.settings.get("tv_playlist_url") or tv_channels.playlist_url_for(
            win.settings.get("tv_country_code", "ES")
        )
        old_radio_country = win.settings.get("radio_country_code", "ES")
        old_accent = win.settings.get("accent_color", palette.ACCENT)
        old_theme = win.settings.get("theme_mode", "dark")
        old_card_size = int(win.settings.get("catalog_card_size", 168))
        old_profile = win.settings.get("active_profile", "Default")
        dialog = SettingsDialog(win.settings, win)
        if dialog.exec() == QDialog.Accepted:
            new_settings = dialog.get_settings()
            if not cfg.save_settings(new_settings):
                QMessageBox.warning(
                    win,
                    "No se pudieron guardar los ajustes",
                    "No se pudieron guardar los ajustes. Inténtalo de nuevo.",
                )
                return
            win.settings = new_settings

            new_profile = win.settings.get("active_profile", "Default")
            if new_profile != old_profile:
                QMessageBox.information(
                    win, "Perfil cambiado",
                    f"Perfil activo: {new_profile}.\n\n"
                    "Cierra y vuelve a abrir la aplicación para que se aplique del todo."
                )
            win.recordings_dir = win.settings.get("recordings_dir") or win.downloads_dir
            if not win.recorder.is_recording:
                win.recorder = rec_module.Recorder(win.recordings_dir)
                win.recordings_dir = str(win.recorder.output_dir)
            if win.settings.get("epg_url"):
                win.epg.load()

            new_accent = win.settings.get("accent_color", palette.ACCENT)
            new_theme = win.settings.get("theme_mode", "dark")
            if new_accent != old_accent or new_theme != old_theme:
                app = QApplication.instance()
                if app is not None:
                    app.setStyleSheet(build_style(new_accent, new_theme))

            new_card_size = int(win.settings.get("catalog_card_size", 168))
            if new_card_size != old_card_size:
                win.grid_delegate.CARD_SIZE = new_card_size
                if win.tv_view_toggle.isChecked():
                    grid_size = QSize(new_card_size, new_card_size)
                    win.tv_list.setGridSize(grid_size)
                    win.radio_list.setGridSize(grid_size)

            new_tv_url = win.settings.get("tv_playlist_url") or tv_channels.playlist_url_for(
                win.settings.get("tv_country_code", "ES")
            )
            if new_tv_url != old_tv_url:
                win.catalog.load_tv_channels()
            if win.settings.get("radio_country_code", "ES") != old_radio_country:
                win.catalog.load_radio_stations()

    def open_logs_folder(self):
        carpeta = log_file_path().parent
        carpeta.mkdir(parents=True, exist_ok=True)
        os.startfile(carpeta)

    def show_keyboard_shortcuts(self):
        """
        Lista de atajos disponibles, generada desde SHORTCUT_SPECS para que
        no pueda quedarse desfasada respecto a los atajos reales.
        """
        win = self.win
        filas = "".join(
            f"<tr>"
            f"<td style='padding:4px 18px 4px 0; font-weight:700; "
            f"color:{palette.ACCENT};'>{teclas}</td>"
            f"<td style='padding:4px 0;'>{descripcion}</td>"
            f"</tr>"
            for teclas, descripcion in describe_shortcuts()
        )
        extra = (
            ("F11", "Pantalla completa (alternativa a F)"),
            ("Esc", "Salir de pantalla completa"),
            ("Ctrl+K", "Búsqueda global"),
        )
        filas += "".join(
            f"<tr>"
            f"<td style='padding:4px 18px 4px 0; font-weight:700; "
            f"color:{palette.ACCENT};'>{teclas}</td>"
            f"<td style='padding:4px 0;'>{descripcion}</td>"
            f"</tr>"
            for teclas, descripcion in extra
        )
        QMessageBox.information(
            win, "Atajos de teclado",
            "<b>Atajos de teclado</b><br>"
            "<span style='font-size:9pt;'>Las teclas sueltas no actúan "
            "mientras escribes en un campo de texto o te mueves por la lista "
            "de canales.</span><br><br>"
            f"<table>{filas}</table>",
        )

    def show_about(self):
        win = self.win
        if win.es_version_free:
            registro_html = (
                f"<p style='font-size:13pt; font-weight:700; color:{palette.ACCENT_INFO};'>"
                "Versión FREE — TV y Radio incluidos, sin Descargas ni Chromecast</p>"
            )
        elif win.activated:
            registro_html = (
                f"<p style='font-size:13pt; font-weight:700; color:{palette.SUCCESS};'>"
                "Aplicación registrada</p>"
            )
        else:
            registro_html = (
                f"<p style='font-size:13pt; font-weight:700; color:{palette.DANGER};'>"
                "Versión no activada</p>"
            )
        QMessageBox.about(
            win, "Acerca de",
            f"<b>TDT & Radio VIP</b> — versión {cfg.APP_VERSION}<br>"
            "Coder By X@R<br><br>"
            f"{registro_html}"
            "Reproductor de canales de TDT y radio online gratuitos.<br>"
            "Fuentes: iptv-org (TV) y Radio-Browser (radio).<br><br>"
            "La disponibilidad y calidad de los streams depende de terceros ajenos a esta aplicación.<br><br>"
            "<table width='100%' cellpadding='12' cellspacing='0' bgcolor='#14161b' "
            "style='border:1px solid #7c6cff; border-radius:10px;'>"
            "<tr><td>"
            "<b style='color:#7c6cff; font-size:12pt;'>TDTChannels</b><br>"
            "Proporciona listas oficiales y legales de television terrestre en Espana "
            "en formato M3U y M3U8.<br>"
            f"<a href='https://www.tdtchannels.com/lists/tv.m3u8' style='color:{palette.ACCENT_INFO};'>"
            "https://www.tdtchannels.com/lists/tv.m3u8</a>"
            "</td></tr></table><br>"
            "<hr>"
            f"<b style='color:{palette.ACCENT};'>&#10084; Un Abrazo grande a mi hijo Hugo Moreno &#161;ERES UN CAMPE&#211;N! &#10084;</b><br>"
            f"<b style='color:{palette.ACCENT};'>&#10084; Besitos a Evelyn Llamas &#10084;</b><br>"
            "Saludos a mi amigo Paco Blanco.<br>"
            "Viva La Guardia Civil — SANCHEZ CABRON:<br>"
            "<b>¡España Campeona del Mundo! "
            "<img src='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAB4AAAAUCAIAAAAVyRqTAAAALUlEQVR4nGNcJSrNQBvARCNzR43GBIwf99PK6KEZIKNGjxo9YEYzjhaqw8FoABs0A4rK4LUlAAAAAElFTkSuQmCC' width='24' height='16'> "
            "&#127942; &#128170; ¡OLÉ, LA UCO!</b><br><br>"
            "Ceuta y Melilla Españolas siempre! Ole Mi Juanito Gordito Y Aitor Super CARS! Edu The Punicher . "
            "<img src='data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAB4AAAAUCAIAAAAVyRqTAAAALUlEQVR4nGNcJSrNQBvARCNzR43GBIwf99PK6KEZIKNGjxo9YEYzjhaqw8FoABs0A4rK4LUlAAAAAElFTkSuQmCC' width='24' height='16'>"
        )
