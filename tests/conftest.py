import pytest


@pytest.fixture
def trusted_update_key(monkeypatch):
    """Instala la clave publica de prueba como clave de actualizaciones."""
    import _signing
    from core import update_signature

    monkeypatch.setattr(
        update_signature, "UPDATE_PUBLIC_KEY_N_B64", _signing.public_modulus_b64()
    )
