from core.channels import Channel, dedupe_channels
from core.radio import Station, dedupe_stations


def test_tv_duplicates_become_fallback_urls():
    result = dedupe_channels([
        Channel("Canal Uno", "https://primary.test"),
        Channel(" canal uno ", "https://backup.test"),
        Channel("Canal Uno", "https://backup.test"),
    ])

    assert len(result) == 1
    assert result[0].url == "https://primary.test"
    assert result[0].alternate_urls == ["https://backup.test"]


def test_radio_duplicates_become_fallback_urls():
    result = dedupe_stations([
        Station("Radio Uno", "https://primary.test"),
        Station("RADIO UNO", "https://backup.test"),
    ])

    assert len(result) == 1
    assert result[0].alternate_urls == ["https://backup.test"]
