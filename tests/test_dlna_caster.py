"""
Cobertura de core/dlna_caster.py: validación de la descripción de
dispositivo (_describe_device) frente a respuestas SSDP/XML hostiles,
descubrimiento (discover_dlna_devices / DLNADiscoveryWorker) y el
control SOAP de DLNASession.

Ninguna prueba toca la red: requests.get/requests.post y _ssdp_search se
sustituyen con monkeypatch. DLNADiscoveryWorker es un QThread, pero se
prueba llamando a .run() directamente (nunca .start()), igual que en
tests/test_caster.py.
"""
from unittest.mock import Mock

import pytest
import requests

from core import dlna_caster
from core.dlna_caster import DLNADevice, DLNADiscoveryWorker, DLNASession

DEVICE_IP = "192.168.1.50"
LOCATION = f"http://{DEVICE_IP}:8080/description.xml"


def _description_xml(control_url="/upnp/control/AVTransport1",
                      service_type="urn:schemas-upnp-org:service:AVTransport:1",
                      friendly="Salón TV"):
    return (
        '<?xml version="1.0"?>'
        '<root xmlns="urn:schemas-upnp-org:device-1-0"><device>'
        f"<friendlyName>{friendly}</friendlyName>"
        "<serviceList><service>"
        f"<serviceType>{service_type}</serviceType>"
        f"<controlURL>{control_url}</controlURL>"
        "</service></serviceList>"
        "</device></root>"
    ).encode("utf-8")


class _FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, chunk_size):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i:i + chunk_size]


@pytest.fixture
def fake_get(monkeypatch):
    """Sustituye requests.get por uno que devuelve el XML indicado."""
    def install(body: bytes):
        get = Mock(return_value=_FakeResponse(body))
        monkeypatch.setattr(dlna_caster.requests, "get", get)
        return get
    return install


# --------------------------------------------------------------------------
# _describe_device(): validación de LOCATION
# --------------------------------------------------------------------------

def test_describe_device_rejects_location_on_other_host_without_request(fake_get):
    get = fake_get(_description_xml())

    device = dlna_caster._describe_device("http://10.0.0.1/description.xml", DEVICE_IP)

    assert device is None
    get.assert_not_called()


def test_describe_device_rejects_non_http_location_without_request(fake_get):
    get = fake_get(_description_xml())

    device = dlna_caster._describe_device(f"ftp://{DEVICE_IP}/description.xml", DEVICE_IP)

    assert device is None
    get.assert_not_called()


def test_describe_device_rejects_oversized_description(fake_get, monkeypatch):
    monkeypatch.setattr(dlna_caster, "_MAX_DESCRIPTION_BYTES", 100)
    fake_get(_description_xml() + b" " * 200)

    assert dlna_caster._describe_device(LOCATION, DEVICE_IP) is None


def test_describe_device_returns_none_on_invalid_xml(fake_get):
    fake_get(b"<no es xml")

    assert dlna_caster._describe_device(LOCATION, DEVICE_IP) is None


def test_describe_device_returns_none_on_http_error(monkeypatch):
    monkeypatch.setattr(
        dlna_caster.requests, "get",
        Mock(side_effect=requests.ConnectionError("sin conexión")),
    )

    assert dlna_caster._describe_device(LOCATION, DEVICE_IP) is None


def test_describe_device_returns_none_without_avtransport(fake_get):
    fake_get(_description_xml(service_type="urn:schemas-upnp-org:service:RenderingControl:1"))

    assert dlna_caster._describe_device(LOCATION, DEVICE_IP) is None


# --------------------------------------------------------------------------
# _describe_device(): validación de controlURL (SSRF)
# --------------------------------------------------------------------------

def test_describe_device_joins_relative_control_url(fake_get):
    fake_get(_description_xml(control_url="/upnp/control/AVTransport1"))

    device = dlna_caster._describe_device(LOCATION, DEVICE_IP)

    assert device is not None
    assert device.name == "Salón TV"
    assert device.location == LOCATION
    assert device.control_url == f"http://{DEVICE_IP}:8080/upnp/control/AVTransport1"


def test_describe_device_accepts_absolute_control_url_on_same_host(fake_get):
    fake_get(_description_xml(control_url=f"http://{DEVICE_IP}:9197/ctl"))

    device = dlna_caster._describe_device(LOCATION, DEVICE_IP)

    assert device is not None
    assert device.control_url == f"http://{DEVICE_IP}:9197/ctl"


