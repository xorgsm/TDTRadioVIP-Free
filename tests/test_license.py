"""
Tests de core/license.py: verificación RSA de códigos de activación V2,
generación/caché del hardware ID y persistencia de la activación.

validate_code() usa una clave pública RSA-2048 fija (_RSA_N/_RSA_E) cuya
clave privada NO vive en este repo (keygen.py, fuera del proyecto
empaquetado) -- no se puede firmar nada real desde un test. Por eso estos
tests sustituyen _RSA_N/_RSA_E por un par de claves RSA-2048 propio,
generado una sola vez con semilla fija (ver
scratchpad/gen_test_rsa.py) para poder firmar códigos de prueba con la
misma aritmética (PKCS#1 v1.5 sobre SHA-256, sin librerías externas) que
usa el propio módulo. Nunca se toca ni se imprime la clave real de
producción.

Nota: `core/license.py` convive con `core/license.cp312-win_amd64.pyd`
(compilado con setup_license.py -- ver ese archivo). Python prefiere la
extensión compilada sobre la fuente cuando ambas existen, así que
`from core import license` en este proceso importa el .pyd, no el .py
que se lee/edita aquí -- es decir, estos tests corren contra el binario
que de verdad se distribuye, tal y como toca para un módulo de
seguridad, no contra una copia de lectura fácil.
"""
import hashlib
import json

import pytest

from core import license as license_mod

# Clave de PRUEBA generada una sola vez (semilla fija) -- no tiene relación
# alguna con la clave pública real embebida en core/license.py.
_TEST_RSA_N = 21897499503695299539181634046318660078030502508506247625436128704278733291031017571627173142798110175007553068823424738912427626549089623410292172782427842482510366270148492065358414831498124605571238055169039560808682309415941317848052590353609561733033862921997714900721608106355967790423320119688190535309775655875497855723290585846460767270098786978484349025293889771233288781983174665736747785863024731241012450467445975679992155333245492113226914668542809213102160906892337985945999339950728536682224352447557917954986254055621342067054948285760773703707365622799520296135117472185856294075972534582232703838477
_TEST_RSA_D = 7869627932473799381209775038420180978956199178827954442862766671832354322041801682477605154833512198482580792987138911997870025910717730445131933801433128980431918714021200750955746288757119319392394676494139017283777018076409751121888134345462349626900019430273161405872957805956972540211490589728183341900669474757080666931408924987716556091433123267378197489002870118738756018754884207309313139768190364574830168357418217082882191775931583596045489073961591038142305526576983494637048464823483500195911644056821200112025988908047406653425098183164030733788051188643895496637476423759287541994440954311204725968477
_TEST_RSA_E = 65537

_SHA256_DER_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")


def _sign_hardware_id(hardware_id: str) -> str:
    """Firma hardware_id con la clave PRIVADA de prueba, replicando el
    esquema PKCS#1 v1.5 exacto que validate_code() espera verificar."""
    clean = hardware_id.replace("-", "").replace(" ", "").upper()
    digest_info = _SHA256_DER_PREFIX + hashlib.sha256(clean.encode("ascii")).digest()
    padded = b"\x00\x01" + b"\xff" * (256 - len(digest_info) - 3) + b"\x00" + digest_info
    signature_int = pow(int.from_bytes(padded, "big"), _TEST_RSA_D, _TEST_RSA_N)
    signature = signature_int.to_bytes(256, "big")
    return "V2." + signature.hex().upper()


@pytest.fixture(autouse=True)
def _use_test_keypair(monkeypatch):
    """Todas las pruebas de este archivo verifican contra la clave de
    prueba, nunca contra la clave pública real de producción."""
    monkeypatch.setattr(license_mod, "_RSA_N", _TEST_RSA_N)
    monkeypatch.setattr(license_mod, "_RSA_E", _TEST_RSA_E)


@pytest.fixture(autouse=True)
def _clear_hardware_id_cache():
    """generate_hardware_id() está decorado con @lru_cache(maxsize=1) a
    nivel de módulo -- sin limpiarlo, el resultado de un test contaminaría
    a todos los siguientes en el mismo proceso de pytest."""
    license_mod.generate_hardware_id.cache_clear()
    yield
    license_mod.generate_hardware_id.cache_clear()


