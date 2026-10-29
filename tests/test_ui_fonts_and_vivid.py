"""Tipografías empaquetadas (Manrope + Playfair Display) y tema oscuro más vivo."""
import os
import re
import sys

import pytest
from PySide6.QtGui import QFontDatabase, QGuiApplication

from core.config import get_font_paths
from ui.application import _register_app_font
from ui.style import build_style


@pytest.fixture(scope="module")
def qt_app():
    return QGuiApplication.instance() or QGuiApplication(sys.argv)


def test_get_font_paths_includes_body_and_display_fonts():
    names = {os.path.basename(p) for p in get_font_paths()}
    assert {"Manrope-Variable.ttf", "PlayfairDisplay-Variable.ttf"} <= names
    assert all(os.path.isfile(p) for p in get_font_paths())


def test_register_app_font_makes_both_families_available(qt_app):
    _register_app_font()
    families = set(QFontDatabase.families())
    assert "Manrope" in families
    assert "Playfair Display" in families


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_body_text_uses_manrope_with_safe_fallbacks(theme):
    style = build_style("#c9a227", theme)
    assert "font-family: 'Manrope', 'Inter', 'Segoe UI', sans-serif;" in style


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_titles_use_playfair_display_serif(theme):
    style = build_style("#c9a227", theme)
    block = re.findall(r"QLabel#sectionTitle,[^{]*\{[^}]*\}", style)[-1]
    assert "'Playfair Display', 'Georgia', serif" in block
    assert "QLabel#homeGreeting" in block and "QLabel#titleBrand" in block


def test_dark_theme_has_tinted_gradient_background():
    style = build_style("#c9a227", "dark")
    assert "qlineargradient" in re.findall(r"QWidget#appSurface \{[^}]*\}", style)[-1]


def test_light_theme_keeps_light_backgrounds_without_dark_gradient():
    style = build_style("#c9a227", "light")
    assert "#120f2a" not in style.lower()


def test_gradients_follow_the_chosen_accent():
    violet = build_style("#a78bfa", "dark")
    gold = build_style("#c9a227", "dark")
    def nav_bar(style):
        return re.findall(r"QWidget#navTopBar \{[^}]*\}", style)[-1]

    assert nav_bar(violet) != nav_bar(gold)


def test_app_font_is_rendered_without_hinting(qt_app):
    """Manrope (variable) pierde el ancho de los espacios en tamaños pequeños
    con el hinting por defecto ("loqueestabas"): se desactiva al arrancar."""
    from PySide6.QtGui import QFont

    from ui.application import _apply_font_rendering

    _apply_font_rendering(qt_app)
    assert qt_app.font().hintingPreference() == QFont.PreferNoHinting


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_menus_and_dialogs_use_manrope(theme):
    style = build_style("#c9a227", theme)
    block = re.findall(r"QMenu,[^{]*\{[^}]*\}", style)[-1]
    assert "'Manrope', 'Inter', 'Segoe UI', sans-serif" in block
    assert "QMenu::item" in block and "QDialog QLabel" in block


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_option_buttons_are_bigger_than_the_base_style(theme):
    style = build_style("#c9a227", theme)
    controls = re.findall(r"QPushButton#ctrlButton,[^{]*\{[^}]*\}", style)[-1]
    assert "min-height: 34px;" in controls and "max-height: 34px;" in controls
    play = re.findall(r"QPushButton#playCircle \{[^}]*\}", style)[-1]
    assert "min-height: 46px;" in play and "max-width: 46px;" in play


def test_dark_theme_colors_sections_on_hover_and_primary_buttons():
    style = build_style("#c9a227", "dark")
    assert re.search(r'QToolButton#navButton\[uiVariant="[^"]+"\]:hover', style)
    assert re.search(r'QPushButton\[uiVariant="primary"\] \{[^}]*qlineargradient', style)
