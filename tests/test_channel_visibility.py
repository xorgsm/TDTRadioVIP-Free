"""Pruebas para ocultar canales públicos sin modificar la lista original."""

from core import channels


def test_hidden_channels_are_persistent_filter_and_can_be_restored(tmp_path, monkeypatch):
    """Ocultar uno no afecta a otros y restaurarlo lo vuelve a mostrar."""
    monkeypatch.setattr(channels, "get_profile_data_dir", lambda: tmp_path)

    catalog = [
        channels.Channel("Canal que no interesa", "https://example.test/skip"),
        channels.Channel("Canal favorito", "https://example.test/keep"),
    ]

    assert channels.hide_channels(["Canal que no interesa"]) == 1
    assert [entry.name for entry in channels.filter_hidden(catalog)] == ["Canal favorito"]

    # Repetir la acción no duplica datos ni oculta más canales.
    assert channels.hide_channels(["Canal que no interesa"]) == 0
    assert channels.unhide_channels(["Canal que no interesa"]) == 1
    assert [entry.name for entry in channels.filter_hidden(catalog)] == [
        "Canal que no interesa",
        "Canal favorito",
    ]
