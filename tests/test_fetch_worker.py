import logging

from PySide6.QtWidgets import QApplication

from ui.fetch_worker import FetchWorker


def test_fetch_worker_logs_the_exception_and_emits_none(caplog):
    app = QApplication.instance() or QApplication([])
    recibidos = []

    def guardar():
        raise OSError("disco de solo lectura")

    worker = FetchWorker(guardar)
    worker.done.connect(recibidos.append)
    with caplog.at_level(logging.WARNING):
        worker.start()
        assert worker.wait(5000)
        app.processEvents()

    assert recibidos == [None]
    assert any("guardar" in r.getMessage() and r.exc_info for r in caplog.records)
