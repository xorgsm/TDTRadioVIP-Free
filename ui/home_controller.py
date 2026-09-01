"""
Controlador de la página de Inicio de TDT & Radio VIP: sincroniza la
tarjeta "reproduciendo ahora", puebla los carruseles de Recientes/
Recomendado para ti/Favoritos destacados, calcula las recomendaciones por
categoría y muestra el resumen de salud de streams.

Extraído de ui/main_window.py por el mismo motivo que
ui.playback_controller.PlaybackController y el resto de controladores —
ver el docstring de PlaybackController para la explicación completa del
porqué del patrón (estado en MainWindow, comportamiento aquí). La
construcción de la página (_build_home_page) sigue en MainWindow: este
controlador solo refresca/reacciona sobre los widgets ya construidos.

Coder By X@R
"""
from PySide6.QtWidgets import QBoxLayout, QListWidgetItem

from core import channels as tv_channels
from core import radio as radio_stations
from core.stream_health_store import list_health, summarize_health
from ui.visual import set_variant
from ui.widgets import ROLE_CUSTOM, ROLE_DATA, ROLE_FAV, ROLE_PLAYING


class HomeController:
    """Refresco y comportamiento de la página de Inicio."""

    def __init__(self, window):
        self.win = window

    def update_home_compact(self, width: int) -> None:
        win = self.win
        compact = width < 520
        direction = QBoxLayout.TopToBottom if compact else QBoxLayout.LeftToRight
        win._home_quick_layout.setDirection(direction)
        win._home_now_layout.setDirection(direction)
        win._home_health_layout.setDirection(direction)
        win._home_secondary_layout.setDirection(direction)
        win._home_layout.setContentsMargins(2, 4, 2 if compact else 20, 18)

    def home_resume_or_search(self):
        win = self.win
        if win.current_url:
            win.playback.toggle_play()
            self._refresh_home_now_playing()
        else:
            win._open_command_palette()

    def _refresh_home_now_playing(self):
        """Sincroniza la tarjeta de portada con el reproductor real."""
        win = self.win
        if not hasattr(win, "home_now_title"):
            return
        if not win.current_url:
            win.home_now_title.setText("Nada en reproducción")
            win.home_now_subtitle.setText("Busca cualquier canal o emisora con Ctrl+K")
            win.home_resume_btn.setText("Buscar")
            win.home_float_btn.setVisible(False)
            return
        kind = "TV en directo" if win.current_type == "tv" else "Radio online"
        win.home_now_title.setText(win.current_name or "Reproduciendo")
        win.home_now_subtitle.setText(kind)
        win.home_resume_btn.setText("Pausar" if win.player.is_playing() else "Continuar")
        win.home_float_btn.setVisible(True)

    def refresh_home_page(self):
        """Puebla los carruseles de 'Recientes' y 'Recomendado para ti', y la
        lista de favoritos destacados, con los mismos datos que ya usan sus
        propias pestañas — se llama cada vez que se entra en Inicio, para
        que nunca se quede desactualizada respecto a lo que se ha
        visto/marcado mientras tanto."""
        win = self.win
        custom_tv = {c.name for c in tv_channels.load_custom_channels()}
        self._refresh_home_now_playing()
        self.refresh_home_health()
        custom_radio = {s.name for s in radio_stations.load_custom_stations()}

        win.home_on_air_carousel.set_entries(win.epg.now_on_air_entries())
        win.home_recent_carousel.set_entries(win.history[:12])
        win.home_recommended_carousel.set_entries(self._compute_recommendations())

        win.home_fav_list.clear()
        destacados = win.favorites[:5]
        for fav in destacados:
            item = QListWidgetItem()
            data = dict(fav)
            data["group"] = fav.get("folder", "")
            item.setData(ROLE_DATA, data)
            item.setData(ROLE_FAV, True)
            item.setData(ROLE_PLAYING, win.current_type == fav["type"] and win.current_name == fav["name"])
            is_custom = fav["name"] in (custom_tv if fav["type"] == "tv" else custom_radio)
            item.setData(ROLE_CUSTOM, is_custom)
            win.home_fav_list.addItem(item)
            win.lists.request_logo(fav.get("logo", ""), item, win.home_fav_list)
        win.home_fav_list.setVisible(bool(destacados))
        win.home_fav_empty.setVisible(not destacados)

    def refresh_home_health(self):
        """Muestra un resumen claro de los últimos diagnósticos guardados."""
        win = self.win
        if not hasattr(win, "home_health_summary"):
            return
        health = summarize_health(list_health())
        if not health["total"]:
            win.home_health_summary.setText(
                "Aún no hay diagnósticos. La app revisa streams en segundo plano."
            )
            set_variant(win.home_health_summary, "secondary")
            return

        issues = health["slow"] + health["down"] + health["restricted"]
        win.home_health_summary.setText(
            f"{health['total']} revisados · {health['stable']} estables · "
            f"{health['slow']} lentos · {issues} con incidencia"
        )
        set_variant(win.home_health_summary, "success" if not issues else "danger")

    def activate_home_entry(self, entry: dict):
        """Reproduce una tarjeta de los carruseles de Inicio (Recientes o
        Recomendado para ti). Solo llama a play(): no depende de una fila
        de QListWidget como activate_item(), porque las tarjetas del
        carrusel no viven dentro de ninguna lista navegable."""
        self.win.playback.play(
            entry.get("type", "tv"), entry.get("name", ""), entry.get("url", ""),
            entry.get("tvg_id", ""), entry.get("logo", ""),
        )

    def _compute_recommendations(self, limit: int = 12) -> list:
        """
        Heurística de "Recomendado para ti" sin necesidad de trackear nada
        nuevo: el historial solo guarda una entrada por canal (la más
        reciente, ver core/history.add_entry), así que no hay forma de
        contar reproducciones -- en su lugar, se recomienda por categoría:
        canales de TV de las mismas categorías que ya has visto o
        marcado como favorito, que todavía no hayas visto ni marcado. Si
        no hay categorías en común todavía (usuario nuevo, o categorías no
        cargadas), se completa con canales de TV que aún no aparezcan ni
        en historial ni en favoritos, para que la sección no salga vacía
        salvo que de verdad no haya canales cargados.
        """
        win = self.win
        vistos_o_favoritos = {(e.get("type"), e.get("name")) for e in win.history}
        vistos_o_favoritos |= {(f.get("type"), f.get("name")) for f in win.favorites}

        categorias_interes = {
            ch.group for ch in win.tv_channels_data
            if ch.group and ("tv", ch.name) in vistos_o_favoritos
        }

        recomendaciones = []
        nombres_añadidos = set()

        if categorias_interes:
            for ch in win.tv_channels_data:
                if ("tv", ch.name) in vistos_o_favoritos or ch.name in nombres_añadidos:
                    continue
                if ch.group in categorias_interes:
                    recomendaciones.append({
                        "type": "tv", "name": ch.name, "url": ch.url,
                        "logo": ch.logo, "tvg_id": ch.tvg_id,
                    })
                    nombres_añadidos.add(ch.name)
                if len(recomendaciones) >= limit:
                    break

        if len(recomendaciones) < limit:
            for ch in win.tv_channels_data:
                if ("tv", ch.name) in vistos_o_favoritos or ch.name in nombres_añadidos:
                    continue
                recomendaciones.append({
                    "type": "tv", "name": ch.name, "url": ch.url,
                    "logo": ch.logo, "tvg_id": ch.tvg_id,
                })
                nombres_añadidos.add(ch.name)
                if len(recomendaciones) >= limit:
                    break

        return recomendaciones
