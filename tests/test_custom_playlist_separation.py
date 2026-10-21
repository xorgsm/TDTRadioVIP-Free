"""La biblioteca importada de TV y Radio debe persistirse por separado."""

from core import channels, config, radio


def test_custom_tv_and_radio_lists_use_independent_files(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "get_app_data_dir", lambda: tmp_path)
    config._profile_dir_for.cache_clear()
    try:
        tv_channel = channels.Channel("TV propia", "https://tv.example/stream")
        radio_station = radio.Station("Radio propia", "https://radio.example/stream")

        channels.add_custom_channels([tv_channel])
        radio.add_custom_stations([radio_station])

        assert [item.name for item in channels.load_custom_channels()] == ["TV propia"]
        assert [item.name for item in radio.load_custom_stations()] == ["Radio propia"]
        assert (tmp_path / channels.CUSTOM_FILE).exists()
        assert (tmp_path / radio.CUSTOM_FILE).exists()
    finally:
        config._profile_dir_for.cache_clear()
