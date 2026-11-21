"""Panel de detalle de la Guía (ui.guide_detail.GuideDetailPanel).

Reutiliza epg_reminders, recording_schedule y recurring_recordings; los tests
aíslan sus ficheros en un perfil temporal. Todo es estructural (estado de
botones, rectángulos con la hoja de estilos real), porque no se ve la pantalla.
"""
import sys
from datetime import datetime, timedelta

import pytest
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMessageBox, QWidget

from core import epg_reminders, recording_schedule, recurring_recordings
from ui.guide_detail import GuideDetailPanel

NOW = datetime(2026, 11, 20, 21, 10)  # viernes


@pytest.fixture
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(scope="session")
def app_font():
    from ui.application import _register_app_font

    QApplication.instance() or QApplication([])
    _register_app_font()


@pytest.fixture(autouse=True)
def profile(tmp_path, monkeypatch):
    for module in (epg_reminders, recording_schedule, recurring_recordings):
        monkeypatch.setattr(module, "get_profile_data_dir", lambda: tmp_path)


@pytest.fixture
def warnings(monkeypatch):
    shown = []
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: shown.append(a)))
    return shown


def _xt(dt):
    return dt.strftime("%Y%m%d%H%M%S")


def _info(**over):
    info = {
        "tvg_id": "La1.es@SD",
        "channel_name": "La 1",
        "channel_url": "http://la1/stream.m3u8",
        "title": "Cine: El Ministerio",
        "start": _xt(NOW + timedelta(minutes=50)),
        "stop": _xt(NOW + timedelta(minutes=110)),
        "description": "Una comedia de los años sesenta.",
    }
    info.update(over)
    return info


class _Ticker:
    """Reloj monótono manual: los clics «seguidos» no avanzan."""

    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t

    def wait(self):
        self.t += 5.0


def _panel(info=None, **kwargs):
    ticker = kwargs.setdefault("monotonic", _Ticker())
    kwargs.setdefault("clock", lambda: NOW)
    panel = GuideDetailPanel(**kwargs)
    panel.ticker = ticker
    if info is not None:
        panel.show_programme(info)
    return panel


def test_panel_paints_its_styled_background(app):
    from PySide6.QtCore import Qt

    panel = _panel()
    assert panel.testAttribute(Qt.WA_StyledBackground)


def test_without_programme_everything_is_disabled(app):
    panel = _panel()
    assert not any(b.isEnabled() for b in (panel.view_btn, panel.record_btn, panel.remind_btn, panel.series_btn))
    assert panel.title_text() == GuideDetailPanel.EMPTY_TITLE
    panel.show_programme(_info())
    panel.show_programme(None)
    assert not panel.view_btn.isEnabled()
    assert panel.title_text() == GuideDetailPanel.EMPTY_TITLE


def test_shows_programme_data(app):
    panel = _panel(_info())
    assert panel.title_text() == "Cine: El Ministerio"
    assert "La 1" in panel.meta_text() and "22:00" in panel.meta_text() and "23:00" in panel.meta_text()
    assert panel.description_text() == "Una comedia de los años sesenta."
    assert all(b.isEnabled() for b in (panel.view_btn, panel.record_btn, panel.remind_btn, panel.series_btn))


@pytest.mark.parametrize("missing", ["channel_url", "stop"])
def test_record_disabled_without_url_or_stop(app, missing):
    panel = _panel(_info(**{missing: ""}))
    assert not panel.record_btn.isEnabled()
    panel.record_btn.click()
    assert recording_schedule.load_scheduled() == []


def test_record_schedules_and_cancels(app):
    cancelled = []
    panel = _panel(_info(), cancel_scheduled=lambda *a: (cancelled.append(a), recording_schedule.remove_scheduled(*a)))
    info = _info()
    panel.record_btn.click()
    assert recording_schedule.has_scheduled(info["tvg_id"], info["title"], info["start"])
    assert panel.record_btn.text() == GuideDetailPanel.CANCEL_RECORD_TEXT
    panel.ticker.wait()
    panel.record_btn.click()
    assert cancelled == [(info["tvg_id"], info["title"], info["start"])]
    assert not recording_schedule.has_scheduled(info["tvg_id"], info["title"], info["start"])
    assert panel.record_btn.text() == GuideDetailPanel.RECORD_TEXT


def test_record_shows_conflict_and_does_not_add(app, warnings):
    other = recording_schedule.ScheduledRecording(
        tvg_id="La2.es@SD", channel_name="La 2", channel_url="http://la2", title="Otra",
        start=_xt(NOW + timedelta(minutes=30)), stop=_xt(NOW + timedelta(minutes=90)),
    )
    recording_schedule.add_scheduled(other)
    panel = _panel(_info())
    panel.record_btn.click()
    assert len(warnings) == 1
    assert "Otra" in warnings[0][2]
    assert len(recording_schedule.load_scheduled()) == 1
    assert panel.record_btn.text() == GuideDetailPanel.RECORD_TEXT


