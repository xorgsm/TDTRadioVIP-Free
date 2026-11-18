import pytest


@pytest.fixture
def trusted_update_key(monkeypatch):
    """Instala la clave publica de prueba como clave de actualizaciones."""
    import _signing
    from core import update_signature

    monkeypatch.setattr(
        update_signature, "UPDATE_PUBLIC_KEY_N_B64", _signing.public_modulus_b64()
    )


@pytest.fixture(autouse=True)
def _offline_dns(monkeypatch):
    """Los tests no deben depender de DNS real: todo host resuelve a una
    IP pública de documentación salvo que el test fije otra cosa."""
    import ipaddress

    from core import net_safety

    monkeypatch.setattr(
        net_safety, "_resolve", lambda host: [ipaddress.ip_address("93.184.216.34")]
    )


@pytest.fixture(autouse=True)
def _mockable_pinned_get(request, monkeypatch):
    """El pinning de DNS abre su propia Session y se saltaría los tests que
    parchean `requests.get`: aquí delega en `requests.get` (resuelto al llamar)
    salvo en test_dns_pinning, que ejercita la conexión fijada de verdad."""
    if request.module.__name__.endswith("test_dns_pinning"):
        return
    import requests

    from core import http_limits

    monkeypatch.setattr(
        http_limits, "_pinned_get",
        lambda resolver: lambda url, **kwargs: requests.get(url, **kwargs),
    )
