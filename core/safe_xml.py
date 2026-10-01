"""Parseo de XML que viene de fuera (EPG, feeds de podcasts, dispositivos DLNA).

``xml.etree`` expande las entidades que declara el propio documento, así que
un "billion laughs" (entidades anidadas) agota la memoria con unos pocos KB.
Ningún XMLTV, RSS ni descripción UPnP legítimo declara entidades, así que se
rechazan; el DOCTYPE con DTD externo, habitual en XMLTV, sigue funcionando
porque ``xml.etree`` no descarga DTDs.
"""
import xml.etree.ElementTree as ET
from xml.parsers import expat


class _PrologScanned(Exception):
    """Se llegó al elemento raíz sin ver declaraciones de entidades."""


def _reject_entity_declaration(entity_name, *_args) -> None:
    raise ET.ParseError(f"Declaración de entidad no permitida: {entity_name}")


def _stop_at_root(_name, _attrs) -> None:
    raise _PrologScanned


def _reject_entities(content: bytes) -> None:
    """Escanea solo el prólogo con expat y lanza ET.ParseError ante entidades.

    Las entidades solo pueden declararse en el DOCTYPE, antes del elemento
    raíz, así que el escaneo se detiene en cuanto empieza el raíz y no
    recorre el documento entero. Se usa el manejador de expat, no un filtro
    de bytes, para que valga con cualquier codificación (UTF-16 incluida).
    El XML mal formado se deja a ``ET.fromstring``, que lo informa.
    """
    parser = expat.ParserCreate()
    parser.EntityDeclHandler = _reject_entity_declaration
    parser.StartElementHandler = _stop_at_root
    try:
        parser.Parse(content, True)
    except (_PrologScanned, expat.ExpatError):
        pass


def parse_xml_safely(content: bytes) -> ET.Element:
    """Como ``ET.fromstring``, pero lanza ``ET.ParseError`` ante entidades."""
    _reject_entities(content)
    return ET.fromstring(content)
