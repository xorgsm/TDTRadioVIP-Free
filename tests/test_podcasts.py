"""
Cobertura de core/podcasts.py: feeds suscritos (persistencia JSON), parseo
de episodios desde RSS (con caché en disco, igual patrón que core/epg.py) y
el worker de descarga de un episodio.

El worker es un QThread pero se prueba llamando a .run() directamente (nunca
.start()), igual que en tests/test_downloader.py: las señales se emiten de
forma síncrona en el hilo del test, sin necesitar un QApplication.
"""
import json

import pytest
import requests

from core import podcasts
from core.podcasts import Episode, EpisodeDownloadWorker, PodcastFeed


# --------------------------------------------------------------------------
# Feeds suscritos
# --------------------------------------------------------------------------

def test_load_feeds_returns_empty_list_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(podcasts, "get_app_data_dir", lambda: tmp_path)
    assert podcasts.load_feeds() == []


def test_load_feeds_returns_empty_list_on_corrupt_json(tmp_path, monkeypatch):
    monkeypatch.setattr(podcasts, "get_app_data_dir", lambda: tmp_path)
    (tmp_path / podcasts.FEEDS_FILE).write_text("{no es json", encoding="utf-8")
    assert podcasts.load_feeds() == []


def test_load_feeds_returns_empty_list_when_top_level_is_not_a_list(tmp_path, monkeypatch):
    monkeypatch.setattr(podcasts, "get_app_data_dir", lambda: tmp_path)
    (tmp_path / podcasts.FEEDS_FILE).write_text(json.dumps({"no": "es una lista"}), encoding="utf-8")
    assert podcasts.load_feeds() == []


def test_load_feeds_skips_entries_that_are_not_dicts_or_have_bad_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(podcasts, "get_app_data_dir", lambda: tmp_path)
    data = [
        {"name": "Bueno", "url": "https://feed.example/good.xml"},
        "no es un dict",
        {"name": "Con campo de más", "url": "https://feed.example/bad.xml", "campo_extra": 1},
    ]
    (tmp_path / podcasts.FEEDS_FILE).write_text(json.dumps(data), encoding="utf-8")

    feeds = podcasts.load_feeds()

    assert [f.name for f in feeds] == ["Bueno"]


def test_add_feed_persists_and_avoids_duplicate_urls(tmp_path, monkeypatch):
    monkeypatch.setattr(podcasts, "get_app_data_dir", lambda: tmp_path)

    podcasts.add_feed("Mi Podcast", "https://feed.example/show.xml")
    feeds = podcasts.add_feed("Otro nombre", "https://feed.example/show.xml")

    assert [f.url for f in feeds] == ["https://feed.example/show.xml"]
    assert (tmp_path / podcasts.FEEDS_FILE).exists()
    # La copia en disco sobrevive a una nueva carga.
    assert [f.name for f in podcasts.load_feeds()] == ["Mi Podcast"]


def test_add_feed_falls_back_to_url_as_name_when_name_is_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(podcasts, "get_app_data_dir", lambda: tmp_path)
    feeds = podcasts.add_feed("", "https://feed.example/show.xml")
    assert feeds[0].name == "https://feed.example/show.xml"


def test_remove_feed_removes_only_the_matching_url(tmp_path, monkeypatch):
    monkeypatch.setattr(podcasts, "get_app_data_dir", lambda: tmp_path)
    podcasts.add_feed("Uno", "https://feed.example/one.xml")
    podcasts.add_feed("Dos", "https://feed.example/two.xml")

    remaining = podcasts.remove_feed("https://feed.example/one.xml")

    assert [f.name for f in remaining] == ["Dos"]
    assert [f.name for f in podcasts.load_feeds()] == ["Dos"]


# --------------------------------------------------------------------------
# fetch_episodes: parseo de RSS
# --------------------------------------------------------------------------

