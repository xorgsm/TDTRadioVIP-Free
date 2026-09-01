"""
Controlador del menú contextual de canales/emisoras de TDT & Radio VIP:
reproducir, añadir a la cola, marcar favorito, mover a carpeta, ocultar un
canal público, y el borrado de grupos completos desde GroupsSidebar.

Extraído de ui/main_window.py por el mismo motivo que
ui.playback_controller.PlaybackController y el resto de controladores —
ver el docstring de PlaybackController para la explicación completa del
porqué del patrón (estado en MainWindow, comportamiento aquí).

Coder By X@R
"""
from PySide6.QtWidgets import QInputDialog, QListWidget, QMenu, QMessageBox

from core import channels as tv_channels
from core import favorites as fav_store
from ui import icons as app_icons
from ui import palette
from ui.widgets import ROLE_CUSTOM, ROLE_DATA


class ChannelMenuController:
    """Menú contextual de listas de canales/emisoras y borrado de grupos."""

    def __init__(self, window):
        self.win = window

    def show_context_menu(self, pos, list_widget: QListWidget):
        win = self.win
        item = list_widget.itemAt(pos)
        if not item:
            return
        data = item.data(ROLE_DATA) or {}
        if not data.get("name"):
            return
        is_custom = bool(item.data(ROLE_CUSTOM))
        is_fav = fav_store.is_favorite(win.favorites, data.get("type"), data.get("name"))

        menu = QMenu(win)
        play_action = menu.addAction("▶ Reproducir")
        queue_action = menu.addAction("Añadir a la cola")
        fav_action = menu.addAction("★ Quitar de favoritos" if is_fav else "☆ Añadir a favoritos")
        folder_action = None
        if is_fav:
            folder_action = menu.addAction("Mover a carpeta…")
        # Los canales públicos no se borran de la fuente externa: se ocultan
        # para este perfil. La acción solo se muestra en la lista de TV;
        # los elementos personalizados conservan su eliminación real.
        hide_public_tv_action = None
        if list_widget is win.tv_list and not is_custom and data.get("type") == "tv":
            menu.addSeparator()
            hide_public_tv_action = menu.addAction("Ocultar este canal")

        edit_action = delete_action = None
        if is_custom:
            menu.addSeparator()
            edit_action = menu.addAction("Editar…")
            delete_action = menu.addAction("Eliminar")

        chosen = menu.exec(list_widget.viewport().mapToGlobal(pos))
        if chosen == play_action:
            win.playback.activate_item(item, list_widget, is_auto=False)
        elif chosen == queue_action:
            win.queue.add(data)
        elif chosen == fav_action:
            self._toggle_favorite_for(data)
        elif folder_action is not None and chosen == folder_action:
            self._mover_a_carpeta(data)
        elif hide_public_tv_action is not None and chosen == hide_public_tv_action:
            self._hide_public_tv_channel(data)
        elif edit_action is not None and chosen == edit_action:
            win.library.edit_custom_entry(data)
        elif delete_action is not None and chosen == delete_action:
            win.library.delete_custom_entry(data)

    def _hide_public_tv_channel(self, data: dict) -> None:
        """Oculta un canal público desde su menú contextual, de forma reversible."""
        win = self.win
        name = str(data.get("name") or "").strip()
        if not name:
            return
        if QMessageBox.question(
            win,
            "Ocultar canal",
            f"¿Ocultar solo «{name}» de tu lista de Television?\n\n"
            "El resto de los canales no se modifican. Podras restaurarlo desde "
            "Archivo > Gestionar canales personalizados > Ocultados.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        win.library.hide_entries("tv", [name])
        win.catalog.update_catalog_count()

    def delete_tv_groups(self, group_names: set) -> None:
        """
        Elimina de golpe todos los canales de uno o varios grupos, desde el
        menú contextual de GroupsSidebar (botón derecho).

        Un grupo puede mezclar canales de la lista PÚBLICA (iptv-org/URL de
        país) con canales PERSONALIZADOS (importados a mano) -- de hecho,
        con un catálogo grande a base de listas M3U importadas, casi todos
        los grupos son enteramente personalizados. Cada tipo necesita su
        propio mecanismo para que el borrado sea permanente de verdad:
          - Personalizados: library.hide_entries() los ocultaba por NOMBRE
            (tv_channels_hidden.json), pero ese filtro solo se aplica a la
            lista pública al recargar (ver CatalogLoadController) -- los
            personalizados se releen tal cual de tv_channels_custom.json
            sin pasar por el filtro de ocultos, así que "reaparecían" al
            reabrir la app (reportado por el usuario). Se borran de verdad
            con library._delete_custom_entries(), el mismo mecanismo que ya
            usa ManageChannelsDialog para borrado individual/por lotes.
          - Públicos: sí usan hide_entries()/hide_channels() como antes --
            no se pueden borrar de verdad porque la lista pública se vuelve
            a descargar entera en cada "Actualizar canales".
        """
        win = self.win
        custom_names = {c.name for c in tv_channels.load_custom_channels()}
        nombres = [c.name for c in win.tv_channels_data if c.group in group_names]
        if not nombres:
            return
        if len(group_names) == 1:
            etiqueta = f"el grupo «{next(iter(group_names))}»"
        else:
            listado = "».\n«".join(sorted(group_names))
            etiqueta = f"los {len(group_names)} grupos:\n«{listado}»"
        if QMessageBox.question(
            win,
            "Eliminar grupo",
            f"¿Eliminar {etiqueta} de tu lista de Televisión?\n\n"
            f"Se eliminarán {len(nombres)} canal(es). El resto de la lista no se "
            "modifica. Los personalizados se borran del todo; los de la lista "
            "pública podrás restaurarlos desde Archivo > Gestionar canales "
            "personalizados > Ocultados.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        personalizados = [n for n in nombres if n in custom_names]
        publicos = [n for n in nombres if n not in custom_names]
        if personalizados:
            win.library._delete_custom_entries("tv", personalizados)
        if publicos:
            win.library.hide_entries("tv", publicos)
        win.catalog.update_catalog_count()

    def _mover_a_carpeta(self, data: dict):
        win = self.win
        carpetas = fav_store.get_folders(win.favorites)
        opciones = ["(Sin carpeta)"] + carpetas + ["+ Nueva carpeta…"]
        carpeta_actual = next(
            (f.get("folder", "") for f in win.favorites
             if f.get("type") == data.get("type") and f.get("name") == data.get("name")),
            "",
        )
        idx_actual = opciones.index(carpeta_actual) if carpeta_actual in opciones else 0
        elegido, ok = QInputDialog.getItem(
            win, "Mover a carpeta",
            f"Carpeta para «{data.get('name', '')}»:",
            opciones, idx_actual, editable=False,
        )
        if not ok:
            return

        if elegido == "+ Nueva carpeta…":
            nombre, ok2 = QInputDialog.getText(win, "Nueva carpeta", "Nombre de la carpeta:")
            if not ok2 or not nombre.strip():
                return
            nueva_carpeta = nombre.strip()
        elif elegido == "(Sin carpeta)":
            nueva_carpeta = ""
        else:
            nueva_carpeta = elegido

        win.favorites = fav_store.set_favorite_folder(data["type"], data["name"], nueva_carpeta)
        win.lists.refresh_favorites_tab()
        if win.stack.currentWidget() is win.fav_list:
            win.lists.refresh_folder_filter()

    def _toggle_favorite_for(self, data: dict):
        win = self.win
        win.favorites = fav_store.toggle_favorite(
            data.get("type"), data.get("name"), data.get("url", ""), data.get("logo", "")
        )
        win.lists.refresh_favorites_tab()
        win.lists.mark_favorites_everywhere()
        if win.current_type == data.get("type") and win.current_name == data.get("name"):
            win.fav_btn.setChecked(fav_store.is_favorite(win.favorites, data.get("type"), data.get("name")))
            win.fav_btn.setIcon(
                app_icons.icon_favorite(
                    palette.ACCENT, size=18, filled=win.fav_btn.isChecked()
                )
            )
