"""Tipografías empaquetadas (Figtree + Bricolage Grotesque) y tema Continuidad."""
import os
import re
import sys

import pytest
from PySide6.QtGui import QFontDatabase, QGuiApplication

from core.config import get_font_paths
from ui import palette
from ui.application import _register_app_font
from ui.nav_sections import SECTION_COLORS, SECTION_VARIANTS
from ui.style import build_style
from ui.style.builder import BODY_FONT, DISPLAY_FONT, SECTION_IDENTS
from ui.style.colors import accent_shades
from ui.visual import VALID_VARIANTS


@pytest.fixture(scope="module")
def qt_app():
    return QGuiApplication.instance() or QGuiApplication(sys.argv)


def test_get_font_paths_includes_body_and_display_fonts():
    names = {os.path.basename(p) for p in get_font_paths()}
    assert {"Figtree-Variable.ttf", "BricolageGrotesque-Variable.ttf"} <= names
    assert all(os.path.isfile(p) for p in get_font_paths())


def test_register_app_font_makes_both_families_available(qt_app):
    _register_app_font()
    families = set(QFontDatabase.families())
    assert "Figtree" in families
    assert "Bricolage Grotesque" in families


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_body_text_uses_figtree_with_safe_fallbacks(theme):
    assert f"font-family: {BODY_FONT};" in build_style("#c9a227", theme)


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_titles_use_the_display_font(theme):
    style = build_style("#c9a227", theme)
    block = re.findall(r"QLabel#sectionTitle,[^{]*\{[^}]*\}", style)[-1]
    assert DISPLAY_FONT in block
    assert "QLabel#homeGreeting" in block and "QLabel#titleBrand" in block


def test_standard_buttons_are_spanish_and_other_qt_texts_survive():
    from ui.application import _StandardButtonsTranslator

    translator = _StandardButtonsTranslator()
    assert translator.translate("QPlatformTheme", "Cancel") == "Cancelar"
    assert translator.translate("QPlatformTheme", "&Yes") == "Sí"
    # None deja que Qt use el original; "" lo borraría.
    assert translator.translate("QPlatformTheme", "Desconocido") is None
    assert translator.translate("QWidgetTextControl", "&Copy") is None


def test_app_font_is_rendered_without_hinting(qt_app):
    """Las fuentes variables pierden el ancho de los espacios en tamaños
    pequeños con el hinting por defecto: se desactiva al arrancar."""
    from PySide6.QtGui import QFont

    from ui.application import _apply_font_rendering

    _apply_font_rendering(qt_app)
    assert qt_app.font().hintingPreference() == QFont.PreferNoHinting


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_transport_buttons_keep_their_target_size(theme):
    style = build_style("#c9a227", theme)
    controls = re.findall(r"QPushButton#ctrlButton,[^{]*\{[^}]*\}", style)[0]
    assert "min-height: 34px;" in controls and "max-height: 34px;" in controls
    play = re.findall(r"QPushButton#playCircle \{[^}]*\}", style)[0]
    assert "min-height: 46px;" in play and "max-width: 46px;" in play


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_style_has_no_unresolved_tokens(theme):
    assert "$" not in build_style("#c9a227", theme)


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_each_section_tab_becomes_a_block_of_its_own_color(theme):
    style = build_style("#c9a227", theme)
    for variant, color in SECTION_IDENTS.items():
        rule = re.search(
            rf'QToolButton#navButton\[uiVariant="{variant}"\]:checked \{{[^}}]*\}}', style
        ).group(0)
        assert color in rule and palette.INK in rule


def test_section_variants_and_colors_match_the_style_idents():
    assert set(SECTION_VARIANTS.values()) == set(SECTION_IDENTS)
    # set_variant descarta en silencio las variantes que no conoce.
    assert set(SECTION_IDENTS) <= VALID_VARIANTS
    for nav_id, variant in SECTION_VARIANTS.items():
        assert SECTION_COLORS[nav_id] == SECTION_IDENTS[variant]


def test_primary_buttons_follow_the_chosen_accent():
    def primary(style):
        return re.findall(r'QPushButton\[uiVariant="primary"\], [^{]*\{[^}]*\}', style)[0]

    assert primary(build_style("#c9a227", "dark")) != primary(build_style("#4d94ff", "dark"))


def test_text_on_accent_stays_dark_in_the_light_theme():
    """Antes usaba BG_ROOT, que el tema claro convierte en un tono casi blanco."""
    assert accent_shades("#ffd02e", "light")["on_accent"] == palette.INK


def test_soft_accent_follows_the_theme_surface():
    assert accent_shades("#ff2d78", "dark")["soft"] != accent_shades("#ff2d78", "light")["soft"]


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_style_never_uses_gold_or_navy_from_the_previous_theme(theme):
    style = build_style(theme=theme).lower()
    for legacy in ("#e0bb4a", "#b3891c", "#c9a227", "#0b152b", "#7c6cff"):
        assert legacy not in style
