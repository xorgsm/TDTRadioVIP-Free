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
