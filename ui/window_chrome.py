"""
Controlador de "cromado" de ventana de TDT & Radio VIP: arrastre de la
barra de título propia (sin bordes nativos de Windows), maximizar/
restaurar, pantalla completa del reproductor y modo ventana flotante
(picture-in-picture).

Extraído de ui/main_window.py por el mismo motivo que
ui.playback_controller.PlaybackController — ver el docstring de ese
módulo. Igual que allí, el estado y los widgets siguen viviendo en
MainWindow (self.win); este módulo agrupa el comportamiento de
"cromado de ventana", que antes vivía mezclado con reproducción, listas
de canales y el resto de secciones dentro de una única clase de más de
2.000 líneas.

Nota sobre eventFilter: Qt exige que el objeto pasado a
installEventFilter() sea el mismo objeto cuyo método eventFilter() se
invoca — por eso MainWindow conserva un eventFilter() propio (obligatorio,
no se puede mover), que delega aquí en event_filter().

Coder By X@R
"""
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QCursor, QGuiApplication

from ui import icons as app_icons
from ui import palette
from ui.nav_sections import NAV_TV
from ui.now_playing_bar_builder import DOCK_HEIGHT, update_now_playing_bar_compact
from ui.style import accent_shades

# Mínimos de la ventana normal: los fija MainWindow.__init__ y los restaura
# exit_pip_mode (ver allí el porqué de 860 × 580 y 330 px de contenido).
WINDOW_MIN_WIDTH = 860
WINDOW_MIN_HEIGHT = 580
CONTENT_MIN_WIDTH = 330


