"""
Comprobación manual de actualizaciones (Ayuda > Buscar actualizaciones,
ui/update_check_controller.py).

Lo principal: distinguir "ya tienes la versión más reciente" de "no se pudo
comprobar". Antes, sin conexión o con el servidor caído, el aviso decía que
ya estabas al día.

QMessageBox, FetchWorker y QDesktopServices se sustituyen en el módulo: no
se abre ningún diálogo ni hilo real.
"""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from core.updater import UP_TO_DATE
from ui import update_check_controller as ucc_module
from ui.update_check_controller import UpdateCheckController

NEWER = {"version": "8.7.0", "download_url": "https://updates.test/setup_v8.7.0.exe",
         "sha256": "a" * 64}


@pytest.fixture
def boxes(monkeypatch):
    box = Mock()
    box.Yes, box.No = "yes", "no"
    box.question.return_value = "no"
    monkeypatch.setattr(ucc_module, "QMessageBox", box)
    monkeypatch.setattr(ucc_module, "QDesktopServices", Mock())
    return box


@pytest.fixture
def workers(monkeypatch):
    creados = []

    def fake_worker(func, *args):
        worker = Mock(func=func, args=args)
        creados.append(worker)
        return worker

    monkeypatch.setattr(ucc_module, "FetchWorker", fake_worker)
    return creados


@pytest.fixture
def win():
    return Mock(_is_closing=False, settings={"update_check_url": "https://updates.test/m.json"})


def test_manual_check_uses_the_status_that_tells_failures_apart(win, boxes, workers):
    UpdateCheckController(win).check_for_update()

    (worker,) = workers
    assert worker.func is ucc_module.updater.check_update_status
    assert worker.args[0] == "https://updates.test/m.json"
    worker.start.assert_called_once()


def test_manual_check_without_url_only_informs(win, boxes, workers):
    win.settings = {}

    UpdateCheckController(win).check_for_update()

    assert workers == []
    boxes.information.assert_called_once()


def test_up_to_date_says_so(win, boxes):
    UpdateCheckController(win).on_update_check_done(UP_TO_DATE)

    boxes.information.assert_called_once()
    assert "más reciente" in boxes.information.call_args.args[2]
    boxes.warning.assert_not_called()


def test_failed_check_does_not_claim_you_are_up_to_date(win, boxes):
    UpdateCheckController(win).on_update_check_done(None)

    boxes.information.assert_not_called()
    boxes.warning.assert_called_once()
    assert "No se pudo comprobar" in boxes.warning.call_args.args[2]


def test_new_version_offers_the_verified_download(win, boxes, workers):
    boxes.question.return_value = "yes"

    UpdateCheckController(win).on_update_check_done(NEWER)

    assert "8.7.0" in boxes.question.call_args.args[2]
    (worker,) = workers
    assert worker.func is ucc_module.updater.download_verified_update
    assert worker.args[0] == NEWER
    worker.start.assert_called_once()


def test_new_version_declined_downloads_nothing(win, boxes, workers):
    UpdateCheckController(win).on_update_check_done(NEWER)

    assert workers == []


def test_new_version_without_checksum_opens_the_download_page(win, boxes, workers):
    boxes.question.return_value = "yes"

    UpdateCheckController(win).on_update_check_done(
        {"version": "8.7.0", "url": "https://updates.test/descargas"}
    )

    assert workers == []
    ucc_module.QDesktopServices.openUrl.assert_called_once()


def test_nothing_is_shown_while_closing(win, boxes):
    win._is_closing = True

    UpdateCheckController(win).on_update_check_done(None)

    boxes.information.assert_not_called()
    boxes.warning.assert_not_called()


def test_failed_download_warns(win, boxes):
    UpdateCheckController(win)._on_update_download_done(None)

    boxes.warning.assert_called_once()


def test_verified_download_runs_the_installer_if_accepted(win, boxes):
    boxes.question.return_value = "yes"

    UpdateCheckController(win)._on_update_download_done(SimpleNamespace())

    ucc_module.QDesktopServices.openUrl.assert_called_once()
