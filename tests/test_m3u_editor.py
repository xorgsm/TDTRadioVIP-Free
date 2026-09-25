from core.channels import parse_m3u


_DUPLICATED_PLAYLIST = """#EXTM3U
#EXTINF:-1 group-title="Noticias",Canal Uno
https://example.test/uno
#EXTINF:-1 group-title="Noticias",Canal Uno
https://example.test/uno-alternativo
"""


def test_editor_can_keep_duplicates_for_review():
    channels = parse_m3u(_DUPLICATED_PLAYLIST, deduplicate=False)

    assert [channel.name for channel in channels] == ["Canal Uno", "Canal Uno"]


def test_regular_import_keeps_its_existing_deduplication():
    channels = parse_m3u(_DUPLICATED_PLAYLIST)

    assert len(channels) == 1
    assert channels[0].alternate_urls == ["https://example.test/uno-alternativo"]


def test_editor_loads_ansi_playlist_without_losing_accents(tmp_path):
    from ui.dialogs.m3u_editor import M3UEditorDialog

    ruta = tmp_path / "lista.m3u"
    ruta.write_bytes('#EXTINF:-1,Canción España\nhttps://es\n'.encode("cp1252"))

    canales = M3UEditorDialog._fetch_and_parse_source(str(ruta))

    assert [c.name for c in canales] == ["Canción España"]
