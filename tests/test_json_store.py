"""
Almacenes JSON: lectura tolerante, escritura atómica y reemplazo transaccional.

`core/json_store.py` es donde se persisten perfiles, favoritos, ajustes e
historial, y no tenía ninguna prueba. Un fallo aquí no da error visible: deja
un JSON a medias o pierde datos del usuario en el siguiente arranque. Estos
tests fijan las tres garantías que el módulo promete en sus docstrings:

1. `read_json` nunca propaga: devuelve el default ante fichero ausente,
   corrupto o ilegible.
2. `write_json_atomic` nunca expone un JSON parcial: o el contenido viejo o
   el nuevo, jamás medio escrito, y no deja temporales sueltos.
3. `replace_json_files_atomically` es todo-o-nada: si falla a mitad, revierte
   los ficheros ya sustituidos a su contenido previo.
"""
import json
import os
from pathlib import Path

import pytest

from core.json_store import (
    read_json,
    replace_json_files_atomically,
    write_json_atomic,
)


# --------------------------------------------------------------------------
# read_json
# --------------------------------------------------------------------------

def test_read_json_devuelve_el_contenido(tmp_path):
    destino = tmp_path / "datos.json"
    destino.write_text('{"canal": "La 1"}', encoding="utf-8")
    assert read_json(destino, {}) == {"canal": "La 1"}


def test_read_json_devuelve_default_si_no_existe(tmp_path):
    centinela = {"vacio": True}
    assert read_json(tmp_path / "no_existe.json", centinela) is centinela


def test_read_json_devuelve_default_si_esta_corrupto(tmp_path):
    """Un JSON truncado (corte de luz a media escritura) no debe reventar."""
    destino = tmp_path / "corrupto.json"
    destino.write_text('{"canal": "La 1"', encoding="utf-8")  # sin cerrar
    assert read_json(destino, []) == []


def test_read_json_devuelve_default_si_no_es_utf8(tmp_path):
    destino = tmp_path / "binario.json"
    destino.write_bytes(b"\xff\xfe\x00\x01 no soy texto")
    assert read_json(destino, {}) == {}


def test_read_json_aparta_el_fichero_corrupto_para_no_perder_los_datos(tmp_path):
    """Si se devolviera solo el default, la siguiente escritura pisaría el
    JSON corrupto y el usuario perdería favoritos/ajustes sin copia alguna."""
    destino = tmp_path / "favoritos.json"
    contenido = '{"canal": "La 1"'  # sin cerrar
    destino.write_text(contenido, encoding="utf-8")

    assert read_json(destino, []) == []

    assert not destino.exists()
    copias = list(tmp_path.glob("favoritos.json.corrupt*"))
    assert len(copias) == 1
    assert copias[0].read_text(encoding="utf-8") == contenido


def test_read_json_corrupto_repetido_no_sobrescribe_copias_anteriores(tmp_path):
    destino = tmp_path / "ajustes.json"
    for texto in ('{"a": 1', '{"b": 2'):
        destino.write_text(texto, encoding="utf-8")
        read_json(destino, {})

    copias = sorted(c.read_text(encoding="utf-8") for c in tmp_path.glob("ajustes.json.corrupt*"))
    assert copias == ['{"a": 1', '{"b": 2']


def test_read_json_aparta_tambien_el_fichero_que_no_es_utf8(tmp_path):
    destino = tmp_path / "binario.json"
    destino.write_bytes(b"\xff\xfe\x00\x01 no soy texto")
    assert read_json(destino, {}) == {}
    assert len(list(tmp_path.glob("binario.json.corrupt*"))) == 1


def test_read_json_devuelve_default_aunque_no_pueda_apartar_el_corrupto(tmp_path, monkeypatch):
    destino = tmp_path / "ajustes.json"
    destino.write_text("{", encoding="utf-8")

    def _falla(self, target):
        raise OSError("archivo en uso")

    monkeypatch.setattr(type(destino), "replace", _falla)
    assert read_json(destino, {"ok": True}) == {"ok": True}


