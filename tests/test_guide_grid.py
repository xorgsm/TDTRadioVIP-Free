"""Maquetación pura de la parrilla de la Guía (core.guide_grid)."""
from datetime import datetime, timedelta, timezone

import pytest

from core.channels import Channel
from core.epg import Programme, _prepare_guide, channel_key
from core.guide_grid import GuideCell, GuideRow, build_rows

WINDOW = datetime(2026, 11, 20, 21, 0)


def _xt(dt: datetime) -> str:
    return dt.strftime("%Y%m%d%H%M%S")


def _prog(title, start: datetime, stop: datetime, tvg="La1.es@SD") -> Programme:
    return Programme(channel_id=tvg, title=title, start=_xt(start), stop=_xt(stop))


def _channel(name="La 1", tvg="La1.es@SD") -> Channel:
    return Channel(name=name, url="http://x", tvg_id=tvg)


def _rows(programmes, *, channels=None, window=WINDOW, hours=3.0, now=None):
    channels = channels if channels is not None else [_channel()]
    guide = {channel_key("La1.es@SD"): programmes}
    return build_rows(guide, channels, window, hours, now or window - timedelta(days=1))


def test_cell_position_and_width():
    rows = _rows([_prog("Telediario", WINDOW + timedelta(minutes=30), WINDOW + timedelta(minutes=90))])
    assert len(rows) == 1
    row = rows[0]
    assert isinstance(row, GuideRow)
    assert row.tvg_id == "La1.es@SD"
    assert row.channel_name == "La 1"
    (cell,) = row.cells
    assert isinstance(cell, GuideCell)
    assert cell.left == pytest.approx(1 / 6)
    assert cell.width == pytest.approx(1 / 3)
    assert cell.title == "Telediario"
    assert cell.start == _xt(WINDOW + timedelta(minutes=30))
    assert cell.stop == _xt(WINDOW + timedelta(minutes=90))
    assert cell.tvg_id == "La1.es@SD"
    assert cell.is_now is False


def test_program_crossing_window_start_is_clipped():
    rows = _rows([_prog("Cine", WINDOW - timedelta(hours=1), WINDOW + timedelta(minutes=30))])
    (cell,) = rows[0].cells
    assert cell.left == pytest.approx(0.0)
    assert cell.width == pytest.approx(1 / 6)
    # Las horas originales se conservan (son la clave de avisos/grabaciones).
    assert cell.start == _xt(WINDOW - timedelta(hours=1))


def test_program_crossing_midnight_is_clipped_to_window():
    window = datetime(2026, 11, 20, 22, 0)  # 22:00 + 3 h -> termina a la 01:00
    prog = _prog("Madrugada", datetime(2026, 11, 20, 23, 30), datetime(2026, 11, 21, 1, 30))
    (cell,) = _rows([prog], window=window)[0].cells
    assert cell.left == pytest.approx(0.5)
    assert cell.width == pytest.approx(0.5)
    assert cell.left + cell.width <= 1.0 + 1e-9


def test_stop_before_start_is_dropped():
    rows = _rows([
        _prog("Al revés", WINDOW + timedelta(hours=1), WINDOW + timedelta(minutes=30)),
        _prog("Sin duración", WINDOW + timedelta(hours=1), WINDOW + timedelta(hours=1)),
        Programme(channel_id="x", title="Fechas rotas", start="basura", stop=""),
        _prog("Bueno", WINDOW, WINDOW + timedelta(hours=1)),
    ])
    assert [c.title for c in rows[0].cells] == ["Bueno"]


def test_channel_without_guide_has_empty_row():
    rows = _rows([], channels=[_channel(), _channel("Sin guía", "Nada.es")])
    assert [r.tvg_id for r in rows] == ["La1.es@SD", "Nada.es"]
    assert rows[1].cells == []
    assert rows[1].channel_name == "Sin guía"


def test_is_now_marks_only_the_running_programme():
    progs = [
        _prog("A", WINDOW, WINDOW + timedelta(hours=1)),
        _prog("B", WINDOW + timedelta(hours=1), WINDOW + timedelta(hours=2)),
        _prog("C", WINDOW + timedelta(hours=2), WINDOW + timedelta(hours=3)),
    ]
    cells = _rows(progs, now=WINDOW + timedelta(minutes=90))[0].cells
    assert [c.is_now for c in cells] == [False, True, False]
    # Frontera: en el instante exacto del cambio solo cuenta el que empieza.
    cells = _rows(progs, now=WINDOW + timedelta(hours=1))[0].cells
    assert [c.is_now for c in cells] == [False, True, False]


