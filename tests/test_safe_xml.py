"""
parse_xml_safely: el XML de EPG, podcasts y dispositivos DLNA viene de fuera.

xml.etree expande entidades definidas en el propio documento, asi que un
"billion laughs" (entidades anidadas) agota la memoria con unos pocos KB.
Ningun XMLTV, RSS ni descripcion UPnP legitimo declara entidades; el DOCTYPE
con DTD externo (<!DOCTYPE tv SYSTEM "xmltv.dtd">) si es habitual en XMLTV y
debe seguir funcionando.
"""
import xml.etree.ElementTree as ET

import pytest

from core.safe_xml import parse_xml_safely

BILLION_LAUGHS = b"""<?xml version="1.0"?>
<!DOCTYPE lolz [
  <!ENTITY lol "lol">
  <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
  <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
]>
<lolz>&lol3;</lolz>"""


def test_parsea_un_xml_normal():
    root = parse_xml_safely(b"<tv><channel id='a'/></tv>")
    assert root.tag == "tv"
    assert root.find("channel").get("id") == "a"


def test_admite_doctype_con_dtd_externo_habitual_en_xmltv():
    xml = b'<?xml version="1.0"?><!DOCTYPE tv SYSTEM "xmltv.dtd"><tv><channel id="a"/></tv>'
    assert parse_xml_safely(xml).tag == "tv"


def test_rechaza_declaraciones_de_entidades():
    with pytest.raises(ET.ParseError):
        parse_xml_safely(BILLION_LAUGHS)


def test_rechaza_entidades_tambien_en_utf16():
    """Un filtro por bytes ASCII no vería '<!ENTITY' en un documento UTF-16."""
    with pytest.raises(ET.ParseError):
        parse_xml_safely(BILLION_LAUGHS.decode("utf-8").encode("utf-16"))


def test_xml_roto_sigue_lanzando_parse_error():
    with pytest.raises(ET.ParseError):
        parse_xml_safely(b"<tv><programme")
