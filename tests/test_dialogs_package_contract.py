"""
Contrato del paquete `ui.dialogs`.

`ui/dialogs.py` era un módulo único de 1300 líneas y pasó a ser el paquete
`ui/dialogs/`, un módulo por diálogo. Todo el código existente importa con
`from ui.dialogs import X`, así que esa forma debe seguir funcionando: estos
tests fijan esa API para que una futura reorganización no la rompa en
silencio (el fallo se vería sólo al abrir el diálogo en tiempo de ejecución).
"""
import importlib
import importlib.util
import inspect
from pathlib import Path

import pytest
from PySide6.QtWidgets import QDialog

import ui.dialogs as dialogs


DIALOGOS_ESPERADOS = {
    "AddEntryDialog": "add_entry",
    "AddPublicTvListDialog": "add_public_tv_list",
    "ExportPlaylistDialog": "export_playlist",
    "ImportPlaylistDialog": "import_playlist",
    "M3UEditorDialog": "m3u_editor",
    "ManageChannelsDialog": "manage_channels",
    "RecordingsLibraryDialog": "recordings_library",
    "SettingsDialog": "settings",
}
# Diálogos de VPN: solo en la edición con licencia (el repo público Free no
# trae sus módulos), así que el contrato los exige solo cuando existen.
if importlib.util.find_spec("ui.dialogs.vpn_dialog") is not None:
    DIALOGOS_ESPERADOS.update({
        "VpnDialog": "vpn_dialog",
        "VpnGatePickerDialog": "vpngate_picker",
    })

LIMITE_LINEAS = 800  # límite de tamaño de archivo del proyecto (AGENTS.md)


@pytest.mark.parametrize("nombre", sorted(DIALOGOS_ESPERADOS))
def test_dialogo_reexportado_en_el_paquete(nombre):
    """`from ui.dialogs import X` sigue resolviendo para los siete diálogos."""
    clase = getattr(dialogs, nombre, None)
    assert clase is not None, f"{nombre} ya no se reexporta desde ui.dialogs"
    assert inspect.isclass(clase)
    assert issubclass(clase, QDialog)


@pytest.mark.parametrize("nombre,modulo", sorted(DIALOGOS_ESPERADOS.items()))
def test_dialogo_vive_en_su_propio_modulo(nombre, modulo):
    """Cada diálogo se define en su módulo, no reagrupado en otro sitio."""
    mod = importlib.import_module(f"ui.dialogs.{modulo}")
    clase = getattr(mod, nombre, None)
    assert clase is not None, f"{nombre} no está en ui/dialogs/{modulo}.py"
    assert clase is getattr(dialogs, nombre), (
        f"ui.dialogs.{nombre} y ui.dialogs.{modulo}.{nombre} son objetos "
        "distintos: hay una definición duplicada"
    )


def test_all_declara_exactamente_los_dialogos_publicos():
    assert sorted(dialogs.__all__) == sorted(DIALOGOS_ESPERADOS)


def test_ningun_modulo_de_dialogos_supera_el_limite_de_lineas():
    """El motivo del split: ningún módulo debe volver a crecer sin control."""
    paquete = Path(dialogs.__file__).parent
    excedidos = {}
    for ruta in paquete.glob("*.py"):
        n = len(ruta.read_text(encoding="utf-8").splitlines())
        if n > LIMITE_LINEAS:
            excedidos[ruta.name] = n
    assert not excedidos, f"módulos por encima de {LIMITE_LINEAS} líneas: {excedidos}"


def test_helpers_compartidos_centralizados():
    """`_panel`/`_header` viven en _common y no se redefinen por módulo."""
    from ui.dialogs import _common

    assert callable(_common._panel)
    assert callable(_common._header)

    paquete = Path(dialogs.__file__).parent
    for ruta in paquete.glob("*.py"):
        if ruta.name == "_common.py":
            continue
        texto = ruta.read_text(encoding="utf-8")
        assert "def _panel(" not in texto, f"{ruta.name} redefine _panel"
        assert "def _header(" not in texto, f"{ruta.name} redefine _header"