RSS_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
<channel>
<title>Show de prueba</title>
{items}
</channel>
</rss>"""


def _rss(items):
    return RSS_TEMPLATE.format(items="\n".join(items))


def _item(title="Episodio", audio_url="https://cdn.example/ep1.mp3", pub_date="Mon, 01 Jan 2024 10:00:00 +0000",
          description="Descripción", duration="30:00", include_enclosure=True):
    enclosure = f'<enclosure url="{audio_url}" type="audio/mpeg" />' if include_enclosure else ""
    return f"""<item>
<title>{title}</title>
<pubDate>{pub_date}</pubDate>
<description>{description}</description>
<itunes:duration>{duration}</itunes:duration>
{enclosure}
</item>"""


class _FakeResponse:
    def __init__(self, content, status_ok=True):
        self.content = content.encode("utf-8") if isinstance(content, str) else content
        self._status_ok = status_ok
        self.headers = {}

    def iter_content(self, chunk_size=1):
        return iter([self.content])

    def close(self):
        pass

    def raise_for_status(self):
        if not self._status_ok:
            raise requests.HTTPError("HTTP 500")


def test_fetch_episodes_parses_title_audio_url_published_and_duration(tmp_path, monkeypatch):
    monkeypatch.setattr(podcasts, "get_app_data_dir", lambda: tmp_path)
    feed_text = _rss([_item(title="Primer episodio", audio_url="https://cdn.example/ep1.mp3")])
    monkeypatch.setattr(podcasts.requests, "get", lambda *a, **k: _FakeResponse(feed_text))

    episodes = podcasts.fetch_episodes("https://feed.example/show.xml")

    assert len(episodes) == 1
    ep = episodes[0]
    assert ep.title == "Primer episodio"
    assert ep.audio_url == "https://cdn.example/ep1.mp3"
    assert ep.published == "Mon, 01 Jan 2024 10:00:00 +0000"
    assert ep.description == "Descripción"
    assert ep.duration == "30:00"


def test_fetch_episodes_uses_placeholder_title_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(podcasts, "get_app_data_dir", lambda: tmp_path)
    feed_text = _rss([_item(title="", audio_url="https://cdn.example/ep1.mp3")])
    monkeypatch.setattr(podcasts.requests, "get", lambda *a, **k: _FakeResponse(feed_text))

    episodes = podcasts.fetch_episodes("https://feed.example/show.xml")

    assert episodes[0].title == "(sin título)"


def test_fetch_episodes_skips_items_without_enclosure_but_keeps_valid_ones(tmp_path, monkeypatch):
    """Un item sin audio (fila mala) no debe tumbar el resto del listado."""
    monkeypatch.setattr(podcasts, "get_app_data_dir", lambda: tmp_path)
    feed_text = _rss([
        _item(title="Sin audio", include_enclosure=False),
        _item(title="Con audio", audio_url="https://cdn.example/ep2.mp3"),
    ])
    monkeypatch.setattr(podcasts.requests, "get", lambda *a, **k: _FakeResponse(feed_text))

    episodes = podcasts.fetch_episodes("https://feed.example/show.xml")

    assert [ep.title for ep in episodes] == ["Con audio"]


def test_fetch_episodes_tolerates_missing_optional_fields(tmp_path, monkeypatch):
    """Un item sin pubDate/description/itunes:duration debe parsear con
    valores por defecto en vez de lanzar."""
    monkeypatch.setattr(podcasts, "get_app_data_dir", lambda: tmp_path)
    item = """<item>
