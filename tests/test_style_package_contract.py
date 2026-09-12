"""
Contrato del paquete `ui.style`.

`ui/style.py` era un módulo único de 1293 líneas (utilidades de color, una
plantilla QSS enorme y el compositor `build_style`) y pasó a ser el paquete
`ui/style/`. Estos tests fijan la API pública y las invariantes del tema,
porque una regresión aquí no rompe ningún import: simplemente la aplicación
se ve mal, que es mucho más difícil de detectar.
"""
from pathlib import Path

import pytest

import ui.style as style
from ui.style import ACCENT_PRESETS, DEFAULT_ACCENT, accent_shades, build_style

LIMITE_LINEAS = 800  # límite de tamaño de archivo del proyecto (AGENTS.md)

API_PUBLICA = [
    "ACCENT_PRESETS",
    "DARK_STYLE",
    "DEFAULT_ACCENT",
    "LIGHT_THEME_COLORS",
    "accent_shades",
    "build_style",
    "normalize_accent",
]


@pytest.mark.parametrize("nombre", API_PUBLICA)
def test_api_publica_reexportada(nombre):
    """`from ui.style import X` sigue resolviendo tras el split en paquete."""
    assert hasattr(style, nombre), f"ui.style ya no exporta {nombre}"


def test_all_coincide_con_la_api_publica():
    assert sorted(style.__all__) == sorted(API_PUBLICA)


def test_ningun_modulo_de_style_supera_el_limite_de_lineas():
    """El motivo del split: ningún módulo debe volver a crecer sin control."""
    paquete = Path(style.__file__).parent
    excedidos = {
        ruta.name: n
        for ruta in paquete.glob("*.py")
        if (n := len(ruta.read_text(encoding="utf-8").splitlines())) > LIMITE_LINEAS
    }
    assert not excedidos, f"módulos por encima de {LIMITE_LINEAS} líneas: {excedidos}"


@pytest.mark.parametrize("theme", ["dark", "light"])
@pytest.mark.parametrize("acento", sorted(ACCENT_PRESETS.values()))
def test_build_style_genera_qss_para_cada_acento_y_tema(acento, theme):
    """El compositor sigue produciendo una hoja completa en las 12 combinaciones."""
    qss = build_style(acento, theme)
    assert isinstance(qss, str)
    assert len(qss) > 10_000, "la hoja de estilos salió sospechosamente corta"
    # Sin marcadores de f-string sin resolver ni llaves huérfanas del split.
    assert "{{" not in qss and "}}" not in qss
    assert "None" not in qss, "algún token de color se resolvió a None"


def test_build_style_es_determinista():
    """Mismo acento y tema -> misma hoja, byte a byte."""
    assert build_style(DEFAULT_ACCENT, "dark") == build_style(DEFAULT_ACCENT, "dark")


def test_dark_y_light_difieren():
    """Los dos temas no pueden colapsar en la misma hoja."""
    assert build_style(DEFAULT_ACCENT, "dark") != build_style(DEFAULT_ACCENT, "light")


@pytest.mark.parametrize("acento", sorted(ACCENT_PRESETS.values()))
def test_accent_shades_devuelve_colores_validos(acento):
    """Los tonos derivados siguen siendo hex de 6 dígitos."""
    shades = accent_shades(acento)
    assert shades, "accent_shades devolvió un diccionario vacío"
    for clave, valor in shades.items():
        assert isinstance(valor, str), f"{clave} no es una cadena"
        assert valor.startswith("#") and len(valor) == 7, f"{clave} = {valor!r} no es hex"
        int(valor[1:], 16)  # lanza ValueError si no es hexadecimal
