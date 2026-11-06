"""Pruebas de las filas compactas del catálogo (catalog_compact_rows)."""

import pytest
from PySide6.QtWidgets import QApplication

from core import config as cfg
from core.backup import sanitize_imported_settings
from ui.dialogs.settings import SettingsDialog
from ui.widgets import ChannelDelegate


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def test_por_defecto_conserva_la_fila_normal():
    assert cfg.DEFAULT_SETTINGS["catalog_compact_rows"] is False
    delegate = ChannelDelegate()
    assert delegate.sizeHint(None, None).height() == 84
    assert delegate.LOGO_SIZE == 54


def test_modo_compacto_reduce_fila_y_logo():
    delegate = ChannelDelegate()
    delegate.set_compact(True)
    assert delegate.sizeHint(None, None).height() == 56
    assert delegate.LOGO_SIZE < delegate.ROW_HEIGHT - 11


def test_compacto_se_puede_desactivar():
    delegate = ChannelDelegate()
    delegate.set_compact(True)
    delegate.set_compact(False)
    assert delegate.sizeHint(None, None).height() == 84
    assert delegate.LOGO_SIZE == 54


def test_un_delegado_compacto_no_afecta_a_otro():
    ChannelDelegate().set_compact(True)
    assert ChannelDelegate().sizeHint(None, None).height() == 84


@pytest.mark.parametrize("compact", [False, True])
def test_los_textos_caben_dentro_de_la_tarjeta(compact):
    delegate = ChannelDelegate()
    delegate.set_compact(compact)
    alto_tarjeta = delegate.ROW_HEIGHT - 11  # margenes de paint()
    assert delegate.NAME_TOP + delegate.NAME_HEIGHT <= delegate.SUBTITLE_TOP
    assert delegate.SUBTITLE_TOP + delegate.SUBTITLE_HEIGHT <= alto_tarjeta


def test_ajustes_importados_descartan_tipo_invalido():
    assert "catalog_compact_rows" not in sanitize_imported_settings({"catalog_compact_rows": []})
    assert sanitize_imported_settings({"catalog_compact_rows": True}) == {"catalog_compact_rows": True}


def test_dialogo_guarda_el_ajuste(app):
    dialog = SettingsDialog(dict(cfg.DEFAULT_SETTINGS))
    assert dialog.compact_rows_check.isChecked() is False
    dialog.compact_rows_check.setChecked(True)
    assert dialog.get_settings()["catalog_compact_rows"] is True


def test_la_vista_recoloca_las_filas_al_cambiar(app):
    """Con setUniformItemSizes la altura se cachea: sin doItemsLayout() las
    filas conservarían la altura anterior tras cambiar el ajuste."""
    from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt
    from PySide6.QtWidgets import QListView

    class Modelo(QAbstractListModel):
        def rowCount(self, parent=QModelIndex()):  # noqa: N802
            return 0 if parent.isValid() else 3

        def data(self, index, role=Qt.DisplayRole):
            return None

    delegate = ChannelDelegate()
    view = QListView()
    view.setUniformItemSizes(True)
    view.setItemDelegate(delegate)
    view.setModel(Modelo(view))
    view.resize(300, 300)
    view.show()
    app.processEvents()
    assert view.visualRect(view.model().index(1, 0)).height() == 84
    delegate.set_compact(True)
    view.doItemsLayout()
    assert view.visualRect(view.model().index(1, 0)).height() == 56
    view.close()


@pytest.mark.parametrize("estado", ["stable", "slow", "down", "restricted"])
def test_el_nombre_reserva_sitio_para_el_punto_de_salud(estado):
    """El punto se pinta en el borde derecho del nombre: sin esta reserva
    tapaba los puntos suspensivos de los nombres largos."""
    assert ChannelDelegate._name_width(200, estado) <= 200 - 8 - 4


@pytest.mark.parametrize("estado", [None, "", "desconocido"])
def test_sin_punto_de_salud_el_nombre_usa_todo_el_ancho(estado):
    assert ChannelDelegate._name_width(200, estado) == 200