<title>Minimalista</title>
<enclosure url="https://cdn.example/min.mp3" type="audio/mpeg" />
</item>"""
    feed_text = _rss([item])
    monkeypatch.setattr(podcasts.requests, "get", lambda *a, **k: _FakeResponse(feed_text))

    episodes = podcasts.fetch_episodes("https://feed.example/show.xml")

    assert episodes[0].title == "Minimalista"
    assert episodes[0].published == ""
    assert episodes[0].description == ""
    assert episodes[0].duration == ""


def test_fetch_episodes_respects_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(podcasts, "get_app_data_dir", lambda: tmp_path)
    items = [_item(title=f"Episodio {i}", audio_url=f"https://cdn.example/ep{i}.mp3") for i in range(5)]
    feed_text = _rss(items)
    monkeypatch.setattr(podcasts.requests, "get", lambda *a, **k: _FakeResponse(feed_text))

    episodes = podcasts.fetch_episodes("https://feed.example/show.xml", limit=2)

    assert len(episodes) == 2


def test_fetch_episodes_writes_cache_and_reuses_it_without_hitting_network_again(tmp_path, monkeypatch):
    monkeypatch.setattr(podcasts, "get_app_data_dir", lambda: tmp_path)
    feed_text = _rss([_item(title="Cacheado", audio_url="https://cdn.example/ep1.mp3")])
    calls = []

    def _fake_get(*args, **kwargs):
        calls.append(1)
        return _FakeResponse(feed_text)

    monkeypatch.setattr(podcasts.requests, "get", _fake_get)

    first = podcasts.fetch_episodes("https://feed.example/show.xml")
    second = podcasts.fetch_episodes("https://feed.example/show.xml")

    assert len(calls) == 1  # la segunda llamada usó la caché en disco
    assert [ep.title for ep in second] == [ep.title for ep in first]


def test_fetch_episodes_force_refresh_ignores_fresh_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(podcasts, "get_app_data_dir", lambda: tmp_path)
    first_feed = _rss([_item(title="Viejo", audio_url="https://cdn.example/old.mp3")])
    second_feed = _rss([_item(title="Nuevo", audio_url="https://cdn.example/new.mp3")])
    responses = iter([_FakeResponse(first_feed), _FakeResponse(second_feed)])
    monkeypatch.setattr(podcasts.requests, "get", lambda *a, **k: next(responses))

    podcasts.fetch_episodes("https://feed.example/show.xml")
    refreshed = podcasts.fetch_episodes("https://feed.example/show.xml", force_refresh=True)

    assert [ep.title for ep in refreshed] == ["Nuevo"]


def test_fetch_episodes_refetches_when_cache_is_older_than_ttl(tmp_path, monkeypatch):
    monkeypatch.setattr(podcasts, "get_app_data_dir", lambda: tmp_path)
    old_feed = _rss([_item(title="Viejo", audio_url="https://cdn.example/old.mp3")])
    new_feed = _rss([_item(title="Nuevo", audio_url="https://cdn.example/new.mp3")])
    responses = iter([_FakeResponse(old_feed), _FakeResponse(new_feed)])
    monkeypatch.setattr(podcasts.requests, "get", lambda *a, **k: next(responses))

    podcasts.fetch_episodes("https://feed.example/show.xml")
    cache_path = podcasts._cache_path_for("https://feed.example/show.xml")
    old_mtime = cache_path.stat().st_mtime - podcasts.CACHE_TTL_SECONDS - 1
    import os
    os.utime(cache_path, (old_mtime, old_mtime))

    refreshed = podcasts.fetch_episodes("https://feed.example/show.xml")

    assert [ep.title for ep in refreshed] == ["Nuevo"]


def test_fetch_episodes_falls_back_to_cache_when_request_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(podcasts, "get_app_data_dir", lambda: tmp_path)
    feed_text = _rss([_item(title="Cacheado", audio_url="https://cdn.example/ep1.mp3")])
    responses = iter([_FakeResponse(feed_text)])
    monkeypatch.setattr(podcasts.requests, "get", lambda *a, **k: next(responses))
    podcasts.fetch_episodes("https://feed.example/show.xml")

    def _raise(*args, **kwargs):
        raise requests.ConnectionError("sin red")

    monkeypatch.setattr(podcasts.requests, "get", _raise)

    episodes = podcasts.fetch_episodes("https://feed.example/show.xml", force_refresh=True)

    assert [ep.title for ep in episodes] == ["Cacheado"]


def test_fetch_episodes_falls_back_to_cache_when_http_status_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(podcasts, "get_app_data_dir", lambda: tmp_path)
    feed_text = _rss([_item(title="Cacheado", audio_url="https://cdn.example/ep1.mp3")])
    responses = iter([_FakeResponse(feed_text)])
    monkeypatch.setattr(podcasts.requests, "get", lambda *a, **k: next(responses))
    podcasts.fetch_episodes("https://feed.example/show.xml")

    monkeypatch.setattr(podcasts.requests, "get", lambda *a, **k: _FakeResponse("", status_ok=False))

    episodes = podcasts.fetch_episodes("https://feed.example/show.xml", force_refresh=True)

    assert [ep.title for ep in episodes] == ["Cacheado"]


def test_fetch_episodes_falls_back_to_cache_on_malformed_xml(tmp_path, monkeypatch):
    monkeypatch.setattr(podcasts, "get_app_data_dir", lambda: tmp_path)
    feed_text = _rss([_item(title="Cacheado", audio_url="https://cdn.example/ep1.mp3")])
    responses = iter([_FakeResponse(feed_text)])
    monkeypatch.setattr(podcasts.requests, "get", lambda *a, **k: next(responses))
    podcasts.fetch_episodes("https://feed.example/show.xml")

    monkeypatch.setattr(podcasts.requests, "get", lambda *a, **k: _FakeResponse("<rss><channel><item>"))

    episodes = podcasts.fetch_episodes("https://feed.example/show.xml", force_refresh=True)

    assert [ep.title for ep in episodes] == ["Cacheado"]


def test_fetch_episodes_returns_empty_list_when_request_fails_and_no_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(podcasts, "get_app_data_dir", lambda: tmp_path)

    def _raise(*args, **kwargs):
        raise requests.ConnectionError("sin red")

    monkeypatch.setattr(podcasts.requests, "get", _raise)

    assert podcasts.fetch_episodes("https://feed.example/show.xml") == []


def test_fetch_episodes_returns_empty_list_when_feed_has_no_audio_items(tmp_path, monkeypatch):
    monkeypatch.setattr(podcasts, "get_app_data_dir", lambda: tmp_path)
    feed_text = _rss([_item(include_enclosure=False)])
    monkeypatch.setattr(podcasts.requests, "get", lambda *a, **k: _FakeResponse(feed_text))

    assert podcasts.fetch_episodes("https://feed.example/show.xml") == []


def test_fetch_episodes_discards_corrupt_cache_file_and_returns_empty_when_network_also_fails(tmp_path, monkeypatch):
    """Caché corrupta (escritura incompleta, apagón…): se descarta para no
    devolver basura, y si además la red falla, no hay nada que devolver."""
    monkeypatch.setattr(podcasts, "get_app_data_dir", lambda: tmp_path)
    cache_path = podcasts._cache_path_for("https://feed.example/show.xml")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text("{esto no es json valido", encoding="utf-8")

    def _raise(*args, **kwargs):
        raise requests.ConnectionError("sin red")

    monkeypatch.setattr(podcasts.requests, "get", _raise)

    assert podcasts.fetch_episodes("https://feed.example/show.xml", force_refresh=True) == []
    assert not cache_path.exists()  # se borró el archivo corrupto


# --------------------------------------------------------------------------
# EpisodeDownloadWorker
# --------------------------------------------------------------------------

class _FakeUrlResponse:
    def __init__(self, chunks, headers=None):
        self._chunks = list(chunks)
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def read(self, n=-1):
        if self._chunks:
            return self._chunks.pop(0)
        return b""


def _episode(title="Mi episodio", audio_url="https://cdn.example/audio.mp3?token=abc"):
    return Episode(title=title, audio_url=audio_url)


def test_worker_run_fails_when_dest_dir_cannot_be_created(tmp_path, monkeypatch):
    worker = EpisodeDownloadWorker(_episode(), str(tmp_path / "destino"))
    monkeypatch.setattr(podcasts.os, "makedirs", lambda *a, **k: (_ for _ in ()).throw(OSError("sin permiso")))
    fallos = []
    worker.failed.connect(fallos.append)
    worker.run()
    assert "no se pudo crear la carpeta" in fallos[0].lower()


def test_worker_run_downloads_and_emits_finished_with_final_path(tmp_path, monkeypatch):
    payload = b"contenido de audio"
    monkeypatch.setattr(
        podcasts.urllib.request, "urlopen",
        lambda req, timeout=None: _FakeUrlResponse([payload], headers={"Content-Length": str(len(payload))}),
    )

    worker = EpisodeDownloadWorker(_episode(title="Mi episodio", audio_url="https://cdn.example/audio.mp3?x=1"), str(tmp_path))
    progresos, finalizados = [], []
    worker.progress.connect(lambda frac, texto: progresos.append((frac, texto)))
    worker.finished_ok.connect(finalizados.append)

    worker.run()

    destino = tmp_path / "Mi episodio.mp3"
    assert finalizados == [str(destino)]
    assert destino.read_bytes() == payload
    assert not destino.with_suffix(".mp3.part").exists()
    assert progresos and progresos[0][0] == 1.0


def test_worker_run_sanitizes_illegal_filename_characters(tmp_path, monkeypatch):
    monkeypatch.setattr(
        podcasts.urllib.request, "urlopen",
        lambda req, timeout=None: _FakeUrlResponse([b"x"], headers={}),
    )
    worker = EpisodeDownloadWorker(_episode(title='Título: "raro"?<>|'), str(tmp_path))
    finalizados = []
    worker.finished_ok.connect(finalizados.append)

    worker.run()

    assert finalizados == [str(tmp_path / "Título raro.mp3")]


def test_worker_run_falls_back_to_generic_name_when_title_is_only_illegal_characters(tmp_path, monkeypatch):
    monkeypatch.setattr(
        podcasts.urllib.request, "urlopen",
        lambda req, timeout=None: _FakeUrlResponse([b"x"], headers={}),
    )
    worker = EpisodeDownloadWorker(_episode(title='???'), str(tmp_path))
    finalizados = []
    worker.finished_ok.connect(finalizados.append)

    worker.run()

    assert finalizados == [str(tmp_path / "episodio.mp3")]


def test_worker_run_defaults_extension_to_mp3_when_url_has_none(tmp_path, monkeypatch):
    monkeypatch.setattr(
        podcasts.urllib.request, "urlopen",
        lambda req, timeout=None: _FakeUrlResponse([b"x"], headers={}),
    )
    worker = EpisodeDownloadWorker(_episode(title="Sin extension", audio_url="https://cdn.example/stream"), str(tmp_path))
    finalizados = []
    worker.finished_ok.connect(finalizados.append)

    worker.run()

    assert finalizados == [str(tmp_path / "Sin extension.mp3")]


def test_worker_run_reports_cancelled_and_cleans_up_partial_file(tmp_path, monkeypatch):
    worker = EpisodeDownloadWorker(_episode(), str(tmp_path))

    def _urlopen(req, timeout=None):
        worker.cancel()
        return _FakeUrlResponse([b"parte1", b"parte2"], headers={})

    monkeypatch.setattr(podcasts.urllib.request, "urlopen", _urlopen)
    fallos, finalizados = [], []
    worker.failed.connect(fallos.append)
    worker.finished_ok.connect(finalizados.append)

    worker.run()

    assert fallos == ["__cancelled__"]
    assert finalizados == []
    assert not (tmp_path / "Mi episodio.mp3.part").exists()


def test_worker_run_emits_failed_with_exception_message_on_download_error(tmp_path, monkeypatch):
    def _raise(*args, **kwargs):
        raise OSError("host inalcanzable")

    monkeypatch.setattr(podcasts.urllib.request, "urlopen", _raise)
    worker = EpisodeDownloadWorker(_episode(), str(tmp_path))
    fallos = []
    worker.failed.connect(fallos.append)

    worker.run()

    assert "host inalcanzable" in fallos[0]


def test_worker_cancel_flag_is_set_and_does_not_raise_before_running():
    worker = EpisodeDownloadWorker(_episode(), ".")
    worker.cancel()
    assert worker._cancelado is True
