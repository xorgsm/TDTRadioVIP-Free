"""
Dialogos de la aplicacion.

Este paquete sustituye al antiguo modulo unico ui/dialogs.py (1300 lineas,
por encima del limite de 800 del proyecto). Cada dialogo vive ahora en su
propio modulo; los imports existentes `from ui.dialogs import X` siguen
funcionando sin cambios gracias a estas reexportaciones.
"""
from ui.dialogs.recordings_library import RecordingsLibraryDialog
from ui.dialogs.settings import SettingsDialog
from ui.dialogs.add_entry import AddEntryDialog
from ui.dialogs.import_playlist import ImportPlaylistDialog
from ui.dialogs.m3u_editor import M3UEditorDialog
from ui.dialogs.export_playlist import ExportPlaylistDialog
from ui.dialogs.manage_channels import ManageChannelsDialog

__all__ = [
    "AddEntryDialog",
    "ExportPlaylistDialog",
    "ImportPlaylistDialog",
    "M3UEditorDialog",
    "ManageChannelsDialog",
    "RecordingsLibraryDialog",
    "SettingsDialog",
]