def test_read_json_devuelve_default_si_es_un_directorio(tmp_path):
    """Ruta que existe pero no se puede abrir como fichero -> OSError."""
    carpeta = tmp_path / "soy_carpeta.json"
    carpeta.mkdir()
    assert read_json(carpeta, "default") == "default"


# --------------------------------------------------------------------------
# write_json_atomic
# --------------------------------------------------------------------------

def test_write_json_atomic_escribe_y_relee(tmp_path):
    destino = tmp_path / "ajustes.json"
    valor = {"tema": "dark", "acento": "#d4af37", "volumen": 80}
    write_json_atomic(destino, valor)
    assert json.loads(destino.read_text(encoding="utf-8")) == valor


def test_write_json_atomic_crea_directorios_intermedios(tmp_path):
    destino = tmp_path / "perfiles" / "xor" / "favoritos.json"
    write_json_atomic(destino, [1, 2, 3])
    assert destino.exists()
    assert read_json(destino, None) == [1, 2, 3]


def test_write_json_atomic_conserva_acentos_sin_escapar(tmp_path):
    """ensure_ascii=False: los nombres de canal deben quedar legibles."""
    destino = tmp_path / "canal.json"
    write_json_atomic(destino, {"nombre": "Televisión Española ñ"})
    crudo = destino.read_text(encoding="utf-8")
    assert "Televisión Española ñ" in crudo
    assert "\\u" not in crudo


def test_write_json_atomic_no_deja_temporales(tmp_path):
    destino = tmp_path / "ajustes.json"
    write_json_atomic(destino, {"a": 1})
    sobrantes = [p.name for p in tmp_path.iterdir() if p.name != "ajustes.json"]
    assert not sobrantes, f"temporales sin limpiar: {sobrantes}"


def test_write_json_atomic_conserva_el_original_si_falla_serializar(tmp_path):
    """
    La garantía central: si el valor no es serializable, el fichero previo
    debe quedar intacto, no truncado a medias.
    """
    destino = tmp_path / "ajustes.json"
    write_json_atomic(destino, {"bueno": 1})

    class NoSerializable:
        pass

    with pytest.raises(TypeError):
        write_json_atomic(destino, {"malo": NoSerializable()})

    assert read_json(destino, None) == {"bueno": 1}
    sobrantes = [p.name for p in tmp_path.iterdir() if p.name != "ajustes.json"]
    assert not sobrantes, f"temporales sin limpiar tras el fallo: {sobrantes}"


def test_write_json_atomic_sobrescribe_contenido_mayor_por_menor(tmp_path):
    """
    Sin escritura atómica, pasar de un fichero largo a uno corto deja cola del
    anterior. Con os.replace no puede ocurrir.
    """
    destino = tmp_path / "lista.json"
    write_json_atomic(destino, [{"n": i} for i in range(500)])
    write_json_atomic(destino, [])
    assert destino.read_text(encoding="utf-8") == "[]"


# --------------------------------------------------------------------------
# replace_json_files_atomically
# --------------------------------------------------------------------------

