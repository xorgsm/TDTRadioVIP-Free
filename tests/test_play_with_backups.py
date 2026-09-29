"""
Accesos que reproducen o guardan un canal y tienen que llevar su tvg_id y
sus fuentes de respaldo: la estrella del menú contextual
(ChannelMenuController) y la búsqueda Ctrl+K (CommandPalette).

Sin tvg_id la TV salía sin "Ahora: ..." de la guía EPG, y sin respaldos un
corte no probaba las demás fuentes del canal.
"""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core.channels import Channel
from core.radio import Station
from ui import channel_menu_controller as menu_module
from ui.channel_menu_controller import ChannelMenuController
from ui.command_palette import CommandPalette

LA1 = Channel(name="La 1", url="https://stream.test/la1", logo="https://logo/la1",
              tvg_id="la1", alternate_urls=["https://respaldo/la1"])
RNE = Station(name="RNE", url="https://stream.test/rne", favicon="https://logo/rne",
              alternate_urls=["https://respaldo/rne"])


# --------------------------------------------------------------------------
# Menú contextual: añadir a favoritos
# --------------------------------------------------------------------------

def test_context_menu_favorite_saves_epg_id_and_backups(monkeypatch):
    fav_store = Mock(toggle_favorite=Mock(return_value=[]), is_favorite=Mock(return_value=False))
    monkeypatch.setattr(menu_module, "fav_store", fav_store)
    win = Mock(current_type=None, current_name=None)
    data = {"type": "tv", "name": "La 1", "url": LA1.url, "logo": LA1.logo,
            "tvg_id": "la1", "alternate_urls": ["https://respaldo/la1"]}

    ChannelMenuController(win)._toggle_favorite_for(data)

    fav_store.toggle_favorite.assert_called_once_with(
        "tv", "La 1", LA1.url, LA1.logo,
        tvg_id="la1", alternate_urls=["https://respaldo/la1"],
    )


# --------------------------------------------------------------------------
# Búsqueda Ctrl+K
# --------------------------------------------------------------------------

def _activate_result(kind, payload):
    palette = SimpleNamespace(close=Mock(), win=Mock())
    item = Mock(data=Mock(return_value=(kind, payload)))
    CommandPalette._activate_item(palette, item)
    return palette.win.playback.play


@pytest.mark.parametrize(("kind", "payload", "expected"), [
    ("tv", LA1, ("tv", "La 1", LA1.url, "la1", LA1.logo, ["https://respaldo/la1"])),
    ("radio", RNE, ("radio", "RNE", RNE.url, "", RNE.favicon, ["https://respaldo/rne"])),
    ("tv", {"name": "La 1", "url": LA1.url, "logo": LA1.logo, "tvg_id": "la1",
            "alternate_urls": ["https://respaldo/la1"]},
     ("tv", "La 1", LA1.url, "la1", LA1.logo, ["https://respaldo/la1"])),
    ("radio", {"name": "RNE", "url": RNE.url, "logo": RNE.favicon},
     ("radio", "RNE", RNE.url, "", RNE.favicon, [])),
])
def test_command_palette_plays_with_backups(kind, payload, expected):
    play = _activate_result(kind, payload)

    play.assert_called_once_with(*expected)
