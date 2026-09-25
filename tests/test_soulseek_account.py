"""
Cobertura de core/soulseek_account.py: cuenta de Soulseek del perfil
activo (usuario/contraseña en JSON dentro de la carpeta del perfil).
"""
import json

import pytest

from core import soulseek_account


@pytest.fixture
def profile_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(soulseek_account, "get_profile_data_dir", lambda: tmp_path)
    return tmp_path


def _write_raw(profile_dir, data):
    (profile_dir / soulseek_account.ACCOUNT_FILE).write_text(json.dumps(data), encoding="utf-8")


def test_save_and_load_account_roundtrip(profile_dir):
    soulseek_account.save_account("usuario", "clave secreta")

    assert soulseek_account.load_account() == {"username": "usuario", "password": "clave secreta"}


def test_load_account_without_file_returns_none(profile_dir):
    assert soulseek_account.load_account() is None


@pytest.mark.parametrize("data", [
    ["no", "es", "dict"],
    {"username": "u"},
    {"username": "", "password": "p"},
    {"username": "u", "password": ""},
    {"username": 12345, "password": "p"},
    {"username": "u", "password": ["p"]},
])
def test_load_account_returns_none_for_incomplete_or_malformed_data(profile_dir, data):
    _write_raw(profile_dir, data)

    assert soulseek_account.load_account() is None


def test_load_account_ignores_extra_fields(profile_dir):
    _write_raw(profile_dir, {"username": "u", "password": "p", "otro": 1})

    assert soulseek_account.load_account() == {"username": "u", "password": "p"}
