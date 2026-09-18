from types import SimpleNamespace

import pytest

import libtorrent as lt

from core import torrent_client as tc


# ---------------------------------------------------------------------------
# Dobles de prueba -- nunca se crea una sesión real de libtorrent ni se toca
# la red; solo se usa el módulo `libtorrent` real para leer sus constantes
# de estado (lt.torrent_status.*), igual que hace core/torrent_client.py.
# ---------------------------------------------------------------------------


class FakeErrc:
    def __init__(self, value=0, message=""):
        self._value = value
        self._message = message

    def value(self):
        return self._value

    def message(self):
        return self._message


def _status(**overrides):
    base = dict(
        errc=FakeErrc(0, ""),
        state=lt.torrent_status.downloading,
        paused=False,
        upload_rate=0,
        download_rate=0,
        num_peers=0,
        name="",
        total_wanted=0,
        total_wanted_done=0,
        progress=0.0,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class FakeParams:
    def __init__(self, name=""):
        self.trackers = []
        self.save_path = None
        self.ti = None
        self.name = name


class FakeHandle:
    def __init__(self, valid=True):
        self._valid = valid
        self.paused = False
        self.resumed = False

    def is_valid(self):
        return self._valid

    def pause(self):
        self.paused = True

    def resume(self):
        self.resumed = True


class FakeSession:
    def __init__(self):
        self.added = []
        self.removed = []
        self.fail_add = None

    def add_torrent(self, params):
        if self.fail_add:
            raise self.fail_add
        handle = FakeHandle()
        self.added.append((params, handle))
        return handle

    def remove_torrent(self, handle, flags):
        self.removed.append((handle, flags))


# ---------------------------------------------------------------------------
# paquete_disponible()
# ---------------------------------------------------------------------------


def test_paquete_disponible_true_when_libtorrent_importable(monkeypatch):
    monkeypatch.setattr(tc, "lt", object())
    assert tc.paquete_disponible() is True


def test_paquete_disponible_false_when_libtorrent_missing(monkeypatch):
    monkeypatch.setattr(tc, "lt", None)
    assert tc.paquete_disponible() is False


# ---------------------------------------------------------------------------
# _estado_legible()
# ---------------------------------------------------------------------------


def test_estado_legible_reports_error_when_errc_has_value():
    status = _status(errc=FakeErrc(1, "disk full"))
    assert tc._estado_legible(status) == "error"


def test_estado_legible_reports_checking_states():
    for estado in (
        lt.torrent_status.checking_files,
        lt.torrent_status.checking_resume_data,
        lt.torrent_status.queued_for_checking,
    ):
        assert tc._estado_legible(_status(state=estado)) == "checkingDL"


def test_estado_legible_reports_metadl_and_queueddl():
    assert (
        tc._estado_legible(_status(state=lt.torrent_status.downloading_metadata)) == "metaDL"
    )
    assert tc._estado_legible(_status(state=lt.torrent_status.allocating)) == "queuedDL"


def test_estado_legible_finished_paused_is_pausedup():
    status = _status(state=lt.torrent_status.finished, paused=True)
    assert tc._estado_legible(status) == "pausedUP"


def test_estado_legible_finished_no_activity_is_stalledup():
    status = _status(state=lt.torrent_status.finished, upload_rate=0, num_peers=0)
    assert tc._estado_legible(status) == "stalledUP"


def test_estado_legible_finished_with_activity_is_uploading():
    status = _status(state=lt.torrent_status.seeding, upload_rate=100, num_peers=1)
    assert tc._estado_legible(status) == "uploading"


def test_estado_legible_downloading_paused_is_pauseddl():
    status = _status(state=lt.torrent_status.downloading, paused=True)
    assert tc._estado_legible(status) == "pausedDL"


def test_estado_legible_downloading_no_activity_is_stalleddl():
    status = _status(state=lt.torrent_status.downloading, download_rate=0, num_peers=0)
    assert tc._estado_legible(status) == "stalledDL"


def test_estado_legible_downloading_with_activity_is_downloading():
    status = _status(state=lt.torrent_status.downloading, download_rate=500, num_peers=3)
    assert tc._estado_legible(status) == "downloading"


def test_estado_legible_falls_back_to_error_attribute_when_errc_raises():
    class BadErrc:
        def value(self):
            raise RuntimeError("sin soporte en este binding")

    status = _status(errc=BadErrc())
    status.error = "algo raro"
    assert tc._estado_legible(status) == "error"


# ---------------------------------------------------------------------------
# TorrentClient.conectar()
# ---------------------------------------------------------------------------


def test_conectar_returns_error_message_when_libtorrent_not_installed(monkeypatch):
    monkeypatch.setattr(tc, "lt", None)
    monkeypatch.setattr(tc, "LIBTORRENT_IMPORT_ERROR", "No module named 'libtorrent'")
    client = tc.TorrentClient()

    resultado = client.conectar()

    assert resultado == (
        "No se pudo cargar el motor de torrents (libtorrent): "
        "No module named 'libtorrent'"
    )
    assert client.conectado is False


def test_conectar_returns_none_without_creating_session_when_already_connected(monkeypatch):
    client = tc.TorrentClient()
    client._session = object()

    def boom(*a, **k):
        raise AssertionError("no debería crear otra sesión si ya está conectado")

    monkeypatch.setattr(tc.lt, "session", boom)

    assert client.conectar() is None


def test_conectar_returns_none_without_creating_session_when_closing(monkeypatch):
    client = tc.TorrentClient()
    client._cerrando = True

    def boom(*a, **k):
        raise AssertionError("no debería crear una sesión si ya se está cerrando")

    monkeypatch.setattr(tc.lt, "session", boom)

    assert client.conectar() is None
    assert client._session is None


def test_conectar_returns_error_message_when_session_creation_raises(monkeypatch):
    client = tc.TorrentClient()

    def fake_session(settings):
        raise RuntimeError("puerto ocupado")

    monkeypatch.setattr(tc.lt, "session", fake_session)

    resultado = client.conectar()

    assert resultado == "No se pudo arrancar el motor de torrents: puerto ocupado"
    assert client._session is None


def test_conectar_discards_session_created_after_close_requested_mid_construction(monkeypatch):
    client = tc.TorrentClient()

    def fake_session(settings):
        # Simula cerrar() disparado por otro hilo justo mientras
        # lt.session(...) todavía está construyéndose.
        client._cerrando = True
        return object()

    monkeypatch.setattr(tc.lt, "session", fake_session)

    resultado = client.conectar()

    assert resultado is None
    assert client._session is None


def test_conectar_success_stores_session_and_marks_connected(monkeypatch):
    client = tc.TorrentClient()
    fake_session_obj = object()
    ajustes_usados = {}

    def fake_session_ctor(settings):
        ajustes_usados.update(settings)
        return fake_session_obj

    monkeypatch.setattr(tc.lt, "session", fake_session_ctor)

    resultado = client.conectar()

    assert resultado is None
    assert client.conectado is True
    assert client._session is fake_session_obj
    assert ajustes_usados["enable_dht"] is True


# ---------------------------------------------------------------------------
# TorrentClient.anadir()
# ---------------------------------------------------------------------------


def test_anadir_returns_error_when_not_connected():
    client = tc.TorrentClient()
    resultado = client.anadir("magnet:?xt=urn:btih:abc", "C:/dest")
    assert resultado == "El motor de torrents no está en marcha."


def test_anadir_parses_magnet_and_adds_public_trackers(monkeypatch):
    client = tc.TorrentClient()
    client._session = FakeSession()
    fake_params = FakeParams(name="mi-torrent")

    monkeypatch.setattr(tc.lt, "parse_magnet_uri", lambda uri: fake_params)

    resultado = client.anadir("magnet:?xt=urn:btih:abc", "C:/destino")

    assert resultado is None
    assert fake_params.save_path == "C:/destino"
    assert fake_params.trackers == tc._TRACKERS_PUBLICOS
    assert len(client._handles) == 1
    assert list(client._nombres_pendientes.values()) == ["mi-torrent"]


def test_anadir_parses_torrent_file_path(monkeypatch):
    client = tc.TorrentClient()
    client._session = FakeSession()
    fake_params = FakeParams()
    fake_info = object()

    monkeypatch.setattr(tc.lt, "torrent_info", lambda ruta: fake_info)
    monkeypatch.setattr(tc.lt, "add_torrent_params", lambda: fake_params)

    resultado = client.anadir("C:/archivo.torrent", "C:/destino")

    assert resultado is None
    assert fake_params.ti is fake_info
    assert fake_params.save_path == "C:/destino"


def test_anadir_returns_error_when_link_is_invalid(monkeypatch):
    client = tc.TorrentClient()
    client._session = FakeSession()

    def fallo(uri):
        raise ValueError("magnet corrupto")

    monkeypatch.setattr(tc.lt, "parse_magnet_uri", fallo)

    resultado = client.anadir("magnet:?bad", "C:/destino")

    assert "no es válido" in resultado
    assert "magnet corrupto" in resultado


def test_anadir_returns_error_when_session_rejects_torrent(monkeypatch):
    client = tc.TorrentClient()
    session = FakeSession()
    session.fail_add = RuntimeError("torrent duplicado")
    client._session = session
    fake_params = FakeParams()

    monkeypatch.setattr(tc.lt, "parse_magnet_uri", lambda uri: fake_params)

    resultado = client.anadir("magnet:?xt=urn:btih:abc", "C:/destino")

    assert "rechazó" in resultado
    assert "torrent duplicado" in resultado
    assert client._handles == {}


def test_anadir_continues_when_trackers_are_not_mutable(monkeypatch):
    client = tc.TorrentClient()
    client._session = FakeSession()

    class ParamsSinTrackersMutables:
        save_path = None
        ti = None
        name = "sin-trackers"

        @property
        def trackers(self):
            return []

    fake_params = ParamsSinTrackersMutables()
    monkeypatch.setattr(tc.lt, "parse_magnet_uri", lambda uri: fake_params)

    resultado = client.anadir("magnet:?xt=urn:btih:abc", "C:/destino")

    assert resultado is None
    assert len(client._handles) == 1


# ---------------------------------------------------------------------------
# TorrentClient.listar()
# ---------------------------------------------------------------------------


def test_listar_returns_empty_when_not_connected():
    client = tc.TorrentClient()
    assert client.listar() == []


def test_listar_skips_invalid_handles():
    client = tc.TorrentClient()
    client._session = FakeSession()
    client._handles["token"] = FakeHandle(valid=False)

    assert client.listar() == []


def test_listar_maps_status_fields_for_active_download():
    client = tc.TorrentClient()
    client._session = FakeSession()
    handle = FakeHandle()
    handle.status = lambda: _status(
        state=lt.torrent_status.downloading,
        name="Pelicula.mkv",
        total_wanted=1000,
        total_wanted_done=250,
        download_rate=50,
        upload_rate=10,
        num_peers=4,
    )
    client._handles["abc"] = handle

    [info] = client.listar()

    assert info.hash == "abc"
    assert info.name == "Pelicula.mkv"
    assert info.state == "downloading"
    assert info.progress == 0.25
    assert info.dlspeed == 50
    assert info.upspeed == 10
    assert info.peers == 4
    assert info.size == 1000
    assert info.eta == 15  # (1000-250)/50


def test_listar_eta_is_minus_one_when_no_download_rate():
    client = tc.TorrentClient()
    client._session = FakeSession()
    handle = FakeHandle()
    handle.status = lambda: _status(
        state=lt.torrent_status.downloading,
        name="x",
        total_wanted=1000,
        total_wanted_done=0,
        download_rate=0,
    )
    client._handles["abc"] = handle

    [info] = client.listar()

    assert info.eta == -1


def test_listar_progress_falls_back_to_status_progress_when_total_wanted_zero():
    client = tc.TorrentClient()
    client._session = FakeSession()
    handle = FakeHandle()
    handle.status = lambda: _status(
        state=lt.torrent_status.downloading_metadata,
        name="",
        total_wanted=0,
        total_wanted_done=0,
        progress=0.42,
    )
    client._handles["abc"] = handle

    [info] = client.listar()

    assert info.progress == 0.42


def test_listar_uses_pending_name_until_metadata_arrives():
    client = tc.TorrentClient()
    client._session = FakeSession()
    handle = FakeHandle()
    handle.status = lambda: _status(state=lt.torrent_status.downloading_metadata, name="")
    client._handles["abc"] = handle
    client._nombres_pendientes["abc"] = "Buscando.torrent"

    [info] = client.listar()

    assert info.name == "Buscando.torrent"
    assert "abc" in client._nombres_pendientes  # todavía sin metadatos reales


def test_listar_clears_pending_name_once_real_name_arrives():
    client = tc.TorrentClient()
    client._session = FakeSession()
    handle = FakeHandle()
    handle.status = lambda: _status(state=lt.torrent_status.downloading, name="Real.mkv")
    client._handles["abc"] = handle
    client._nombres_pendientes["abc"] = tc._NOMBRE_PENDIENTE

    [info] = client.listar()

    assert info.name == "Real.mkv"
    assert "abc" not in client._nombres_pendientes


# ---------------------------------------------------------------------------
# pausar() / reanudar() / eliminar()
# ---------------------------------------------------------------------------


def test_pausar_calls_handle_pause_when_valid():
    client = tc.TorrentClient()
    handle = FakeHandle()
    client._handles["abc"] = handle

    client.pausar("abc")

    assert handle.paused is True


def test_pausar_noop_when_handle_missing():
    client = tc.TorrentClient()
    client.pausar("no-existe")  # no debe lanzar


def test_pausar_noop_when_handle_invalid():
    client = tc.TorrentClient()
    handle = FakeHandle(valid=False)
    client._handles["abc"] = handle

    client.pausar("abc")

    assert handle.paused is False


def test_reanudar_calls_handle_resume_when_valid():
    client = tc.TorrentClient()
    handle = FakeHandle()
    client._handles["abc"] = handle

    client.reanudar("abc")

    assert handle.resumed is True


def test_reanudar_noop_when_handle_invalid():
    client = tc.TorrentClient()
    handle = FakeHandle(valid=False)
    client._handles["abc"] = handle

    client.reanudar("abc")

    assert handle.resumed is False


def test_eliminar_removes_handle_and_forwards_delete_files_flag():
    client = tc.TorrentClient()
    session = FakeSession()
    client._session = session
    handle = FakeHandle()
    client._handles["abc"] = handle
    client._nombres_pendientes["abc"] = "pendiente"

    client.eliminar("abc", borrar_archivos=True)

    assert "abc" not in client._handles
    assert "abc" not in client._nombres_pendientes
    assert session.removed == [(handle, lt.session.delete_files)]


def test_eliminar_uses_zero_flag_when_not_deleting_files():
    client = tc.TorrentClient()
    session = FakeSession()
    client._session = session
    handle = FakeHandle()
    client._handles["abc"] = handle

    client.eliminar("abc", borrar_archivos=False)

    assert session.removed == [(handle, 0)]


def test_eliminar_noop_when_handle_missing():
    client = tc.TorrentClient()
    client._session = FakeSession()
    client.eliminar("no-existe")  # no debe lanzar


def test_eliminar_noop_when_handle_invalid():
    client = tc.TorrentClient()
    session = FakeSession()
    client._session = session
    client._handles["abc"] = FakeHandle(valid=False)

    client.eliminar("abc")

    assert session.removed == []


def test_eliminar_noop_when_not_connected():
    client = tc.TorrentClient()
    client._handles["abc"] = FakeHandle()

    client.eliminar("abc")  # self._session es None: no debe lanzar

    assert "abc" not in client._handles


# ---------------------------------------------------------------------------
# cerrar()
# ---------------------------------------------------------------------------


def test_cerrar_clears_session_and_handles():
    client = tc.TorrentClient()
    client._session = FakeSession()
    client._handles["abc"] = FakeHandle()
    client._nombres_pendientes["abc"] = "x"

    client.cerrar()

    assert client._session is None
    assert client._handles == {}
    assert client._nombres_pendientes == {}
    assert client._cerrando is True


def test_cerrar_accepts_on_wait_callback_without_using_it():
    client = tc.TorrentClient()
    client._session = FakeSession()
    llamado = []

    client.cerrar(on_wait=lambda: llamado.append(1))

    assert llamado == []  # cerrar() no bloquea; no debe invocar on_wait
