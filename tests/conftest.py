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