# ── validate_code() ─────────────────────────────────────────────────────────

def test_validate_code_accepts_a_correctly_signed_code():
    hw = "AAAA-BBBB-CCCC-DDDD"
    code = _sign_hardware_id(hw)
    assert license_mod.validate_code(hw, code) is True


def test_validate_code_is_case_insensitive_on_the_v2_prefix_and_hex():
    hw = "AAAA-BBBB-CCCC-DDDD"
    code = _sign_hardware_id(hw)
    assert license_mod.validate_code(hw, "v2." + code[3:].lower()) is True


def test_validate_code_ignores_dashes_in_the_signature_block():
    """validate_code() quita los guiones antes de convertir a bytes
    (`code[3:].replace("-", "")`) -- debe validar igual si el código
    que pega el usuario viene formateado en bloques con guiones, sea
    cual sea el tamaño de bloque."""
    hw = "AAAA-BBBB-CCCC-DDDD"
    code = _sign_hardware_id(hw)
    prefix, hexpart = code.split(".", 1)
    dashed = prefix + "." + "-".join(hexpart[i:i + 5] for i in range(0, len(hexpart), 5))
    assert license_mod.validate_code(hw, dashed) is True


def test_validate_code_normalizes_hardware_id_dashes_case_and_spaces():
    """El hardware_id se normaliza (sin guiones/espacios, mayúsculas)
    antes de hashear -- variantes de formato del mismo ID deben validar
    igual contra el mismo código."""
    code = _sign_hardware_id("AAAA-BBBB-CCCC-DDDD")
    assert license_mod.validate_code("aaaa bbbb-cccc dddd", code) is True
    assert license_mod.validate_code("AAAABBBBCCCCDDDD", code) is True


def test_validate_code_rejects_code_for_a_different_hardware_id():
    code = _sign_hardware_id("AAAA-BBBB-CCCC-DDDD")
    assert license_mod.validate_code("1111-2222-3333-4444", code) is False


def test_validate_code_rejects_a_tampered_signature():
    hw = "AAAA-BBBB-CCCC-DDDD"
    code = _sign_hardware_id(hw)
    prefix, hexpart = code.split(".", 1)
    flipped_byte = format(int(hexpart[:2], 16) ^ 0xFF, "02X")
    tampered = prefix + "." + flipped_byte + hexpart[2:]
    assert license_mod.validate_code(hw, tampered) is False


@pytest.mark.parametrize(
    "code",
    [
        "",
        "not-a-code",
        "V1." + "AB" * 256,             # prefijo de versión equivocado
        "V2." + "ZZ" * 256,             # hex inválido
        "V2." + "AB" * 100,             # firma demasiado corta (no 256 bytes)
        "V2." + "AB" * 300,             # firma demasiado larga
    ],
)
def test_validate_code_rejects_malformed_input(code):
    assert license_mod.validate_code("AAAA-BBBB-CCCC-DDDD", code) is False


@pytest.mark.parametrize("bad_code", [None, 123, 12.5, [], {}])
def test_validate_code_raises_typeerror_on_non_string_code(bad_code):
    """core/license.py se distribuye compilado a .pyd con Cython
    (ver setup_license.py) precisamente para dificultar la ingeniería
    inversa del binario -- y python prefiere ese .pyd sobre el .py
    fuente cuando ambos coexisten (confirmado: license_mod.__file__
    apunta al .pyd). El .py fuente hace `isinstance(code, str)` como
    primera línea de defensa, pero en el binario compilado la
    anotación `code: str` se aplica como un tipo estático de Cython:
    un valor no-str ni siquiera llega a esa comprobación, se rechaza
    antes con un TypeError. En la práctica esto no es alcanzable desde
    la UI (save_activation()/is_activated() solo le pasan strings, y
    is_activated() ya filtra con isinstance antes de llamar aquí), así
    que se documenta como comportamiento real en vez de forzar que el
    test finja el comportamiento -- más laxo -- del .py sin compilar."""
    with pytest.raises(TypeError):
        license_mod.validate_code("AAAA-BBBB-CCCC-DDDD", bad_code)


