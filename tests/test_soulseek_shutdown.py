from core import soulseek_client


def test_search_stops_polling_when_client_closes(monkeypatch):
    client = soulseek_client.SoulseekClient()
    client._post = lambda *args, **kwargs: {"id": "search-id"}
    calls = []

    def close_during_first_poll(*args, **kwargs):
        calls.append(1)
        client.cerrar()
        return {"responses": [], "isComplete": False}

    client._get = close_during_first_poll
    monkeypatch.setattr(soulseek_client, "_BUSQUEDA_ESPERA", 60)

    assert client.buscar("test") == []
    assert len(calls) == 1
