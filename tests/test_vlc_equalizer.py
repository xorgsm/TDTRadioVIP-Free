from player import vlc_equalizer, vlc_player
from player.vlc_equalizer import VLCEqualizer


class _NativeEqualizer:
    def __init__(self):
        self.released = False
        self.preamp = None
        self.bands = {}

    def set_preamp(self, value):
        self.preamp = value

    def set_amp_at_index(self, value, index):
        self.bands[index] = value

    def release(self):
        self.released = True


class _MediaPlayer:
    def __init__(self, reject=False):
        self._reject = reject
        self.equalizer = "untouched"

    def set_equalizer(self, equalizer):
        if self._reject:
            raise RuntimeError("libVLC rejected the equalizer")
        self.equalizer = equalizer


def _patch_native_factory(monkeypatch, module=vlc_equalizer):
    created = []

    def factory():
        native = _NativeEqualizer()
        created.append(native)
        return native

    monkeypatch.setattr(module, "vlc", type("Vlc", (), {"AudioEqualizer": staticmethod(factory)}))
    return created


def test_apply_to_does_nothing_before_configure():
    eq = VLCEqualizer()
    player = _MediaPlayer()

    eq.apply_to(player)

    assert player.equalizer == "untouched"


def test_apply_to_builds_native_equalizer_from_configured_values(monkeypatch):
    created = _patch_native_factory(monkeypatch)
    eq = VLCEqualizer()
    eq.configure(preamp=3.5, bands=[1.0, -2.0])
    player = _MediaPlayer()

    eq.apply_to(player)

    assert player.equalizer is created[0]
    assert created[0].preamp == 3.5
    assert created[0].bands == {0: 1.0, 1: -2.0}


def test_reapplying_releases_the_previous_native_object(monkeypatch):
    created = _patch_native_factory(monkeypatch)
    eq = VLCEqualizer()
    eq.configure(0.0, [1.0])
    player = _MediaPlayer()
    eq.apply_to(player)

    eq.apply_to(player)  # e.g. after media_player recreation on channel change

    assert created[0].released is True
    assert created[1].released is False


def test_failed_apply_releases_the_new_native_object(monkeypatch):
    created = _patch_native_factory(monkeypatch)
    eq = VLCEqualizer()
    eq.configure(0.0, [1.0])
    player = _MediaPlayer(reject=True)

    eq.apply_to(player)

    assert created[0].released is True


def test_clear_detaches_and_releases_the_native_object(monkeypatch):
    created = _patch_native_factory(monkeypatch)
    eq = VLCEqualizer()
    eq.configure(0.0, [1.0])
    player = _MediaPlayer()
    eq.apply_to(player)

    eq.clear(player)

    assert player.equalizer is None
    assert created[0].released is True


def test_apply_to_is_noop_after_clear_until_reconfigured(monkeypatch):
    _patch_native_factory(monkeypatch)
    eq = VLCEqualizer()
    eq.configure(0.0, [1.0])
    player = _MediaPlayer()
    eq.apply_to(player)
    eq.clear(player)

    player2 = _MediaPlayer()
    eq.apply_to(player2)

    assert player2.equalizer == "untouched"


def test_release_frees_the_native_object_without_touching_media_player(monkeypatch):
    created = _patch_native_factory(monkeypatch)
    eq = VLCEqualizer()
    eq.configure(0.0, [1.0])
    player = _MediaPlayer()
    eq.apply_to(player)

    eq.release()

    assert created[0].released is True
    assert player.equalizer is created[0]  # release() never touches media_player


def test_vlcplayer_set_equalizer_delegates_to_the_equalizer_collaborator(monkeypatch):
    created = _patch_native_factory(monkeypatch)
    player = type(
        "PlayerState",
        (),
        {
            "set_equalizer": vlc_player.VLCPlayer.set_equalizer,
            "clear_equalizer": vlc_player.VLCPlayer.clear_equalizer,
        },
    )()
    player._equalizer = VLCEqualizer()
    player.media_player = _MediaPlayer()

    player.set_equalizer(2.0, [1.0, 1.0])
    assert player.media_player.equalizer is created[0]

    player.clear_equalizer()
    assert player.media_player.equalizer is None
    assert created[0].released is True
