"""Comprobaciones estáticas de TDTRadioVIP_Setup.iss.

El instalador corre elevado (PrivilegesRequired por defecto = admin), así
que todo lo que ejecute hereda privilegios de administrador.
"""
import re
from pathlib import Path

import pytest

ISS = Path(__file__).resolve().parent.parent / "TDTRadioVIP_Setup.iss"

# El repo de la edición Free no lleva el .iss (ver RELEASE.md).
pytestmark = pytest.mark.skipif(not ISS.exists(), reason="sin TDTRadioVIP_Setup.iss")


def test_old_install_search_ignores_hkcu():
    """HKCU lo puede escribir cualquier proceso sin elevar: un
    UninstallString plantado ahí se ejecutaría como administrador al
    aceptar "desinstalar versiones anteriores"."""
    texto = ISS.read_text(encoding="utf-8-sig")
    assert not re.search(r"^\s*FindOldInstalls\(\s*HKCU", texto, re.MULTILINE)