# --- Casos de borde ---------------------------------------------------------

def test_cells_are_sorted_by_start():
    progs = [
        _prog("C", WINDOW + timedelta(hours=2), WINDOW + timedelta(hours=3)),
        _prog("A", WINDOW, WINDOW + timedelta(hours=1)),
        _prog("B", WINDOW + timedelta(hours=1), WINDOW + timedelta(hours=2)),
    ]
    assert [c.title for c in _rows(progs)[0].cells] == ["A", "B", "C"]


def test_programme_fully_outside_window_is_dropped():
    progs = [
        _prog("Antes", WINDOW - timedelta(hours=2), WINDOW - timedelta(hours=1)),
        _prog("Toca el borde", WINDOW - timedelta(hours=1), WINDOW),
        _prog("Después", WINDOW + timedelta(hours=3), WINDOW + timedelta(hours=4)),
    ]
    assert _rows(progs)[0].cells == []


def test_programme_covering_whole_window_fills_it():
    prog = _prog("Maratón", WINDOW - timedelta(hours=1), WINDOW + timedelta(hours=5))
    (cell,) = _rows([prog])[0].cells
    assert (cell.left, cell.width) == (pytest.approx(0.0), pytest.approx(1.0))


@pytest.mark.parametrize("hours", [0, -1, float("nan"), float("inf"), 1e10, 1e300])
def test_unusable_hours_gives_rows_without_cells(hours):
    # Sin ventana representable (no positiva, no finita o que desborda
    # timedelta): filas sin celdas y sin excepción.
    rows = _rows([_prog("A", WINDOW, WINDOW + timedelta(hours=1))], hours=hours)
    assert [r.tvg_id for r in rows] == ["La1.es@SD"]
    assert rows[0].cells == []


def test_window_end_past_datetime_max_gives_rows_without_cells():
    # La duración cabe en un timedelta, pero el final de la ventana no cabe en un datetime.
    rows = _rows([], window=datetime.max - timedelta(hours=1), hours=3.0)
    assert [r.tvg_id for r in rows] == ["La1.es@SD"]
    assert rows[0].cells == []


def test_channel_without_tvg_id_is_skipped():
    rows = _rows([], channels=[_channel("Sin id", ""), _channel("Solo símbolos", "@HD"), _channel()])
    assert [r.channel_name for r in rows] == ["La 1"]


def test_xmltv_timezone_is_honoured():
    # 20:30 UTC = 21:30 hora local solo si el equipo está en UTC+1; se calcula
    # el desfase real del sistema para que la prueba no dependa del huso.
    local_start = WINDOW + timedelta(minutes=30)
    utc_start = local_start.astimezone(timezone.utc)
    prog = Programme(
        channel_id="x", title="Con zona",
        start=utc_start.strftime("%Y%m%d%H%M%S") + " +0000",
        stop=(utc_start + timedelta(hours=1)).strftime("%Y%m%d%H%M%S") + " +0000",
    )
    (cell,) = _rows([prog])[0].cells
    assert cell.left == pytest.approx(1 / 6)
    assert cell.width == pytest.approx(1 / 3)


def test_aware_window_and_now_are_converted_to_local_naive():
    aware_window = WINDOW.astimezone()  # mismo instante, con zona local
    aware_now = (WINDOW + timedelta(minutes=45)).astimezone(timezone.utc)
    prog = _prog("A", WINDOW + timedelta(minutes=30), WINDOW + timedelta(minutes=90))
    (cell,) = _rows([prog], window=aware_window, now=aware_now)[0].cells
    assert cell.left == pytest.approx(1 / 6)
    assert cell.is_now is True


def test_prepared_guide_is_not_reparsed(monkeypatch):
    guide = _prepare_guide({channel_key("La1.es@SD"): [
        _prog("A", WINDOW, WINDOW + timedelta(hours=1)),
    ]})
    import core.guide_grid as grid

    def boom(_value):
        raise AssertionError("no debe reparsear una guía preparada")

    monkeypatch.setattr(grid, "parse_xmltv_time", boom)
    rows = build_rows(guide, [_channel()], WINDOW, 3, WINDOW)
    assert [c.title for c in rows[0].cells] == ["A"]
