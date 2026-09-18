import hashlib
import json
import time
import zipfile

import pytest

from core import soulseek_client


class FakeProcess:
    """Doble de subprocess.Popen -- nunca se lanza un slskd.exe real."""

    def __init__(self, poll_result=None):
        self._poll_result = poll_result
        self.killed = False
        self.terminated = False
        self.wait_calls = 0

    def poll(self):
        return self._poll_result

    def kill(self):
        self.killed = True

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        self.wait_calls += 1
        return 0


class FakeHTTPResponse:
    """Doble del objeto devuelto por urllib.request.urlopen()."""

    def __init__(self, data: bytes):
        self._data = data

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def read(self):
        return self._data


# ---------------------------------------------------------------------------
# conectar()
# ---------------------------------------------------------------------------


def test_conectar_returns_none_immediately_when_already_connected(monkeypatch):
    client = soulseek_client.SoulseekClient()
    client._proceso = FakeProcess(poll_result=None)  # poll() None => conectado

    def boom():
        raise AssertionError("no debería buscar el exe si ya está conectado")

    monkeypatch.setattr(soulseek_client, "_slskd_exe_path", boom)

    assert client.conectar("user", "pass", "C:/descargas") is None


def test_conectar_returns_message_when_exe_not_downloaded(monkeypatch):
    client = soulseek_client.SoulseekClient()
    monkeypatch.setattr(soulseek_client, "_slskd_exe_path", lambda: None)

    resultado = client.conectar("user", "pass", "C:/descargas")

    assert resultado == "slskd todavía no se ha descargado."


def test_conectar_returns_message_when_popen_fails(monkeypatch, tmp_path):
    client = soulseek_client.SoulseekClient()
    monkeypatch.setattr(soulseek_client, "_slskd_exe_path", lambda: tmp_path / "slskd.exe")

    def fake_popen(*args, **kwargs):
        raise OSError("permiso denegado")

    monkeypatch.setattr(soulseek_client.subprocess, "Popen", fake_popen)

    resultado = client.conectar("user", "pass", str(tmp_path))

    assert resultado == "No se pudo arrancar slskd: permiso denegado"


