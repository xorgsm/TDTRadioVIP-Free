"""
Pruebas de "Añadir lista pública de TV…" (AddPublicTvListDialog +
LibraryController.open_add_public_tv_list_dialog) -- ver
ui/dialogs.py y ui/library_controller.py.
"""
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication, QDialog

from core import channels as tv_channels
from ui.dialogs import AddPublicTvListDialog
from ui.library_controller import LibraryController


def _app():
    return QApplication.instance() or QApplication([])


def test_dialog_defaults_to_spain_and_exposes_selection():
    _app()
    dialog = AddPublicTvListDialog()
    assert dialog.selected_country_code() == "ES"
    assert dialog.selected_country_name()

    idx = dialog.country_combo.findData("FR")
    assert idx >= 0
    dialog.country_combo.setCurrentIndex(idx)
    assert dialog.selected_country_code() == "FR"


def test_open_add_public_tv_list_dialog_fetches_playlist_url_for_chosen_country(monkeypatch):
    """
    Al aceptar el diálogo con un país elegido, debe lanzarse un FetchWorker
    sobre exactamente tv_channels.playlist_url_for(código) -- el mismo
    origen que usa el catálogo por defecto para ese país -- sin que el
    usuario haya escrito ninguna URL, y el resultado debe entrar por el
    mismo callback que usa la importación M3U normal (_on_playlist_fetched
    con entry_type="tv").
    """
    _app()

    class _FakeDialog:
        def __init__(self, parent=None):
            pass

        def exec(self):
            return QDialog.Accepted

        def selected_country_code(self):
            return "FR"

        def selected_country_name(self):
            return "Francia"

    monkeypatch.setattr("ui.library_controller.AddPublicTvListDialog", _FakeDialog)

    started_workers = []

    class _FakeWorker:
        def __init__(self, fn, *args):
            self.fn = fn
            self.args = args
            self.done = SimpleNamespace(connect=lambda cb: started_workers.append((fn, args, cb)))

        def start(self):
            pass

    monkeypatch.setattr("ui.library_controller.FetchWorker", _FakeWorker)

    win = SimpleNamespace(statusBar=lambda: SimpleNamespace(showMessage=lambda *a, **k: None))
    controller = LibraryController(win)

    controller.open_add_public_tv_list_dialog()

    assert len(started_workers) == 1
    fn, args, _cb = started_workers[0]
    assert fn is LibraryController._fetch_and_parse_playlist
    assert args == (tv_channels.playlist_url_for("FR"),)
    assert win._import_worker is not None