class WindowChrome:
    """Arrastre de ventana, maximizar/restaurar, fullscreen y PiP."""

    def __init__(self, window):
        self.win = window

    # ---------- Arrastre de la barra de título / fullscreen por doble clic ----------

    def event_filter(self, obj, event):
        win = self.win
        if obj is win.title_bar:
            # Los clics sobre el menú o sobre los botones los recibe cada uno
            # de esos widgets, así que aquí solo llegan los de la zona vacía:
            # exactamente donde tiene sentido arrastrar la ventana.
            if event.type() == QEvent.MouseButtonDblClick and event.button() == Qt.LeftButton:
                self.toggle_maximize()
                return True
            return self._handle_drag_event(event)
        elif obj is win.player_frame:
            if event.type() == QEvent.MouseButtonDblClick and event.button() == Qt.LeftButton:
                self.toggle_player_fullscreen()
                return True
        elif obj is win.library_sidebar:
            # Fondo vacío del sidebar de biblioteca (Recientes/Playlists):
            # arrastra la ventana igual que la barra de título. Pensado
            # para cuando este panel está abierto y ocupa buena parte de
            # la altura de la ventana -- sin esto, la única zona de
            # arrastre seguía siendo la franja fina de arriba del todo.
            return self._handle_drag_event(event)
        elif obj is win.library_sidebar.recent_list.viewport():
            return self._drag_from_list_background(win.library_sidebar.recent_list, event)
        elif obj is win.library_sidebar.playlists_list.viewport():
            return self._drag_from_list_background(win.library_sidebar.playlists_list, event)
        return None

    def _handle_drag_event(self, event):
        """
        Arrastre de ventana genérico a partir de un evento de ratón, sin el
        doble clic de maximizar (eso solo tiene sentido en la barra de
        título de verdad) -- extraído de la barra de título para
        reutilizarlo también en el fondo del sidebar de biblioteca (ver
        event_filter() y _drag_from_list_background()).

        Antes esto reposicionaba la ventana a mano en cada MouseMove
        (win.move() + win.repaint()). Con ventana sin marco +
        WA_TranslucentBackground + el HWND nativo de vídeo de libVLC
        embebido dentro, ese arrastre "a pulso" competía con cómo DWM
        compone la ventana en Windows: durante un arrastre rápido, distintas
        zonas (controles, sidebar, vídeo) podían recomponerse en instantes
        ligeramente distintos y quedar mezcladas -- huecos vacíos o
        contenido "fantasma" de la posición anterior, como se ve en la
        captura que reportó Xor. Pedirle a Qt/Windows que mueva la ventana
        con su propio bucle nativo (startSystemMove()) delega todo el
        arrastre al gestor de ventanas: es la misma ruta que usa cualquier
        ventana con barra de título nativa, así que compone exactamente
        igual de bien -- sin el tearing de ir empujando move() a mano.
        """
        win = self.win
        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
            if win._pseudo_maximizado:
                # Arrastrar una ventana maximizada la restaura y la
                # "engancha" al cursor, como en cualquier app de Windows --
                # ahora se calcula una sola vez al pulsar, no en cada
                # MouseMove, porque el resto del arrastre lo lleva el SO.
                cursor = event.globalPosition().toPoint()
                ancho_previo = win.width()
                proporcion = cursor.x() / max(1, ancho_previo)
                self.restaurar_tamano()
                win.move(cursor.x() - int(win.width() * proporcion), win.y())
            handle = win.windowHandle()
            if handle is not None:
                handle.startSystemMove()
            return True
        return None

    def _drag_from_list_background(self, list_widget, event):
        """
        Igual que _handle_drag_event, pero solo cuando el clic cae en el
        hueco vacío de un QListWidget (sin ningún elemento bajo el
        cursor) -- así "Recientes"/"Playlists" siguen funcionando con
        normalidad (clic, selección) y solo el espacio en blanco de
        debajo de las entradas sirve para arrastrar la ventana.
        """
        if (
            event.type() == QEvent.MouseButtonPress
            and list_widget.itemAt(event.position().toPoint()) is not None
        ):
            return None  # clic sobre una entrada real: comportamiento normal
        return self._handle_drag_event(event)

    # ---------- Maximizar / restaurar ----------

    def toggle_maximize(self):
        if self.win._pseudo_maximizado:
            self.restaurar_tamano()
        else:
            self.maximizar()

    def maximizar(self):
        win = self.win
        pantalla = win.screen() or QGuiApplication.primaryScreen()
        if pantalla is None:
            return
        win._geometria_normal = win.geometry()
        win._pseudo_maximizado = True
        # availableGeometry() excluye la barra de tareas; geometry() no.
        win.setGeometry(pantalla.availableGeometry())
        win._maximize_btn.setText("❐")
        win._maximize_btn.setToolTip("Restaurar")

    def restaurar_tamano(self):
        win = self.win
        win._pseudo_maximizado = False
        if win._geometria_normal is not None:
            win.setGeometry(win._geometria_normal)
        win._maximize_btn.setText("□")
        win._maximize_btn.setToolTip("Maximizar")

    # ---------- Pantalla completa del reproductor ----------

    def toggle_player_fullscreen(self):
        win = self.win
        if win._pip_mode:
            self.exit_pip_mode()
        if win._player_fullscreen:
            self.exit_player_fullscreen()
        else:
            self.enter_player_fullscreen()

    def salir_fullscreen_si_activo(self):
        win = self.win
        if win._player_fullscreen:
            self.exit_player_fullscreen()
        elif win._pip_mode:
            self.exit_pip_mode()

    def enter_player_fullscreen(self):
        win = self.win
        win._player_fullscreen = True
        win._was_maximized_before_fs = win._pseudo_maximizado
        # Sin reproducción el panel de vídeo está plegado; la pantalla
        # completa lo necesita (con el flag ya puesto: no cuenta como
        # tamaño elegido por el usuario).
        win.set_player_panel_collapsed(False)

        win.nav_rail.setVisible(False)
        win.top_bar.setVisible(False)
        win.content_widget.setVisible(False)
        win.library_sidebar.setVisible(False)
        win.groups_sidebar.setVisible(False)
        win.title_bar.setVisible(False)
        win.statusBar().setVisible(False)
        win.fullscreen_btn.setIcon(app_icons.icon_fullscreen(palette.TEXT_PRIMARY, size=18, close=True))
        win.fullscreen_btn.setToolTip("Salir de pantalla completa (Esc)")
        win.fullscreen_btn.setAccessibleName("Salir de pantalla completa")
        win.fullscreen_btn.setToolTip("Salir de pantalla completa (Esc)")
        win.showFullScreen()

        if win.settings.get("fullscreen_autohide_ui", True):
            # Se ve un momento al entrar (como YouTube/VLC) y luego se
            # oculta sola -- ver show_fullscreen_overlay/
            # check_fullscreen_mouse_activity para el resto del ciclo.
            win._fs_last_cursor_pos = QCursor.pos()
            win._fs_mouse_poll_timer.start()
            self.show_fullscreen_overlay()

    def exit_player_fullscreen(self):
        win = self.win
        win._player_fullscreen = False

        win._fs_mouse_poll_timer.stop()
        win._fs_overlay_hide_timer.stop()
        # Fuera de pantalla completa, cabecera y controles se ven siempre,
        # sin importar el ajuste de auto-ocultado.
        win.player_header_bar.setVisible(True)
        win.now_playing_bar.setVisible(True)

        win.nav_rail.setVisible(True)
        win.top_bar.setVisible(True)
        win.content_widget.setVisible(True)
        # Respeta la preferencia del usuario (botón de biblioteca de la
        # barra de navegación)
        # en vez de forzarlo visible: si lo había ocultado antes de entrar
        # en pantalla completa, debe seguir oculto al salir.
        win.library_sidebar.setVisible(win.library_toggle_btn.isChecked())
        win.groups_sidebar.setVisible(win._current_nav_id == NAV_TV)
        win.title_bar.setVisible(True)
        win.statusBar().setVisible(True)

        win.fullscreen_btn.setIcon(app_icons.icon_fullscreen(palette.TEXT_PRIMARY, size=18))
        win.fullscreen_btn.setToolTip("Pantalla completa (F11)")
        win.fullscreen_btn.setAccessibleName("Pantalla completa")
        win.fullscreen_btn.setToolTip("Pantalla completa (F11)")

        win.showNormal()
        if win._was_maximized_before_fs:
            win._pseudo_maximizado = False  # forzar recálculo limpio
            self.maximizar()
        if not win.current_url:
            win.set_player_panel_collapsed(True)

    def show_fullscreen_overlay(self):
        """
        Muestra cabecera y controles sobre el vídeo en pantalla completa y
        reinicia la cuenta atrás para volver a ocultarlos. La llama
        enter_player_fullscreen() al entrar y check_fullscreen_mouse_activity()
        cada vez que detecta que el cursor se movió.
        """
        win = self.win
        win.player_header_bar.setVisible(True)
        win.now_playing_bar.setVisible(True)
        if win._player_fullscreen and win.settings.get("fullscreen_autohide_ui", True):
            win._fs_overlay_hide_timer.start()
        else:
            win._fs_overlay_hide_timer.stop()

    def hide_fullscreen_overlay(self):
        """Vuelve a ocultar cabecera/controles tras el aviso de inactividad."""
        win = self.win
        # El ajuste pudo desactivarse mientras el timer estaba en marcha
        # (Preferencias abierta encima de la pantalla completa).
        if win._player_fullscreen and win.settings.get("fullscreen_autohide_ui", True):
            win.player_header_bar.setVisible(False)
            win.now_playing_bar.setVisible(False)

    def check_fullscreen_mouse_activity(self):
        """
        Sondeo periódico de la posición global del cursor mientras se está
        en pantalla completa -- ver el comentario en
        ui.player_panel_builder.build_player_panel sobre por qué no basta
        con un eventFilter de Qt (el vídeo es una ventana nativa de libVLC
        embebida, ajena al bucle de eventos de Qt).
        """
        win = self.win
        pos = QCursor.pos()
        if pos != win._fs_last_cursor_pos:
            win._fs_last_cursor_pos = pos
            self.show_fullscreen_overlay()

    # ---------- Ventana flotante (picture-in-picture) ----------

    def toggle_pip_mode(self):
        win = self.win
        if win._player_fullscreen:
            # No tiene sentido combinar los dos modos a la vez; salir de
            # pantalla completa primero evita un estado confuso a medias.
            self.exit_player_fullscreen()
        if win._pip_mode:
            self.exit_pip_mode()
        else:
            self.enter_pip_mode()

    def enter_pip_mode(self):
        win = self.win
        win._pip_mode = True
        win._geometria_antes_pip = win.geometry()
        win._was_maximized_before_pip = win._pseudo_maximizado
        # Igual que en pantalla completa: el PiP es el panel de vídeo.
        win.set_player_panel_collapsed(False)

        win.nav_rail.setVisible(False)
        win.top_bar.setVisible(False)
        win.content_widget.setVisible(False)
        win.content_widget.setMinimumWidth(0)
        win.library_sidebar.setVisible(False)
        # groups_sidebar ("GRUPOS", panel de categorías de TV) vive como
        # hermano de content_widget en el mismo QHBoxLayout raíz -- no es
        # parte de content_widget, así que ocultar solo ese no bastaba: si
        # el usuario entraba en PiP estando en la pestaña de TV, el panel
        # de grupos se quedaba a ancho completo y aplastaba el vídeo/los
        # controles contra el borde de la ventana flotante (se veían
        # cortados, reportado con captura). Se guarda su visibilidad para
        # devolverla tal cual al salir.
        win._groups_sidebar_visible_before_pip = win.groups_sidebar.isVisible()
        win.groups_sidebar.setVisible(False)
        # win.nav_rail y win.top_bar ya se ocultan más arriba en este mismo
        # método, y con ellos la búsqueda global y "Más ▾" (ver
        # ui.more_menu) -- no hace falta ocultarlos aparte.
        win.statusBar().setVisible(False)
        # El PiP funciona como mini reproductor: esconde favorito y Cast,
        # pero conserva lo esencial (DESIGN.md, "Essential Controls
        # Survive"): reproducir, detener, grabar, volumen y "Más opciones".
        # El resto del encogido lo hace update_now_playing_bar_compact con
        # el ancho de 460 px. En Free win.cast_btn es None (ver
        # ui.now_playing_bar_builder.build_now_playing_bar).
        win._pip_compact_visibility = {
            widget: widget.isVisible() for widget in (win.fav_btn, win.cast_btn)
            if widget is not None
        }
        for widget in win._pip_compact_visibility:
            widget.setVisible(False)
        win.now_playing_bar.setFixedHeight(DOCK_HEIGHT)
        # El setMinimumSize(860, 580) del arranque impediría encoger la
        # ventana a un tamaño de ventana flotante — se relaja mientras
        # dure el modo PiP y se restaura al salir.
        win.setMinimumSize(320, 240)

        win.pip_btn.setIcon(app_icons.icon_pip(
            accent_shades(win.settings.get("accent_color", palette.ACCENT))["lighter"]
        ))
        # Salida visible del PiP: el dock compacto lo mantiene a la vista
        # mientras dure el modo (ver update_now_playing_bar_compact).
        win.pip_btn.setToolTip("Salir de ventana flotante")
        win.pip_btn.setAccessibleName("Salir de ventana flotante")

        win.setWindowFlag(Qt.WindowStaysOnTopHint, True)
        win.resize(460, 340)
        pantalla = (win.screen() or QGuiApplication.primaryScreen()).availableGeometry()
        win.move(pantalla.right() - 480, pantalla.bottom() - 360)
        win.show()  # obligatorio tras cambiar setWindowFlag en una ventana visible

    def exit_pip_mode(self):
        win = self.win
        win._pip_mode = False

        win.nav_rail.setVisible(True)
        win.top_bar.setVisible(True)
        win.content_widget.setVisible(True)
        win.content_widget.setMinimumWidth(CONTENT_MIN_WIDTH)
        win.library_sidebar.setVisible(win.library_toggle_btn.isChecked())
        win.groups_sidebar.setVisible(getattr(win, "_groups_sidebar_visible_before_pip", False))
        win.statusBar().setVisible(True)
        for widget, was_visible in getattr(win, "_pip_compact_visibility", {}).items():
            widget.setVisible(was_visible)
        win._pip_compact_visibility = {}
        win.now_playing_bar.setFixedHeight(DOCK_HEIGHT)
        # Los mismos mínimos que fija MainWindow.__init__ (antes 900 y 420:
        # tras un PiP la ventana ya no bajaba a 860).
        win.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

        win.pip_btn.setIcon(app_icons.icon_pip(palette.TEXT_PRIMARY))
        win.pip_btn.setToolTip("Ventana flotante")
        win.pip_btn.setAccessibleName("Abrir ventana flotante")

        win.setWindowFlag(Qt.WindowStaysOnTopHint, False)
        win.show()
        if not win.current_url:
            win.set_player_panel_collapsed(True)
        if win._geometria_antes_pip is not None:
            win.setGeometry(win._geometria_antes_pip)
        if win._was_maximized_before_pip:
            win._pseudo_maximizado = False
            self.maximizar()
        # Sin _pip_mode el botón de PiP vuelve a la regla normal del dock
        # aunque la geometría restaurada no cambie de ancho.
        update_now_playing_bar_compact(win, win.now_playing_bar.width())