# ── generate_hardware_id() ──────────────────────────────────────────────────

def test_generate_hardware_id_uses_disk_cache_without_running_subprocesses(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(license_mod, "get_app_data_dir", lambda: tmp_path)
    (tmp_path / license_mod.HARDWARE_ID_CACHE_FILE).write_text(
        json.dumps({"hardware_id": "CACHED-VALUE"}), encoding="utf-8"
    )

    def _boom():
        raise AssertionError("no debería recalcularse si hay caché en disco")

    monkeypatch.setattr(license_mod, "_get_disk_serial", _boom)
    monkeypatch.setattr(license_mod, "_get_board_uuid", _boom)
    monkeypatch.setattr(license_mod, "_get_cpu_id", _boom)
    monkeypatch.setattr(license_mod, "_get_machine_guid", _boom)

    assert license_mod.generate_hardware_id() == "CACHED-VALUE"


def test_generate_hardware_id_computes_and_persists_when_no_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(license_mod, "get_app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(license_mod, "_get_disk_serial", lambda: "DISK1")
    monkeypatch.setattr(license_mod, "_get_board_uuid", lambda: "BOARD1")
    monkeypatch.setattr(license_mod, "_get_cpu_id", lambda: "CPU1")
    monkeypatch.setattr(license_mod, "_get_machine_guid", lambda: "GUID1")

    hw = license_mod.generate_hardware_id()

    expected_digest = hashlib.sha256(b"DISK1|BOARD1|CPU1|GUID1").hexdigest()[:16].upper()
    expected = "-".join(expected_digest[i:i + 4] for i in range(0, 16, 4))
    assert hw == expected

    cached = json.loads(
        (tmp_path / license_mod.HARDWARE_ID_CACHE_FILE).read_text(encoding="utf-8")
    )
    assert cached["hardware_id"] == hw


def test_generate_hardware_id_survives_a_read_only_cache_directory(monkeypatch, tmp_path):
    """_save_cached_hardware_id() no debe romper el arranque si el disco
    está lleno o no hay permiso de escritura -- se recalcularía en el
    siguiente arranque en vez de fallar este."""
    monkeypatch.setattr(license_mod, "get_app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(license_mod, "_get_disk_serial", lambda: "DISK1")
    monkeypatch.setattr(license_mod, "_get_board_uuid", lambda: "BOARD1")
    monkeypatch.setattr(license_mod, "_get_cpu_id", lambda: "CPU1")
    monkeypatch.setattr(license_mod, "_get_machine_guid", lambda: "GUID1")

    def _raise_oserror(*_args, **_kwargs):
        raise OSError("disco lleno")

    monkeypatch.setattr(license_mod, "write_json_atomic", _raise_oserror)

    hw = license_mod.generate_hardware_id()
    assert hw  # no lanza, devuelve el ID calculado igualmente


@pytest.mark.parametrize("bad_content", ["{not json", json.dumps([1, 2, 3]), json.dumps("just a string")])
def test_generate_hardware_id_recomputes_when_the_disk_cache_is_corrupt_or_not_a_dict(
    monkeypatch, tmp_path, bad_content
):
    """hardware_id_cache.json es precisamente la superficie que el
    propio docstring de generate_hardware_id() admite como manipulable
    a mano por quien tenga acceso de escritura a la carpeta de datos
    (revisión de seguridad, ver Indice/hallazgos) -- confirma que un
    archivo corrupto o con una forma inesperada degrada recalculando en
    vez de reventar el arranque."""
    monkeypatch.setattr(license_mod, "get_app_data_dir", lambda: tmp_path)
    (tmp_path / license_mod.HARDWARE_ID_CACHE_FILE).write_text(bad_content, encoding="utf-8")
    monkeypatch.setattr(license_mod, "_get_disk_serial", lambda: "DISK1")
    monkeypatch.setattr(license_mod, "_get_board_uuid", lambda: "BOARD1")
    monkeypatch.setattr(license_mod, "_get_cpu_id", lambda: "CPU1")
    monkeypatch.setattr(license_mod, "_get_machine_guid", lambda: "GUID1")

    hw = license_mod.generate_hardware_id()

    expected_digest = hashlib.sha256(b"DISK1|BOARD1|CPU1|GUID1").hexdigest()[:16].upper()
    expected = "-".join(expected_digest[i:i + 4] for i in range(0, 16, 4))
    assert hw == expected


# ── load_activation() / save_activation() / is_activated() ────────────────

def test_load_activation_when_no_file_exists(monkeypatch, tmp_path):
    monkeypatch.setattr(license_mod, "get_app_data_dir", lambda: tmp_path)
    assert license_mod.load_activation() == {"activated": False, "code": ""}


def test_load_activation_rejects_corrupt_json(monkeypatch, tmp_path):
    monkeypatch.setattr(license_mod, "get_app_data_dir", lambda: tmp_path)
    (tmp_path / license_mod.LICENSE_FILE).write_text("{not json", encoding="utf-8")
    assert license_mod.load_activation() == {"activated": False, "code": ""}


@pytest.mark.parametrize("top_level_json", [[1, 2, 3], "just a string", 42, True])
def test_load_activation_rejects_valid_json_that_is_not_a_dict(monkeypatch, tmp_path, top_level_json):
    """json.loads() puede parsear con éxito y aun así no darnos un dict
    -- distinto del caso de JSON sintácticamente inválido de arriba."""
    monkeypatch.setattr(license_mod, "get_app_data_dir", lambda: tmp_path)
    (tmp_path / license_mod.LICENSE_FILE).write_text(json.dumps(top_level_json), encoding="utf-8")
    assert license_mod.load_activation() == {"activated": False, "code": ""}


@pytest.mark.parametrize("bad_code", [123, None, [], {}])
def test_load_activation_rejects_a_non_string_code(monkeypatch, tmp_path, bad_code):
    """Un license.json manipulado a mano con 'code' no-string no debe
    llegar a validate_code() (usa str.replace) y reventar el arranque."""
    monkeypatch.setattr(license_mod, "get_app_data_dir", lambda: tmp_path)
    (tmp_path / license_mod.LICENSE_FILE).write_text(
        json.dumps({"activated": True, "code": bad_code}), encoding="utf-8"
    )
    assert license_mod.load_activation() == {"activated": False, "code": ""}


def test_save_activation_persists_a_valid_code(monkeypatch, tmp_path):
    monkeypatch.setattr(license_mod, "get_app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(license_mod, "_get_disk_serial", lambda: "DISK1")
    monkeypatch.setattr(license_mod, "_get_board_uuid", lambda: "BOARD1")
    monkeypatch.setattr(license_mod, "_get_cpu_id", lambda: "CPU1")
    monkeypatch.setattr(license_mod, "_get_machine_guid", lambda: "GUID1")

    hw = license_mod.generate_hardware_id()
    code = _sign_hardware_id(hw)

    assert license_mod.save_activation(code) is True
    assert license_mod.load_activation() == {"activated": True, "code": code.upper()}


def test_save_activation_rejects_an_invalid_code(monkeypatch, tmp_path):
    monkeypatch.setattr(license_mod, "get_app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(license_mod, "_get_disk_serial", lambda: "DISK1")
    monkeypatch.setattr(license_mod, "_get_board_uuid", lambda: "BOARD1")
    monkeypatch.setattr(license_mod, "_get_cpu_id", lambda: "CPU1")
    monkeypatch.setattr(license_mod, "_get_machine_guid", lambda: "GUID1")

    assert license_mod.save_activation("V2." + "AB" * 256) is False
    assert not (tmp_path / license_mod.LICENSE_FILE).exists()


def test_save_activation_returns_false_when_it_cannot_write_to_disk(monkeypatch, tmp_path):
    """Un código válido que no se puede persistir (disco lleno, permisos,
    antivirus) debe reportarse como False -- si no, is_activated() no
    encontraría el archivo tras reiniciar y pediría el código otra vez,
    como si la activación nunca hubiera pasado."""
    monkeypatch.setattr(license_mod, "get_app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(license_mod, "_get_disk_serial", lambda: "DISK1")
    monkeypatch.setattr(license_mod, "_get_board_uuid", lambda: "BOARD1")
    monkeypatch.setattr(license_mod, "_get_cpu_id", lambda: "CPU1")
    monkeypatch.setattr(license_mod, "_get_machine_guid", lambda: "GUID1")

    hw = license_mod.generate_hardware_id()
    code = _sign_hardware_id(hw)

    def _raise_oserror(*_args, **_kwargs):
        raise OSError("disco lleno")

    monkeypatch.setattr(license_mod, "write_json_atomic", _raise_oserror)

    assert license_mod.save_activation(code) is False


def test_is_activated_true_for_a_valid_saved_code(monkeypatch, tmp_path):
    monkeypatch.setattr(license_mod, "get_app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(license_mod, "_get_disk_serial", lambda: "DISK1")
    monkeypatch.setattr(license_mod, "_get_board_uuid", lambda: "BOARD1")
    monkeypatch.setattr(license_mod, "_get_cpu_id", lambda: "CPU1")
    monkeypatch.setattr(license_mod, "_get_machine_guid", lambda: "GUID1")

    hw = license_mod.generate_hardware_id()
    license_mod.save_activation(_sign_hardware_id(hw))

    assert license_mod.is_activated() is True


def test_is_activated_false_when_never_activated(monkeypatch, tmp_path):
    monkeypatch.setattr(license_mod, "get_app_data_dir", lambda: tmp_path)
    assert license_mod.is_activated() is False


def test_is_activated_false_when_the_license_file_was_copied_to_another_pc(
    monkeypatch, tmp_path
):
    """is_activated() revalida el código guardado contra el hardware
    ACTUAL -- copiar license.json a otro PC con hardware distinto no
    debe activar la app ahí.

    Cada "PC" usa su propia carpeta de datos (tmp_path/pc_a, tmp_path/pc_b):
    generate_hardware_id() cachea en disco (hardware_id_cache.json) y
    deliberadamente sigue usando ese ID cacheado aunque el hardware
    real cambie (ver su docstring) -- reusar la misma carpeta para
    "las dos PCs" solo probaría esa caché, no la revalidación real que
    hace is_activated()."""
    pc_a, pc_b = tmp_path / "pc_a", tmp_path / "pc_b"
    pc_a.mkdir()
    pc_b.mkdir()

    monkeypatch.setattr(license_mod, "get_app_data_dir", lambda: pc_a)
    monkeypatch.setattr(license_mod, "_get_disk_serial", lambda: "DISK1")
    monkeypatch.setattr(license_mod, "_get_board_uuid", lambda: "BOARD1")
    monkeypatch.setattr(license_mod, "_get_cpu_id", lambda: "CPU1")
    monkeypatch.setattr(license_mod, "_get_machine_guid", lambda: "GUID1")
    hw_a = license_mod.generate_hardware_id()
    license_mod.save_activation(_sign_hardware_id(hw_a))

    # "Copiar license.json a otro PC": mismo código firmado, hardware distinto.
    (pc_b / license_mod.LICENSE_FILE).write_text(
        (pc_a / license_mod.LICENSE_FILE).read_text(encoding="utf-8"), encoding="utf-8"
    )
    license_mod.generate_hardware_id.cache_clear()
    monkeypatch.setattr(license_mod, "get_app_data_dir", lambda: pc_b)
    monkeypatch.setattr(license_mod, "_get_disk_serial", lambda: "DISK2-OTHER-PC")

    assert license_mod.is_activated() is False


def test_is_activated_false_when_activated_flag_is_false(monkeypatch, tmp_path):
    monkeypatch.setattr(license_mod, "get_app_data_dir", lambda: tmp_path)
    monkeypatch.setattr(license_mod, "_get_disk_serial", lambda: "DISK1")
    monkeypatch.setattr(license_mod, "_get_board_uuid", lambda: "BOARD1")
    monkeypatch.setattr(license_mod, "_get_cpu_id", lambda: "CPU1")
    monkeypatch.setattr(license_mod, "_get_machine_guid", lambda: "GUID1")

    hw = license_mod.generate_hardware_id()
    (tmp_path / license_mod.LICENSE_FILE).write_text(
        json.dumps({"activated": False, "code": _sign_hardware_id(hw)}), encoding="utf-8"
    )

    assert license_mod.is_activated() is False
