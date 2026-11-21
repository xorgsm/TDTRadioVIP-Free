"""Contraste WCAG AA de los tonos de texto y de los bloques de color."""
import re

import pytest

from core.config import _migrate_legacy_accent, DEFAULT_SETTINGS
from ui import palette
from ui.style import build_style
from ui.style.builder import SECTION_IDENTS
from ui.style.colors import _contrast_ratio, ACCENT_PRESETS, accent_shades, readable_on_surface

SURFACES = ("BG_ROOT", "BG_PANEL", "BG_CARD", "BG_PANEL_ALT", "BG_HOVER")
TEXTS = ("TEXT_PRIMARY", "TEXT_SECONDARY", "TEXT_MUTED", "TEXT_DIM")
# Tonos que también se usan como texto sobre las superficies.
FUNCTION_TONES = (
    "DANGER", "SUCCESS", "ACCENT_TV", "ACCENT_RADIO",
    "ACCENT_CAST", "ACCENT_SLEEP", "ACCENT_LIST",
)
SECTION_ACCENTS = (
    "ACCENT_HOME", "ACCENT_TV", "ACCENT_RADIO", "ACCENT_GUIDE",
    "ACCENT_LIST", "ACCENT_RECORD", "ACCENT_DOWNLOAD", "ACCENT_TOOLS",
)
BLOCKS = (
    palette.ACCENT_HOME, palette.ACCENT_TV, palette.ACCENT_RADIO,
    palette.ACCENT_GUIDE, palette.ACCENT_LIST, palette.ACCENT_RECORD,
    palette.ACCENT_DOWNLOAD, palette.ACCENT_TOOLS,
    palette.DANGER, palette.ACCENT_CAST,
)


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_section_idents_are_distinct_in_both_themes(theme):
    tones = [palette.tone(name, theme) for name in SECTION_ACCENTS]
    assert len(set(tones)) == len(SECTION_ACCENTS) == 8


def test_new_ident_blocks_take_ink_text_at_aa():
    """El bloque de color es el mismo vivo en ambos temas; la tinta es fija."""
    for name in SECTION_ACCENTS:
        assert _contrast_ratio(palette.INK, palette.tone(name, "dark")) >= 4.5, name


@pytest.mark.parametrize("name", SECTION_ACCENTS)
def test_section_idents_read_as_text_on_the_light_panel(name):
    assert _contrast_ratio(palette.tone(name, "light"), palette.tone("BG_PANEL", "light")) >= 4.5


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("surface", SURFACES)
@pytest.mark.parametrize("text", TEXTS)
def test_text_tones_pass_aa_on_every_surface(theme, surface, text):
    assert _contrast_ratio(palette.tone(text, theme), palette.tone(surface, theme)) >= 4.5


@pytest.mark.parametrize("name", FUNCTION_TONES)
def test_function_tones_read_as_text_in_the_light_theme(name):
    assert _contrast_ratio(palette.tone(name, "light"), palette.tone("BG_ROOT", "light")) >= 4.5


def test_apply_theme_rewrites_the_palette_and_can_go_back():
    dark_root = palette.BG_ROOT
    try:
        palette.apply_theme("light")
        assert palette.BG_ROOT == palette.tone("BG_ROOT", "light")
        assert palette.INK == "#12110e"
    finally:
        palette.apply_theme("dark")
    assert palette.BG_ROOT == dark_root


def test_style_does_not_depend_on_the_active_theme():
    dark = build_style(theme="dark")
    try:
        palette.apply_theme("light")
        assert build_style(theme="dark") == dark
    finally:
        palette.apply_theme("dark")


@pytest.mark.parametrize("color", sorted(SECTION_IDENTS.values()))
def test_section_icons_stay_visible_on_the_light_panel(color):
    try:
        palette.apply_theme("light")
        assert _contrast_ratio(readable_on_surface(color), palette.BG_PANEL) >= 3.0
    finally:
        palette.apply_theme("dark")


def test_section_icons_keep_their_color_in_the_dark_theme():
    for color in SECTION_IDENTS.values():
        assert readable_on_surface(color) == color


@pytest.mark.parametrize("block", BLOCKS)
def test_ink_is_readable_on_every_color_block(block):
    assert _contrast_ratio(palette.INK, block) >= 4.5


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_every_ink_rule_of_the_built_style_passes_aa(theme):
    """Sobre el estilo final: el tema claro sustituye muchos tonos."""
    rules = re.findall(r"\{[^}]*\}", build_style(theme=theme))
    pairs = 0
    for rule in rules:
        background = re.search(r"background-color: (#[0-9a-f]{6});", rule)
        if background and re.search(rf"(?<![-w])color: {palette.INK};", rule):
            pairs += 1
            assert _contrast_ratio(palette.INK, background.group(1)) >= 4.5, rule
    assert pairs >= 10


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("state", ["tv", "radio", "error"])
def test_rotulo_blocks_keep_their_vivid_color_in_both_themes(theme, state):
    rule = re.search(
        rf'QFrame#nowRotulo\[uiState="{state}"\] \{{ background-color: (#[0-9a-f]{{6}})',
        build_style(theme=theme),
    )
    assert _contrast_ratio(palette.INK, rule.group(1)) >= 4.5


@pytest.mark.parametrize("accent", sorted(ACCENT_PRESETS.values()))
def test_text_on_every_accent_preset_passes_aa(accent):
    shades = accent_shades(accent)
    assert _contrast_ratio(shades["on_accent"], shades["base"]) >= 4.5


@pytest.mark.parametrize("accent", sorted(ACCENT_PRESETS.values()))
def test_accent_as_text_passes_large_text_contrast_in_the_light_theme(accent):
    shades = accent_shades(accent, "light")
    assert _contrast_ratio(shades["text"], palette.tone("BG_ROOT", "light")) >= 3.0


def _rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


@pytest.mark.parametrize("name", ["EPG_NOW_BG", "EPG_CELL_BG"])
def test_leftover_dark_tones_belong_to_the_warm_ink_family(name):
    """Restos de la paleta ciruela: en el negro cálido el azul nunca domina."""
    red, _green, blue = _rgb(palette.tone(name, "dark"))
    assert blue <= red, name


def test_video_black_stays_pinned_by_design():
    """DESIGN.md fija video-black en #08060c: el marco del vídeo nunca se tiñe."""
    assert palette.VIDEO_BLACK == "#08060c"


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("cell", ["EPG_NOW_BG", "EPG_CELL_BG"])
def test_epg_cell_text_passes_aa(theme, cell):
    assert _contrast_ratio(palette.tone("EPG_CELL_TEXT", theme), palette.tone(cell, theme)) >= 4.5


def test_light_wash_is_warm_ink():
    style = build_style(theme="light")
    assert "rgba(26, 21, 38" not in style
    assert "rgba(18, 17, 14, 12)" in style


def test_previous_default_accent_moves_to_the_new_default():
    settings = {"accent_color": "#7C6CFF"}
    _migrate_legacy_accent(settings)
    assert settings["accent_color"] == DEFAULT_SETTINGS["accent_color"]


def test_hand_picked_accent_is_respected():
    settings = {"accent_color": "#123456"}
    _migrate_legacy_accent(settings)
    assert settings["accent_color"] == "#123456"