def test_reemplazo_transaccional_escribe_todos(tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    replace_json_files_atomically({a: {"x": 1}, b: {"y": 2}})
    assert read_json(a, None) == {"x": 1}
    assert read_json(b, None) == {"y": 2}


def test_reemplazo_transaccional_no_deja_artefactos(tmp_path):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    replace_json_files_atomically({a: [1], b: [2]})
    nombres = sorted(p.name for p in tmp_path.iterdir())
    assert nombres == ["a.json", "b.json"], f"artefactos sueltos: {nombres}"


def test_reemplazo_transaccional_revierte_si_falla_a_mitad(tmp_path, monkeypatch):
    """
    Núcleo del rollback: con dos ficheros ya existentes, si el segundo
    os.replace falla, el primero debe volver a su contenido anterior. Sin
    rollback quedaría un estado mixto (a nuevo, b viejo).
    """
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    write_json_atomic(a, {"version": "vieja"})
    write_json_atomic(b, {"version": "vieja"})

    real_replace = os.replace
    llamadas = {"n": 0}

    def replace_que_falla_la_segunda(src, dst, *args, **kwargs):
        # Solo cuenta los replace hacia los destinos .json (no los del rollback).
        if str(dst).endswith(".json"):
            llamadas["n"] += 1
            if llamadas["n"] == 2:
                raise OSError("fallo simulado a mitad de la transacción")
        return real_replace(src, dst, *args, **kwargs)

    monkeypatch.setattr(os, "replace", replace_que_falla_la_segunda)

    with pytest.raises(OSError):
        replace_json_files_atomically({a: {"version": "nueva"}, b: {"version": "nueva"}})

    monkeypatch.undo()

    assert read_json(a, None) == {"version": "vieja"}, "a no se revirtió"
    assert read_json(b, None) == {"version": "vieja"}, "b no debería haber cambiado"


def test_reemplazo_transaccional_borra_los_nuevos_al_revertir(tmp_path, monkeypatch):
    """
    Si un destino no existía antes, el rollback debe eliminarlo: no puede
    quedarse un fichero a medio crear de una transacción abortada.
    """
    nuevo_a = tmp_path / "nuevo_a.json"
    nuevo_b = tmp_path / "nuevo_b.json"

    real_replace = os.replace
    llamadas = {"n": 0}

    def replace_que_falla_la_segunda(src, dst, *args, **kwargs):
        if str(dst).endswith(".json"):
            llamadas["n"] += 1
            if llamadas["n"] == 2:
                raise OSError("fallo simulado")
        return real_replace(src, dst, *args, **kwargs)

    monkeypatch.setattr(os, "replace", replace_que_falla_la_segunda)

    with pytest.raises(OSError):
        replace_json_files_atomically({nuevo_a: [1], nuevo_b: [2]})

    monkeypatch.undo()

    assert not nuevo_a.exists(), "el destino nuevo debió borrarse en el rollback"
    assert not nuevo_b.exists()


def test_reemplazo_transaccional_aborta_sin_tocar_nada_si_un_valor_no_serializa(tmp_path):
    """
    El fallo ocurre en la fase de preparación: ningún destino debe haberse
    modificado todavía.
    """
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    write_json_atomic(a, {"version": "vieja"})
    write_json_atomic(b, {"version": "vieja"})

    class NoSerializable:
        pass

    with pytest.raises(TypeError):
        replace_json_files_atomically({a: {"version": "nueva"}, b: NoSerializable()})

    assert read_json(a, None) == {"version": "vieja"}
    assert read_json(b, None) == {"version": "vieja"}
    sobrantes = sorted(p.name for p in tmp_path.iterdir())
    assert sobrantes == ["a.json", "b.json"], f"artefactos sueltos: {sobrantes}"


def test_reemplazo_transaccional_acepta_rutas_en_texto(tmp_path):
    """La firma admite Mapping[Path, object] pero normaliza con Path()."""
    destino = tmp_path / "a.json"
    replace_json_files_atomically({str(destino): {"ok": True}})
    assert read_json(destino, None) == {"ok": True}


def test_reemplazo_transaccional_con_mapa_vacio_no_hace_nada(tmp_path):
    replace_json_files_atomically({})
    assert list(tmp_path.iterdir()) == []


def test_reemplazo_transaccional_crea_directorios_intermedios(tmp_path):
    destino = tmp_path / "perfiles" / "xor" / "historial.json"
    replace_json_files_atomically({destino: [{"visto": "La 1"}]})
    assert read_json(destino, None) == [{"visto": "La 1"}]


# --------------------------------------------------------------------------
# Ida y vuelta
# --------------------------------------------------------------------------

@pytest.mark.parametrize("valor", [
    {},
    [],
    {"anidado": {"lista": [1, 2, {"x": None}]}},
    [{"nombre": "Canal ñ", "url": "http://x/y?a=1&b=2"}],
    {"unicode": "日本語 · emoji 🎵 · acentos áéíóú"},
    {"numeros": [0, -1, 3.5, 1e10]},
    {"booleanos": [True, False, None]},
])
def test_ida_y_vuelta_conserva_el_valor(tmp_path, valor):
    destino = tmp_path / "v.json"
    write_json_atomic(destino, valor)
    assert read_json(destino, object()) == valor