def test_conectar_starts_process_and_stores_port_when_api_answers(monkeypatch, tmp_path):
    client = soulseek_client.SoulseekClient()
    exe = tmp_path / "slskd.exe"
    monkeypatch.setattr(soulseek_client, "_slskd_exe_path", lambda: exe)

    fake_proc = FakeProcess(poll_result=None)
    llamadas = []

    def fake_popen(comando, **kwargs):
        llamadas.append((comando, kwargs))
        return fake_proc

    monkeypatch.setattr(soulseek_client.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(client, "_esperar_api", lambda: True)

    resultado = client.conectar("miuser", "mipass", str(tmp_path))

    assert resultado is None
    assert client.conectado is True
    assert client.puerto == soulseek_client.DEFAULT_HTTP_PORT
    comando, kwargs = llamadas[0]
    assert comando[0] == str(exe)
    assert "--http-port" in comando
    assert str(soulseek_client.DEFAULT_HTTP_PORT) in comando
    assert kwargs["env"]["SLSKD_SLSK_USERNAME"] == "miuser"
    assert kwargs["env"]["SLSKD_SLSK_PASSWORD"] == "mipass"


def test_conectar_tries_next_port_when_first_api_never_answers(monkeypatch, tmp_path):
    client = soulseek_client.SoulseekClient()
    monkeypatch.setattr(soulseek_client, "_slskd_exe_path", lambda: tmp_path / "slskd.exe")

    procesos = [FakeProcess(poll_result=None), FakeProcess(poll_result=None)]
    popen_calls = []

    def fake_popen(comando, **kwargs):
        popen_calls.append(comando)
        return procesos[len(popen_calls) - 1]

    monkeypatch.setattr(soulseek_client.subprocess, "Popen", fake_popen)

    resultados_api = iter([False, True])
    monkeypatch.setattr(client, "_esperar_api", lambda: next(resultados_api))

    resultado = client.conectar("user", "pass", str(tmp_path))

    assert resultado is None
    assert client.puerto == soulseek_client.DEFAULT_HTTP_PORT + 1
    assert procesos[0].killed is True
    assert procesos[1].killed is False


def test_conectar_returns_message_when_closing_flag_already_set(monkeypatch, tmp_path):
    client = soulseek_client.SoulseekClient()
    client._cerrando = True
    monkeypatch.setattr(soulseek_client, "_slskd_exe_path", lambda: tmp_path / "slskd.exe")

    def boom(*args, **kwargs):
        raise AssertionError("no debería arrancar ningún proceso si ya se está cerrando")

    monkeypatch.setattr(soulseek_client.subprocess, "Popen", boom)

    resultado = client.conectar("user", "pass", str(tmp_path))

    assert resultado == "Cierre en curso; conexión cancelada."


def test_conectar_kills_process_when_close_requested_during_api_wait(monkeypatch, tmp_path):
    client = soulseek_client.SoulseekClient()
    monkeypatch.setattr(soulseek_client, "_slskd_exe_path", lambda: tmp_path / "slskd.exe")

    fake_proc = FakeProcess(poll_result=None)
    monkeypatch.setattr(soulseek_client.subprocess, "Popen", lambda *a, **k: fake_proc)

    def esperar_api_y_cerrar():
        # Simula que cerrar() se dispara desde otro hilo justo cuando la
        # API acaba de responder.
        client._cerrando = True
        return True

    monkeypatch.setattr(client, "_esperar_api", esperar_api_y_cerrar)

    resultado = client.conectar("user", "pass", str(tmp_path))

    assert resultado == "Cierre en curso; conexión cancelada."
    assert fake_proc.killed is True
    assert client._proceso is None


def test_conectar_returns_message_when_no_port_is_free(monkeypatch, tmp_path):
    client = soulseek_client.SoulseekClient()
    monkeypatch.setattr(soulseek_client, "_slskd_exe_path", lambda: tmp_path / "slskd.exe")

    procesos = []

    def fake_popen(*args, **kwargs):
        proceso = FakeProcess(poll_result=None)
        procesos.append(proceso)
        return proceso

    monkeypatch.setattr(soulseek_client.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(client, "_esperar_api", lambda: False)

    resultado = client.conectar("user", "pass", str(tmp_path))

    assert resultado == "No se pudo arrancar slskd: no se encontró un puerto libre."
    assert len(procesos) == len(soulseek_client.PUERTO_RANGO)
    assert all(p.killed for p in procesos)


# ---------------------------------------------------------------------------
# _esperar_api()
# ---------------------------------------------------------------------------


def test_esperar_api_returns_true_as_soon_as_get_succeeds(monkeypatch):
    client = soulseek_client.SoulseekClient()
    monkeypatch.setattr(soulseek_client.time, "sleep", lambda s: None)
    llamadas = []

    def fake_get(path):
        llamadas.append(path)
        return {}

    client._get = fake_get

    assert client._esperar_api(intentos=5, espera=0) is True
    assert len(llamadas) == 1


def test_esperar_api_returns_false_after_exhausting_attempts(monkeypatch):
    client = soulseek_client.SoulseekClient()
    monkeypatch.setattr(soulseek_client.time, "sleep", lambda s: None)

    def fake_get(path):
        raise OSError("conexión rechazada")

    client._get = fake_get

    assert client._esperar_api(intentos=3, espera=0) is False


def test_esperar_api_stops_early_when_closing_flag_set(monkeypatch):
    client = soulseek_client.SoulseekClient()
    monkeypatch.setattr(soulseek_client.time, "sleep", lambda s: None)
    llamadas = []

    def fake_get(path):
        llamadas.append(path)
        client._cerrando = True
        raise OSError("todavía no arranca")

    client._get = fake_get

    assert client._esperar_api(intentos=10, espera=0) is False
    assert len(llamadas) == 1


# ---------------------------------------------------------------------------
# esta_logueado()
# ---------------------------------------------------------------------------


def test_esta_logueado_false_when_not_connected():
    client = soulseek_client.SoulseekClient()
    assert client.esta_logueado() is False


def test_esta_logueado_false_when_get_raises():
    client = soulseek_client.SoulseekClient()
    client._proceso = FakeProcess(poll_result=None)

    def fake_get(path):
        raise OSError("caído")

    client._get = fake_get

    assert client.esta_logueado() is False


def test_esta_logueado_true_when_server_reports_logged_in():
    client = soulseek_client.SoulseekClient()
    client._proceso = FakeProcess(poll_result=None)
    client._get = lambda path: {"server": {"isLoggedIn": True}}

    assert client.esta_logueado() is True


def test_esta_logueado_false_when_server_field_missing():
    client = soulseek_client.SoulseekClient()
    client._proceso = FakeProcess(poll_result=None)
    client._get = lambda path: {}

    assert client.esta_logueado() is False


# ---------------------------------------------------------------------------
# cerrar() / _esperar_fin()
# ---------------------------------------------------------------------------


def test_cerrar_noop_when_no_process():
    client = soulseek_client.SoulseekClient()
    client.cerrar()  # no debe lanzar
    assert client._cerrando is True


def test_cerrar_terminates_process_gracefully():
    client = soulseek_client.SoulseekClient()
    fake_proc = FakeProcess(poll_result=None)

    def poll():
        return 0 if fake_proc.terminated else None

    fake_proc.poll = poll
    client._proceso = fake_proc
    client.puerto = 5030

    client.cerrar()

    assert fake_proc.terminated is True
    assert fake_proc.killed is False
    assert client._proceso is None
    assert client.puerto is None


def test_cerrar_kills_process_when_it_does_not_terminate_in_time(monkeypatch):
    client = soulseek_client.SoulseekClient()
    fake_proc = FakeProcess(poll_result=None)  # nunca termina por sí solo
    client._proceso = fake_proc
    monkeypatch.setattr(soulseek_client.time, "sleep", lambda s: None)
    monkeypatch.setattr(soulseek_client, "_CIERRE_TIMEOUT_SEGUNDOS", 0)

    client.cerrar()

    assert fake_proc.killed is True


def test_esperar_fin_calls_on_wait_and_stops_when_process_ends(monkeypatch):
    client = soulseek_client.SoulseekClient()
    monkeypatch.setattr(soulseek_client.time, "sleep", lambda s: None)
    poll_secuencia = iter([None, None, 0, 0])

    class Proceso:
        def poll(self):
            return next(poll_secuencia)

    llamadas = []
    resultado = client._esperar_fin(
        Proceso(), time.monotonic() + 5, on_wait=lambda: llamadas.append(1)
    )

    assert resultado is True
    assert len(llamadas) == 2


# ---------------------------------------------------------------------------
# _request()/_get()/_post()/_delete()
# ---------------------------------------------------------------------------


def test_get_builds_url_with_puerto_and_parses_json(monkeypatch):
    client = soulseek_client.SoulseekClient()
    client.puerto = 5030
    peticiones = []

    def fake_urlopen(request, timeout=None):
        peticiones.append(request)
        return FakeHTTPResponse(b'{"ok": true}')

    monkeypatch.setattr(soulseek_client.urllib.request, "urlopen", fake_urlopen)

    resultado = client._get("/api/v0/application")

    assert resultado == {"ok": True}
    assert peticiones[0].get_full_url() == "http://127.0.0.1:5030/api/v0/application"
    assert peticiones[0].get_method() == "GET"


def test_post_sends_json_body_with_content_type_header(monkeypatch):
    client = soulseek_client.SoulseekClient()
    client.puerto = 5030
    peticiones = []

    def fake_urlopen(request, timeout=None):
        peticiones.append(request)
        return FakeHTTPResponse(b"")

    monkeypatch.setattr(soulseek_client.urllib.request, "urlopen", fake_urlopen)

    resultado = client._post("/api/v0/searches", {"searchText": "abc"})

    assert resultado is None  # cuerpo de respuesta vacío -> None
    peticion = peticiones[0]
    assert peticion.get_method() == "POST"
    assert peticion.data == json.dumps({"searchText": "abc"}).encode("utf-8")
    assert peticion.get_header("Content-type") == "application/json"


def test_delete_sends_delete_method(monkeypatch):
    client = soulseek_client.SoulseekClient()
    client.puerto = 5030
    peticiones = []

    def fake_urlopen(request, timeout=None):
        peticiones.append(request)
        return FakeHTTPResponse(b"null")

    monkeypatch.setattr(soulseek_client.urllib.request, "urlopen", fake_urlopen)

    resultado = client._delete("/api/v0/transfers/downloads/all/completed")

    assert resultado is None
    assert peticiones[0].get_method() == "DELETE"


# ---------------------------------------------------------------------------
# buscar()
# ---------------------------------------------------------------------------


def test_buscar_returns_immediately_when_first_poll_has_results():
    client = soulseek_client.SoulseekClient()
    client._post = lambda *a, **k: {"id": "sid"}
    client._get = lambda *a, **k: {
        "isComplete": True,
        "responses": [
            {
                "username": "peer1",
                "uploadSpeed": 1000,
                "queueLength": 2,
                "files": [
                    {"filename": "song.mp3", "size": 123, "bitRate": 320, "extension": "mp3"},
                ],
            }
        ],
    }

    resultado = client.buscar("test")

    assert resultado == [
        {
            "username": "peer1",
            "filename": "song.mp3",
            "size": 123,
            "bitrate": 320,
            "extension": "mp3",
            "upload_speed": 1000,
            "queue_length": 2,
        }
    ]


def test_buscar_fills_defaults_for_missing_optional_fields():
    client = soulseek_client.SoulseekClient()
    client._post = lambda *a, **k: {"id": "sid"}
    client._get = lambda *a, **k: {"isComplete": True, "responses": [{"files": [{}]}]}

    resultado = client.buscar("test")

    assert resultado == [
        {
            "username": "",
            "filename": "",
            "size": 0,
            "bitrate": None,
            "extension": "",
            "upload_speed": 0,
            "queue_length": 0,
        }
    ]


def test_buscar_keeps_polling_while_incomplete_without_results():
    client = soulseek_client.SoulseekClient()
    client._post = lambda *a, **k: {"id": "sid"}
    respuestas = iter(
        [
            {"isComplete": False, "responses": []},
            {"isComplete": False, "responses": []},
            {"isComplete": True, "responses": [{"files": [{"filename": "x"}]}]},
        ]
    )
    llamadas = []

    def fake_get(*a, **k):
        r = next(respuestas)
        llamadas.append(r)
        return r

    client._get = fake_get
    client._cancelar_esperas.wait = lambda t: False

    resultado = client.buscar("test")

    assert len(llamadas) == 3
    assert resultado[0]["filename"] == "x"


def test_buscar_stops_after_max_attempts_when_never_complete(monkeypatch):
    client = soulseek_client.SoulseekClient()
    monkeypatch.setattr(soulseek_client, "_BUSQUEDA_INTENTOS", 3)
    client._post = lambda *a, **k: {"id": "sid"}
    llamadas = []

    def fake_get(*a, **k):
        llamadas.append(1)
        return {"isComplete": False, "responses": []}

    client._get = fake_get
    client._cancelar_esperas.wait = lambda t: False

    resultado = client.buscar("test")

    assert resultado == []
    assert len(llamadas) == 3


# ---------------------------------------------------------------------------
# descargar()
# ---------------------------------------------------------------------------


def test_descargar_posts_expected_payload_and_returns_none():
    client = soulseek_client.SoulseekClient()
    llamadas = []
    client._post = lambda path, body: llamadas.append((path, body))

    resultado = client.descargar("user name", "song.mp3", 4096)

    assert resultado is None
    path, body = llamadas[0]
    assert path == "/api/v0/transfers/downloads/user%20name"
    assert body == [{"filename": "song.mp3", "size": 4096}]


def test_descargar_returns_error_message_when_post_fails():
    client = soulseek_client.SoulseekClient()

    def fake_post(*a, **k):
        raise RuntimeError("servidor caído")

    client._post = fake_post

    resultado = client.descargar("user", "song.mp3", 10)

    assert resultado == "No se pudo encolar la descarga: servidor caído"


# ---------------------------------------------------------------------------
# listar_descargas()
# ---------------------------------------------------------------------------


def test_listar_descargas_returns_empty_list_when_get_returns_none():
    client = soulseek_client.SoulseekClient()
    client._get = lambda *a, **k: None

    assert client.listar_descargas() == []


def test_listar_descargas_flattens_groups_and_maps_fields():
    client = soulseek_client.SoulseekClient()
    client._get = lambda *a, **k: [
        {
            "username": "peer1",
            "directories": [
                {
                    "files": [
                        {
                            "id": "f1",
                            "filename": "a.mp3",
                            "size": 10,
                            "state": "InProgress",
                            "percentComplete": 50.0,
                            "bytesTransferred": 5,
                            "averageSpeed": 100.0,
                        },
                    ]
                }
            ],
        }
    ]

    resultado = client.listar_descargas()

    assert resultado == [
        {
            "id": "f1",
            "username": "peer1",
            "filename": "a.mp3",
            "size": 10,
            "state": "InProgress",
            "percent_complete": 50.0,
            "bytes_transferred": 5,
            "average_speed": 100.0,
        }
    ]


def test_listar_descargas_uses_defaults_for_missing_fields():
    client = soulseek_client.SoulseekClient()
    client._get = lambda *a, **k: [{"directories": [{"files": [{}]}]}]

    resultado = client.listar_descargas()

    assert resultado == [
        {
            "id": None,
            "username": "",
            "filename": "",
            "size": 0,
            "state": "",
            "percent_complete": 0.0,
            "bytes_transferred": 0,
            "average_speed": 0.0,
        }
    ]


# ---------------------------------------------------------------------------
# cancelar_descarga() / limpiar_completadas()
# ---------------------------------------------------------------------------


def test_cancelar_descarga_calls_delete_with_encoded_username_and_remove_flag():
    client = soulseek_client.SoulseekClient()
    llamadas = []
    client._delete = lambda path: llamadas.append(path)

    client.cancelar_descarga("user/name", "abc123")

    assert llamadas == ["/api/v0/transfers/downloads/user%2Fname/abc123?remove=true"]


def test_limpiar_completadas_calls_delete_with_fixed_path():
    client = soulseek_client.SoulseekClient()
    llamadas = []
    client._delete = lambda path: llamadas.append(path)

    client.limpiar_completadas()

    assert llamadas == ["/api/v0/transfers/downloads/all/completed"]


# ---------------------------------------------------------------------------
# _extraer_zip_seguro() -- protección zip-slip / límite de tamaño
# ---------------------------------------------------------------------------


def test_extraer_zip_seguro_rejects_path_traversal_entries(tmp_path):
    destino = tmp_path / "slskd"
    destino.mkdir()
    zip_path = tmp_path / "malicioso.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("../evil.txt", "pwned")

    with zipfile.ZipFile(zip_path) as zf:
        with pytest.raises(RuntimeError, match="fuera de destino"):
            soulseek_client._extraer_zip_seguro(zf, destino)

    assert not (tmp_path / "evil.txt").exists()


def test_extraer_zip_seguro_rejects_oversized_content(monkeypatch, tmp_path):
    monkeypatch.setattr(soulseek_client, "MAX_SLSKD_EXTRACTED_BYTES", 5)
    destino = tmp_path / "slskd"
    destino.mkdir()
    zip_path = tmp_path / "grande.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("slskd.exe", "0123456789")

    with zipfile.ZipFile(zip_path) as zf:
        with pytest.raises(RuntimeError, match="tamaño descomprimido"):
            soulseek_client._extraer_zip_seguro(zf, destino)


def test_extraer_zip_seguro_extracts_normal_entries(tmp_path):
    destino = tmp_path / "slskd"
    destino.mkdir()
    zip_path = tmp_path / "ok.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("slskd.exe", "contenido")

    with zipfile.ZipFile(zip_path) as zf:
        soulseek_client._extraer_zip_seguro(zf, destino)

    assert (destino / "slskd.exe").read_text() == "contenido"


# ---------------------------------------------------------------------------
# ensure_slskd() -- solo las rutas de error/caché que no requieren red real
# ---------------------------------------------------------------------------


def test_ensure_slskd_returns_cached_exe_when_hash_matches(monkeypatch, tmp_path):
    exe = tmp_path / "slskd.exe"
    exe.write_bytes(b"contenido-binario")
    hash_path = exe.with_suffix(".exe.sha256")
    hash_path.write_text(hashlib.sha256(exe.read_bytes()).hexdigest(), encoding="ascii")

    monkeypatch.setattr(soulseek_client, "_slskd_exe_path", lambda: exe)

    def boom(*a, **k):
        raise AssertionError("no debería llamar a la red si el hash coincide")

    monkeypatch.setattr(soulseek_client.urllib.request, "urlopen", boom)

    assert soulseek_client.ensure_slskd() == str(exe)


def test_ensure_slskd_raises_when_release_has_no_win_x64_asset(monkeypatch):
    monkeypatch.setattr(soulseek_client, "_slskd_exe_path", lambda: None)
    release = {"assets": [{"name": "slskd-1.0.0-linux-x64.zip"}]}

    def fake_urlopen(request, timeout=None):
        return FakeHTTPResponse(json.dumps(release).encode("utf-8"))

    monkeypatch.setattr(soulseek_client.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(RuntimeError, match="win-x64"):
        soulseek_client.ensure_slskd()


def test_ensure_slskd_raises_when_digest_is_missing_or_malformed(monkeypatch):
    monkeypatch.setattr(soulseek_client, "_slskd_exe_path", lambda: None)
    release = {
        "assets": [
            {"name": "slskd-1.0.0-win-x64.zip", "browser_download_url": "http://x/slskd.zip"}
        ]
    }

    def fake_urlopen(request, timeout=None):
        return FakeHTTPResponse(json.dumps(release).encode("utf-8"))

    monkeypatch.setattr(soulseek_client.urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(RuntimeError, match="SHA-256"):
        soulseek_client.ensure_slskd()