@pytest.mark.parametrize("hostile_control_url", [
    "http://192.168.1.1/cgi-bin/admin",       # otro host de la LAN (router)
    "http://127.0.0.1:5000/api",              # servicio local del propio PC
    "//10.0.0.1/ctl",                         # URL relativa al esquema
    f"file://{DEVICE_IP}/C:/Windows/win.ini",  # esquema no HTTP
])
def test_describe_device_rejects_control_url_outside_device(fake_get, hostile_control_url):
    fake_get(_description_xml(control_url=hostile_control_url))

    assert dlna_caster._describe_device(LOCATION, DEVICE_IP) is None


def test_describe_device_uses_default_name_when_missing(fake_get):
    fake_get(_description_xml(friendly=""))

    device = dlna_caster._describe_device(LOCATION, DEVICE_IP)

    assert device is not None
    assert device.name == "TV DLNA"


# --------------------------------------------------------------------------
# discover_dlna_devices() / DLNADiscoveryWorker
# --------------------------------------------------------------------------

def test_discover_skips_duplicate_locations_and_invalid_devices(monkeypatch):
    monkeypatch.setattr(dlna_caster, "_ssdp_search", lambda timeout: [
        (LOCATION, DEVICE_IP),
        (LOCATION, DEVICE_IP),
        ("http://192.168.1.60/desc.xml", "192.168.1.60"),
    ])
    good = DLNADevice("Salón TV", LOCATION, "http://x/ctl")
    describe = Mock(side_effect=[good, None])
    monkeypatch.setattr(dlna_caster, "_describe_device", describe)

    assert dlna_caster.discover_dlna_devices(timeout=0.1) == [good]
    assert describe.call_count == 2


def test_discovery_worker_emits_names_and_finds_device_by_name(monkeypatch):
    device = DLNADevice("Salón TV", LOCATION, "http://x/ctl")
    monkeypatch.setattr(dlna_caster, "discover_dlna_devices", lambda timeout: [device])
    worker = DLNADiscoveryWorker()
    received = []
    worker.found.connect(received.append)

    worker.run()

    assert received == [["Salón TV"]]
    assert worker.device_by_name("Salón TV") is device
    assert worker.device_by_name("Otra") is None


def test_discovery_worker_emits_empty_list_on_failure(monkeypatch):
    monkeypatch.setattr(
        dlna_caster, "discover_dlna_devices", Mock(side_effect=OSError("red caída"))
    )
    worker = DLNADiscoveryWorker()
    received = []
    worker.found.connect(received.append)

    worker.run()

    assert received == [[]]
    assert worker.devices == []


# --------------------------------------------------------------------------
# DLNASession
# --------------------------------------------------------------------------

@pytest.fixture
def session_with_device(monkeypatch):
    post = Mock()
    monkeypatch.setattr(dlna_caster.requests, "post", post)
    session = DLNASession()
    session.connect(DLNADevice("Salón TV", LOCATION, f"http://{DEVICE_IP}:8080/ctl"))
    yield session, post
    session.file_server.stop()


def test_cast_url_without_device_raises():
    session = DLNASession()
    with pytest.raises(RuntimeError):
        session.cast_url("http://radio/stream.mp3", "audio/mpeg")


def test_cast_url_sends_set_uri_then_play_with_escaped_url(session_with_device):
    session, post = session_with_device

    session.cast_url("http://radio/stream.mp3?a=1&b=2", "audio/mpeg", title="<Radio>")

    assert post.call_count == 2
    first, second = post.call_args_list
    assert first.args[0] == f"http://{DEVICE_IP}:8080/ctl"
    assert "SetAVTransportURI" in first.kwargs["headers"]["SOAPAction"]
    body = first.kwargs["data"].decode("utf-8")
    assert "<CurrentURI>http://radio/stream.mp3?a=1&amp;b=2</CurrentURI>" in body
    assert "&lt;Radio&gt;" in body and "<Radio>" not in body
    assert "object.item.audioItem" in body
    assert "Play" in second.kwargs["headers"]["SOAPAction"]


def test_cast_url_translates_request_errors(session_with_device):
    session, post = session_with_device
    post.side_effect = requests.HTTPError("500")

    with pytest.raises(RuntimeError, match="rechazó"):
        session.cast_url("http://tv/live.m3u8", "application/x-mpegURL")


def test_disconnect_sends_stop_and_clears_device_even_if_stop_fails(session_with_device):
    session, post = session_with_device
    post.side_effect = requests.ConnectionError("apagada")

    session.disconnect()

    assert "Stop" in post.call_args.kwargs["headers"]["SOAPAction"]
    assert session.device is None
    assert session.device_name is None
