"""
Módulo `vlc` simulado para los tests de player/vlc_player.py y
player/audio_preview.py -- ningún test necesita VLC instalado. Imita lo
justo de python-vlc: Instance, MediaPlayer, Media, gestores de eventos y
la lista enlazada C de descripciones de pistas.
"""
import ctypes
from types import SimpleNamespace


# --------------------------------------------------------------------------

class _TrackDescription(ctypes.Structure):
    pass


_TrackDescription._fields_ = [
    ("id", ctypes.c_int),
    ("name", ctypes.c_char_p),
    ("next", ctypes.POINTER(_TrackDescription)),
]


def track_list(*tracks):
    """Lista enlazada C como la que devuelve libVLC: [(id, nombre|None), ...]."""
    nodos = [_TrackDescription(tid, nombre.encode() if nombre else None) for tid, nombre in tracks]
    for actual, siguiente in zip(nodos, nodos[1:]):
        actual.next = ctypes.pointer(siguiente)
    cabeza = ctypes.pointer(nodos[0]) if nodos else ctypes.POINTER(_TrackDescription)()
    cabeza._keepalive = nodos
    return cabeza


class FakeEventManager:
    def __init__(self):
        self.attached = {}
        self.detached = []

    def event_attach(self, event_type, callback):
        self.attached[event_type] = callback

    def event_detach(self, event_type):
        self.detached.append(event_type)
        self.attached.pop(event_type, None)


class FakeMedia:
    def __init__(self, url):
        self.url = url
        self.released = False
        self.events = FakeEventManager()
        self.now_playing = None
        self.stats = {"input_bitrate": 0.5, "demux_bitrate": None}

    def event_manager(self):
        return self.events

    def get_meta(self, _key):
        return self.now_playing

    def get_stats(self):
        return self.stats

    def release(self):
        self.released = True


class FakeMediaPlayer:
    def __init__(self):
        self.events = FakeEventManager()
        self.media = None
        self.playing = False
        self.released = False
        self.volume = 100
        self.muted = 0
        self.hwnd = None
        self.scale = None
        self.time = 10_000
        self.length = 60_000
        self.seekable = True
        self.video_track = 0
        self.audio_track = 1
        self.spu = -1
        self.equalizer = None
        self.stop_error = None
        self.audio_descriptions = track_list((-1, "Desactivar"), (1, "Español"), (2, None))
        self.video_descriptions = track_list((-1, "Desactivar"), (5, "Vídeo"))
        self.spu_descriptions = track_list()

    def event_manager(self):
        return self.events

    def set_media(self, media):
        self.media = media

    def play(self):
        self.playing = True

    def pause(self):
        self.playing = False

    def set_pause(self, paused):
        self.playing = not paused

    def stop(self):
        if self.stop_error is not None:
            raise self.stop_error
        self.playing = False

    def is_playing(self):
        return 1 if self.playing else 0

    def release(self):
        self.released = True

    def audio_get_volume(self):
        return self.volume

    def audio_set_volume(self, value):
        self.volume = value

    def audio_get_mute(self):
        return self.muted

    def audio_set_mute(self, muted):
        self.muted = 1 if muted else 0

    def set_hwnd(self, hwnd):
        self.hwnd = hwnd

    set_nsobject = set_xwindow = set_hwnd

    def video_set_scale(self, scale):
        self.scale = scale

    def video_get_size(self, _num):
        return (1920, 1080)

    def audio_get_track_count(self):
        return 3

    def video_get_spu_count(self):
        return -1

    def get_state(self):
        return "State.Playing"

    def is_seekable(self):
        return self.seekable

    def get_time(self):
        return self.time

    def get_length(self):
        return self.length

    def set_time(self, value):
        self.time = value

    def audio_get_track_description(self):
        return self.audio_descriptions

    def video_get_track_description(self):
        return self.video_descriptions

    def video_get_spu_description(self):
        return self.spu_descriptions

    def audio_get_track(self):
        return self.audio_track

    def audio_set_track(self, track):
        self.audio_track = track

    def video_get_spu(self):
        return self.spu

    def video_set_spu(self, track):
        self.spu = track

    def video_set_track(self, track):
        self.video_track = track

    def set_equalizer(self, equalizer):
        self.equalizer = equalizer


class FakeInstance:
    def __init__(self, args):
        self.args = args
        self.players = []
        self.medias = []
        self.released = False

    def media_player_new(self):
        player = FakeMediaPlayer()
        self.players.append(player)
        return player

    def media_new(self, url):
        media = FakeMedia(url)
        self.medias.append(media)
        return media

    def release(self):
        self.released = True


def fake_vlc_module():
    modulo = SimpleNamespace(
        EventType=SimpleNamespace(
            MediaPlayerEncounteredError="error",
            MediaPlayerEndReached="end",
            MediaPlayerVout="vout",
            MediaMetaChanged="meta",
        ),
        Meta=SimpleNamespace(NowPlaying="now_playing"),
        instances=[],
        released_lists=[],
    )

    def instance(args):
        inst = FakeInstance(args)
        modulo.instances.append(inst)
        return inst

    modulo.Instance = instance
    modulo.libvlc_track_description_list_release = modulo.released_lists.append
    return modulo
