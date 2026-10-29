"""pump_events_without_input: la espera de parar una grabación bombea eventos
para que la ventana no se congele, pero sin entregar entrada del usuario."""
from unittest.mock import Mock

from PySide6.QtCore import QEventLoop

from ui import event_pump


def test_pump_excluye_los_eventos_de_entrada_del_usuario(monkeypatch):
    process_events = Mock()
    monkeypatch.setattr(event_pump.QCoreApplication, "instance", Mock(return_value=object()))
    monkeypatch.setattr(event_pump.QCoreApplication, "processEvents", process_events)

    event_pump.pump_events_without_input()

    process_events.assert_called_once_with(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
