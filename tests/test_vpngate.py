import base64

import pytest

from core import vpngate


def _ovpn_b64(body="client\ndev tun\nproto udp\nremote vpn.example.com 1194\n"):
    return base64.b64encode(body.encode("utf-8")).decode("ascii")


def _fake_response(text, status_ok=True):
    class _Resp:
        def __init__(self):
            self.text = text

        def raise_for_status(self):
            if not status_ok:
                raise Exception("HTTP 500")

    return _Resp()


def _csv(rows):
    header = (
        "#HostName,IP,Score,Ping,Speed,CountryLong,CountryShort,NumVpnSessions,"
        "Uptime,TotalUsers,TotalTraffic,LogType,Operator,Message,"
        "OpenVPN_ConfigData_Base64"
    )
    lines = ["*vpn_servers", header, *rows, "*"]
    return "\r\n".join(lines)


def test_fetch_servers_parses_country_and_decodes_ovpn():
    row = ",".join([
        "public-vpn-1", "1.2.3.4", "1000", "20", "5000000", "Japan", "JP",
        "10", "123456", "999", "888777", "2weeks", "Operator", "",
        _ovpn_b64(),
    ])
    text = _csv([row])
    servers = vpngate.fetch_servers(request_get=lambda url, timeout: _fake_response(text))
    assert len(servers) == 1
    server = servers[0]
    assert server["hostname"] == "public-vpn-1"
    assert server["country_long"] == "Japan"
    assert server["country_short"] == "JP"
    assert server["ping"] == 20
    assert server["speed"] == 5000000
    assert server["score"] == 1000
    assert "remote vpn.example.com 1194" in server["ovpn_text"]


def test_fetch_servers_sorted_by_score_descending():
    low = ",".join([
        "low", "1.1.1.1", "100", "20", "1000", "France", "FR", "1", "1", "1", "1",
        "2weeks", "Op", "", _ovpn_b64(),
    ])
    high = ",".join([
        "high", "2.2.2.2", "900", "20", "1000", "Spain", "ES", "1", "1", "1", "1",
        "2weeks", "Op", "", _ovpn_b64(),
    ])
    text = _csv([low, high])
    servers = vpngate.fetch_servers(request_get=lambda url, timeout: _fake_response(text))
    assert [s["hostname"] for s in servers] == ["high", "low"]


def test_fetch_servers_skips_rows_with_missing_or_bad_config():
    missing_b64 = ",".join([
        "no-config", "1.1.1.1", "100", "20", "1000", "France", "FR", "1", "1", "1", "1",
        "2weeks", "Op", "", "",
    ])
    good = ",".join([
        "good", "2.2.2.2", "900", "20", "1000", "Spain", "ES", "1", "1", "1", "1",
        "2weeks", "Op", "", _ovpn_b64(),
    ])
    text = _csv([missing_b64, good])
    servers = vpngate.fetch_servers(request_get=lambda url, timeout: _fake_response(text))
    assert [s["hostname"] for s in servers] == ["good"]


def test_fetch_servers_raises_on_empty_response():
    with pytest.raises(vpngate.VpnGateError, match="vacía"):
        vpngate.fetch_servers(request_get=lambda url, timeout: _fake_response(""))


def test_fetch_servers_raises_when_request_fails():
    def _raise(url, timeout):
        raise Exception("sin red")

    with pytest.raises(vpngate.VpnGateError, match="No se pudo descargar"):
        vpngate.fetch_servers(request_get=_raise)
