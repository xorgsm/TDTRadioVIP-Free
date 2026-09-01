from player import vlc_player


class _Equalizer:
    def __init__(self):
        self.released = False

    def set_preamp(self, value):
        return None

    def set_amp_at_index(self, value, index):
        return None

    def release(self):
        self.released = True


class _FailingMediaPlayer:
    def set_equalizer(self, equalizer):
        raise RuntimeError("libVLC rejected the equalizer")


def test_failed_equalizer_apply_releases_new_native_object(monkeypatch):
    equalizer = _Equalizer()
    monkeypatch.setattr(vlc_player, "vlc", type("Vlc", (), {"AudioEqualizer": lambda: equalizer}))
    player = type(
        "PlayerState",
        (),
        {
            "_aplicar_equalizer": vlc_player.VLCPlayer._aplicar_equalizer,
            "_liberar_eq_object": vlc_player.VLCPlayer._liberar_eq_object,
        },
    )()
    player._eq_enabled = True
    player._eq_preamp = 0.0
    player._eq_bands = [1.0]
    player._eq_object = None
    player.media_player = _FailingMediaPlayer()

    player._aplicar_equalizer()

    assert equalizer.released is True
    assert player._eq_object is None
