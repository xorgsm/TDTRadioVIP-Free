import time
import uuid

from PySide6.QtWidgets import QApplication

from core.single_instance import SingleInstanceGuard


def _app():
    return QApplication.instance() or QApplication([])


def _pump_until(app, predicate, timeout_ms=2000, step_ms=10):
    waited = 0
    while not predicate() and waited < timeout_ms:
        app.processEvents()
        time.sleep(step_ms / 1000)
        waited += step_ms
    return predicate()


def test_first_instance_acquires_the_lock():
    app = _app()
    key = f"TDTRadioVIP-test-{uuid.uuid4().hex}"
    guard = SingleInstanceGuard(key)
    try:
        assert guard.try_acquire() is True
    finally:
        guard.deleteLater()


def test_second_instance_fails_to_acquire_and_notifies_the_first():
    app = _app()
    key = f"TDTRadioVIP-test-{uuid.uuid4().hex}"
    first = SingleInstanceGuard(key)
    second = SingleInstanceGuard(key)
    activated = []
    first.activation_requested.connect(lambda: activated.append(True))
    try:
        assert first.try_acquire() is True
        assert second.try_acquire() is False
        assert _pump_until(app, lambda: len(activated) == 1)
    finally:
        first.deleteLater()
        second.deleteLater()


def test_different_keys_do_not_collide():
    app = _app()
    key_a = f"TDTRadioVIP-test-{uuid.uuid4().hex}"
    key_b = f"TDTRadioVIP-test-{uuid.uuid4().hex}"
    guard_a = SingleInstanceGuard(key_a)
    guard_b = SingleInstanceGuard(key_b)
    try:
        assert guard_a.try_acquire() is True
        assert guard_b.try_acquire() is True
    finally:
        guard_a.deleteLater()
        guard_b.deleteLater()