def test_reminder_toggles_label_between_avisarme_and_quitar_aviso(app):
    info = _info()
    panel = _panel(info)
    assert panel.remind_btn.text() == GuideDetailPanel.REMIND_TEXT
    panel.remind_btn.click()
    assert epg_reminders.has_reminder(info["tvg_id"], info["title"], info["start"])
    assert panel.remind_btn.text() == GuideDetailPanel.UNREMIND_TEXT
    panel.ticker.wait()
    panel.remind_btn.click()
    assert not epg_reminders.has_reminder(info["tvg_id"], info["title"], info["start"])
    assert panel.remind_btn.text() == GuideDetailPanel.REMIND_TEXT


def test_view_now_emits_tune_request_with_tvg_id(app):
    panel = _panel(_info())
    got = []
    panel.tune_requested.connect(got.append)
    panel.view_btn.click()
    assert got == ["La1.es@SD"]


def test_view_disabled_without_channel_url(app):
    panel = _panel(_info(channel_url=""))
    assert not panel.view_btn.isEnabled()
    assert not panel.record_btn.isEnabled()
    assert not panel.series_btn.isEnabled()


def test_finished_programme_cannot_be_recorded_or_reminded(app):
    ended = _info(start=_xt(NOW - timedelta(hours=2)), stop=_xt(NOW - timedelta(hours=1)))
    panel = _panel(ended)
    assert not panel.record_btn.isEnabled()
    assert not panel.remind_btn.isEnabled()
    assert not panel.series_btn.isEnabled()
    assert panel.view_btn.isEnabled()


def test_running_programme_can_be_recorded_but_not_reminded(app):
    running = _info(start=_xt(NOW - timedelta(minutes=10)), stop=_xt(NOW + timedelta(minutes=50)))
    panel = _panel(running)
    assert panel.record_btn.isEnabled()
    assert not panel.remind_btn.isEnabled()


def test_double_click_on_record_does_not_duplicate_or_cancel(app):
    panel = _panel(_info())
    panel.record_btn.click()
    panel.record_btn.click()  # sin que pase el tiempo: se ignora
    assert len(recording_schedule.load_scheduled()) == 1
    assert panel.record_btn.text() == GuideDetailPanel.CANCEL_RECORD_TEXT


def test_double_click_on_remind_does_not_toggle_twice(app):
    panel = _panel(_info())
    panel.remind_btn.click()
    panel.remind_btn.click()
    assert len(epg_reminders.load_reminders()) == 1
    assert panel.remind_btn.text() == GuideDetailPanel.UNREMIND_TEXT


def test_debounce_does_not_leak_to_a_newly_selected_programme(app):
    # Avisar en A y, sin que pase el tiempo, elegir B y avisar: B es otra
    # acción legítima, no un doble clic.
    panel = _panel(_info())
    panel.remind_btn.click()
    panel.show_programme(_info(
        title="Otro programa",
        start=_xt(NOW + timedelta(minutes=130)),
        stop=_xt(NOW + timedelta(minutes=190)),
    ))
    panel.remind_btn.click()
    assert len(epg_reminders.load_reminders()) == 2


def test_series_creates_rule_for_that_weekday_time_and_duration(app):
    panel = _panel(_info())
    panel.series_btn.click()
    rules = recurring_recordings.load_rules()
    assert len(rules) == 1
    rule = rules[0]
    assert (rule.channel_name, rule.channel_url) == ("La 1", "http://la1/stream.m3u8")
    assert rule.days == [4] and rule.start_time == "22:00" and rule.duration_minutes == 60
    assert panel.series_btn.text() == GuideDetailPanel.UNSERIES_TEXT
    panel.ticker.wait()
    panel.series_btn.click()
    assert recurring_recordings.load_rules() == []
    assert panel.series_btn.text() == GuideDetailPanel.SERIES_TEXT


def test_series_double_click_creates_one_rule(app):
    panel = _panel(_info())
    panel.series_btn.click()
    panel.series_btn.click()
    assert len(recurring_recordings.load_rules()) == 1


def test_series_conflict_warns_and_does_not_add(app, warnings):
    recurring_recordings.add_rule("La 2", "http://la2", [4], "22:30", 60)
    panel = _panel(_info())
    panel.series_btn.click()
    assert len(warnings) == 1
    assert len(recurring_recordings.load_rules()) == 1


def test_series_disabled_when_duration_is_out_of_range(app):
    too_long = _info(stop=_xt(NOW + timedelta(minutes=50 + 601)))
    assert not _panel(too_long).series_btn.isEnabled()


