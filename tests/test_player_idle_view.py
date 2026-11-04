"""Vista de reposo del reproductor (ui/player_idle_view.py) y ElidedLabel."""
import pytest

from ui.player_idle_view import MAX_QUICK_ENTRIES, pick_quick_entries


def _e(name, kind="tv", url="http://x"):
    return {"type": kind, "name": name, "url": url}


def test_pick_quick_entries_recientes_antes_que_favoritos_sin_repetir():
    history = [_e("A"), _e("B")]
    favorites = [_e("B"), _e("C", "radio")]
    picked = pick_quick_entries(history, favorites)
    assert [p["name"] for p in picked] == ["A", "B", "C"]


def test_pick_quick_entries_excluye_la_entrada_del_boton_principal():
    history = [_e("A"), _e("B")]
    picked = pick_quick_entries(history, [], exclude=history[0])
    assert [p["name"] for p in picked] == ["B"]


def test_pick_quick_entries_ignora_entradas_sin_url_o_invalidas():
    history = [_e("A", url=""), "basura", None, _e("B")]
    assert [p["name"] for p in pick_quick_entries(history, [])] == ["B"]


def test_pick_quick_entries_respeta_el_limite():
    history = [_e(str(i)) for i in range(10)]
    assert len(pick_quick_entries(history, [])) == MAX_QUICK_ENTRIES


def test_mismo_nombre_en_tv_y_radio_son_entradas_distintas():
    picked = pick_quick_entries([_e("X", "tv"), _e("X", "radio")], [])
    assert len(picked) == 2


@pytest.fixture
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def test_elided_label_conserva_texto_completo(qapp):
    from ui.visual import ElidedLabel
    label = ElidedLabel("Nada en reproducción")
    label.show()
    label.resize(40, 20)
    label.setText("Nada en reproducción")
    assert label.text() == "Nada en reproducción"
    assert label.toolTip() == "Nada en reproducción"
    label.resize(2000, 20)
    assert label.toolTip() == ""


def test_idle_view_sin_historial_oculta_volver(qapp):
    from ui.player_idle_view import PlayerIdleView
    view = PlayerIdleView(on_activate=lambda e: None, on_search=lambda: None)
    view.refresh([], [])
    assert view.resume_btn.isHidden()


def test_idle_view_volver_reproduce_la_ultima_entrada(qapp):
    from ui.player_idle_view import PlayerIdleView
    played = []
    view = PlayerIdleView(on_activate=played.append, on_search=lambda: None)
    view.refresh([_e("Canal [Geo-blocked]")], [])
    view.resize(600, 600)
    view.resume_btn.click()
    assert played and played[0]["name"] == "Canal [Geo-blocked]"
    assert "Geo-blocked" not in view.resume_btn.text()


def _idle_view_in(qapp, width, height, entries):
    # Dentro de un padre sin layout, como en player_stack: el padre impone
    # la geometría aunque sea menor que el mínimo de la vista.
    from PySide6.QtWidgets import QWidget

    from ui.player_idle_view import PlayerIdleView
    parent = QWidget()
    parent.resize(width, height)
    view = PlayerIdleView(on_activate=lambda e: None, on_search=lambda: None, parent=parent)
    view.refresh(entries, [])
    view.setGeometry(0, 0, width, height)
    parent.show()
    qapp.processEvents()
    return parent, view


def _visible_quick_buttons(view):
    items = (view._quick_layout.itemAt(i).widget() for i in range(view._quick_layout.count()))
    return [w for w in items if w is not None and not w.isHidden()]


def test_idle_view_sin_espacio_no_comprime_los_accesos_rapidos(qapp):
    entries = [_e(f"Serie larga {i} (2005) S02 - S02E1{i}") for i in range(5)]
    parent, view = _idle_view_in(qapp, 560, 400, entries)
    for btn in _visible_quick_buttons(view):
        assert btn.height() >= btn.sizeHint().height()
    for label in (view.title, view.subtitle):
        if not label.isHidden():
            assert label.height() >= label.heightForWidth(label.width())


def test_idle_view_con_espacio_muestra_todo(qapp):
    entries = [_e(f"Canal {i}") for i in range(5)]
    parent, view = _idle_view_in(qapp, 840, 700, entries)
    assert not view.icon_label.isHidden()
    assert len(_visible_quick_buttons(view)) == 4