def test_free_edition_hides_recording_buttons(app):
    panel = _panel(_info(), recording_enabled=False)
    panel.show()
    assert not panel.record_btn.isVisibleTo(panel)
    assert not panel.series_btn.isVisibleTo(panel)
    assert panel.view_btn.isVisibleTo(panel) and panel.remind_btn.isVisibleTo(panel)
    panel.record_btn.click()
    assert recording_schedule.load_scheduled() == []


def test_state_is_refreshed_when_shown_again(app):
    now = [NOW]
    panel = _panel(_info(), clock=lambda: now[0])
    panel.show()
    assert panel.remind_btn.isEnabled()
    panel.hide()
    now[0] = NOW + timedelta(hours=3)  # ya terminó
    panel.show()
    assert not panel.remind_btn.isEnabled()
    assert not panel.record_btn.isEnabled()


def test_remind_after_programme_started_adds_nothing(app):
    now = [NOW]
    panel = _panel(_info(), clock=lambda: now[0])
    panel.show()
    assert panel.remind_btn.isEnabled()
    now[0] = NOW + timedelta(minutes=55)  # ya empezó, sin tick que refresque
    panel.remind_btn.click()
    assert epg_reminders.load_reminders() == []


def test_record_after_programme_ended_adds_nothing(app):
    now = [NOW]
    panel = _panel(_info(), clock=lambda: now[0])
    panel.show()
    assert panel.record_btn.isEnabled()
    now[0] = NOW + timedelta(hours=3)  # ya terminó
    panel.record_btn.click()
    assert recording_schedule.load_scheduled() == []


def test_multi_day_rule_is_never_removed_from_the_panel(app, warnings):
    recurring_recordings.add_rule("La 1", "http://la1/stream.m3u8", [0, 1, 2, 3, 4], "22:00", 60)
    monday = NOW + timedelta(days=3, minutes=50)  # lunes 22:00
    panel = _panel(_info(start=_xt(monday), stop=_xt(monday + timedelta(hours=1))))
    assert panel.series_btn.text() == GuideDetailPanel.SERIES_TEXT
    panel.series_btn.click()
    rules = recurring_recordings.load_rules()
    assert len(rules) == 1 and rules[0].days == [0, 1, 2, 3, 4]


@pytest.mark.parametrize("delta_min", [0, -60])
def test_record_disabled_for_zero_or_reversed_interval(app, delta_min):
    start = NOW + timedelta(hours=26)
    panel = _panel(_info(start=_xt(start), stop=_xt(start + timedelta(minutes=delta_min))))
    assert not panel.record_btn.isEnabled()
    panel.record_btn.click()
    assert recording_schedule.load_scheduled() == []


def test_series_value_error_shows_warning_and_adds_nothing(app, warnings, monkeypatch):
    def boom(*a, **k):
        raise ValueError("URL no válida")

    monkeypatch.setattr(recurring_recordings, "add_rule", boom)
    panel = _panel(_info())
    panel.series_btn.click()
    assert len(warnings) == 1
    assert "URL no válida" in warnings[0][2]
    assert recurring_recordings.load_rules() == []


def test_module_imports_no_private_modules():
    import ui.guide_detail as detail

    private = {"core.license", "core.downloader", "core.caster", "ui.cast_controller", "ui.splash"}
    imported = {getattr(v, "__name__", "") for v in vars(detail).values()}
    assert not imported & private
    assert detail.__name__ in sys.modules


@pytest.mark.parametrize("height", [319, 599])
def test_panel_and_grid_do_not_overlap_at_860x580(app, app_font, height):
    from ui.guide_view import GuideView
    from ui.style import build_style
    from core.channels import Channel
    from PySide6.QtWidgets import QPushButton

    host = QWidget()
    layout = QHBoxLayout(host)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    view = GuideView([Channel(name="La 1", url="http://la1", group="General", tvg_id="La1.es@SD")], {},
                     clock=lambda: NOW)
    panel = _panel(_info(
        title="Un título de programa bastante largo que ocupa varias líneas del panel",
        description="Texto largo. " * 80,
    ))
    layout.addWidget(view, 1)
    layout.addWidget(panel)
    app.setStyleSheet(build_style())
    try:
        host.resize(750, height)
        host.show()
        QApplication.processEvents()
        assert 280 <= panel.width() <= 320
        panel_rect = panel.geometry()
        assert not panel_rect.intersects(view.geometry())
        buttons = [b for b in panel.findChildren(QPushButton)]
        assert len(buttons) == 4
        rects = []
        for button in buttons:
            assert button.isVisible(), button.text()
            rect = button.geometry()
            assert panel.rect().contains(rect), button.text()
            assert button.width() >= button.sizeHint().width(), button.text()
            assert button.height() >= button.sizeHint().height(), button.text()
            rects.append(rect)
        for i, a in enumerate(rects):
            for b in rects[i + 1:]:
                assert not a.intersects(b)
    finally:
        host.close()
        app.setStyleSheet("")
