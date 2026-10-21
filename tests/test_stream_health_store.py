import json
from datetime import datetime, timezone

import pytest

from core import stream_health_store
from core.stream_health_store import (
    StreamHealthStore, derive_health_status, is_health_stale, matches_health_filter,
    list_health, select_stale_entries, summarize_health,
)


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        ({"status": "ok", "latency_ms": 200}, "stable"),
        ({"status": "ok", "latency_ms": 1500}, "slow"),
        ({"status": "error", "http_status": 0}, "down"),
        ({"status": "ok", "http_status": 403}, "restricted"),
        ({"status": "restricted", "latency_ms": 10}, "restricted"),
    ],
)
def test_derive_health_status(result, expected):
    assert derive_health_status(result) == expected


@pytest.mark.parametrize(
    ("status", "filter_key", "expected"),
    [
        # "all" acepta cualquier estado, incluido "sin diagnosticar" (None).
        ("stable", "all", True),
        (None, "all", True),
        ("stable", "stable", True),
        ("slow", "stable", False),
        (None, "stable", False),
        ("slow", "issues", True),
        ("down", "issues", True),
        ("restricted", "issues", True),
        ("stable", "issues", False),
        (None, "issues", False),
        (None, "unchecked", True),
        ("", "unchecked", True),
        ("stable", "unchecked", False),
        # Un filtro desconocido no debe ocultar nada por accidente.
        ("down", "no-existe", True),
    ],
)
def test_matches_health_filter(status, filter_key, expected):
    assert matches_health_filter(status, filter_key) is expected


def test_record_result_persists_history_by_kind_and_url(tmp_path):
    path = tmp_path / "stream_health.json"
    store = StreamHealthStore(path, max_history=2)

    first = store.record_result(
        "tv", "https://example.test/live", {"status": "ok", "latency_ms": 80},
        checked_at="2026-08-22T10:00:00+00:00",
    )
    second = store.record_result(
        "tv", "https://example.test/live", {"status": "error", "error": "offline"},
        checked_at="2026-08-22T11:00:00+00:00",
    )

    assert first["status"] == "stable"
    assert second["status"] == "down"
    restored = StreamHealthStore(path).get("tv", "https://example.test/live")
    assert restored["checked_at"] == "2026-08-22T11:00:00+00:00"
    assert [event["status"] for event in restored["history"]] == ["down", "stable"]
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 1


def test_list_filters_by_kind_and_orders_newest_first(tmp_path):
    store = StreamHealthStore(tmp_path / "health.json")
    store.record_result("tv", "https://tv.test", {"status": "ok"}, checked_at="2026-01-01T00:00:00+00:00")
    store.record_result("radio", "https://radio.test", {"status": "ok"}, checked_at="2026-01-02T00:00:00+00:00")

    assert [item["url"] for item in store.list()] == ["https://radio.test", "https://tv.test"]
    assert [item["kind"] for item in store.list("tv")] == ["tv"]


def test_list_health_uses_the_active_profile_store(monkeypatch, tmp_path):
    store = StreamHealthStore(tmp_path / "stream_health.json")
    store.record_result("radio", "https://radio.test", {"status": "ok"})
    monkeypatch.setattr("core.stream_health_store.get_profile_data_dir", lambda: tmp_path)

    assert [item["url"] for item in list_health()] == ["https://radio.test"]


def test_clear_removes_selected_stream_or_all_states(tmp_path):
    store = StreamHealthStore(tmp_path / "health.json")
    store.record_results([
        {"kind": "tv", "url": "https://one.test", "status": "ok"},
        {"kind": "tv", "url": "https://two.test", "status": "error"},
        {"kind": "radio", "url": "https://one.test", "status": "ok"},
    ])

    assert store.clear("tv", "https://one.test") == 1
    assert store.get("tv", "https://one.test") is None
    assert store.clear("tv") == 1
    assert store.clear() == 1
    assert store.list() == []


def test_store_tolerates_invalid_file_and_rejects_incomplete_identity(tmp_path):
    path = tmp_path / "health.json"
    path.write_text('{"streams": ["bad", {"kind": "tv"}]}', encoding="utf-8")
    store = StreamHealthStore(path)

    assert store.list() == []
    with pytest.raises(ValueError):
        store.record_result("", "https://stream.test", {"status": "ok"})
    with pytest.raises(ValueError):
        store.clear(url="https://stream.test")


def test_summarize_health_accepts_saved_and_raw_diagnostic_results():
    assert summarize_health([
        {"status": "stable"},
        {"status": "ok", "latency_ms": 2_000},
        {"status": "error"},
        {"status": "restricted"},
    ]) == {"total": 4, "stable": 1, "slow": 1, "down": 1, "restricted": 1}


def test_health_staleness_handles_old_missing_and_recent_dates():
    now = datetime(2026, 8, 24, tzinfo=timezone.utc)
    assert is_health_stale(None, now=now)
    assert is_health_stale("2026-08-01T00:00:00+00:00", now=now)
    assert not is_health_stale("2026-08-23T00:00:00+00:00", now=now)


def test_select_stale_entries_respects_limit(tmp_path):
    store = StreamHealthStore(tmp_path / "health.json")
    entries = [
        {"kind": "tv", "name": f"Canal {index}", "url": f"https://{index}.test"}
        for index in range(5)
    ]
    assert len(select_stale_entries(entries, store=store, limit=2)) == 2


def test_record_results_writes_a_batch_only_once(tmp_path, monkeypatch):
    store = StreamHealthStore(tmp_path / "health.json")
    save_calls = []
    original_save = store._save_streams

    def save_once(streams):
        save_calls.append(len(streams))
        original_save(streams)

    monkeypatch.setattr(store, "_save_streams", save_once)

    recorded = store.record_results([
        {"kind": "tv", "url": "https://one.test", "status": "ok"},
        {"kind": "radio", "url": "https://two.test", "status": "error"},
    ])

    assert len(recorded) == 2
    assert save_calls == [2]


# --- Rendimiento: lecturas ligeras sin historial y fichero compacto ---------

def _seed(store, count=3):
    for index in range(count):
        store.record_result(
            "tv", f"https://tv.test/{index}", {"status": "ok", "latency_ms": 10},
            checked_at=f"2026-01-0{index + 1}T00:00:00+00:00",
        )


def test_list_without_history_omits_the_event_log(tmp_path):
    store = StreamHealthStore(tmp_path / "health.json")
    _seed(store)

    entries = store.list(include_history=False)

    assert [entry["url"] for entry in entries] == [f"https://tv.test/{i}" for i in (2, 1, 0)]
    assert all("history" not in entry for entry in entries)
    assert entries[0]["status"] == "stable"
    assert entries[0]["checked_at"] == "2026-01-03T00:00:00+00:00"


def test_list_with_history_keeps_returning_it_by_default(tmp_path):
    store = StreamHealthStore(tmp_path / "health.json")
    _seed(store, 1)

    assert store.list()[0]["history"]


def test_light_list_does_not_reread_an_unchanged_file(tmp_path, monkeypatch):
    store = StreamHealthStore(tmp_path / "health.json")
    _seed(store)
    store.list(include_history=False)
    reads = []
    real_read_json = stream_health_store.read_json
    monkeypatch.setattr(
        stream_health_store, "read_json",
        lambda *args, **kwargs: reads.append(args) or real_read_json(*args, **kwargs),
    )

    store.list(include_history=False)
    store.list(include_history=False)

    assert reads == []


def test_light_list_sees_results_recorded_after_it_was_cached(tmp_path):
    store = StreamHealthStore(tmp_path / "health.json")
    _seed(store, 1)
    assert len(store.list(include_history=False)) == 1

    store.record_result("tv", "https://tv.test/new", {"status": "error"},
                        checked_at="2026-02-01T00:00:00+00:00")

    urls = {entry["url"] for entry in store.list(include_history=False)}
    assert urls == {"https://tv.test/0", "https://tv.test/new"}


def test_light_list_returns_copies_the_caller_may_mutate(tmp_path):
    store = StreamHealthStore(tmp_path / "health.json")
    _seed(store, 1)

    store.list(include_history=False)[0]["status"] = "down"

    assert store.list(include_history=False)[0]["status"] == "stable"


def test_saving_trims_the_history_of_every_stream_not_only_the_updated_one(tmp_path):
    path = tmp_path / "health.json"
    long_history = [
        {"status": "stable", "checked_at": f"2026-01-{day:02d}T00:00:00+00:00",
         "latency_ms": 1, "http_status": 0, "error": ""}
        for day in range(1, 9)
    ]
    path.write_text(json.dumps({"version": 1, "streams": [{
        "kind": "tv", "url": "https://old.test", "status": "stable",
        "checked_at": "2026-01-08T00:00:00+00:00", "latency_ms": 1,
        "http_status": 0, "error": "", "history": long_history,
    }]}), encoding="utf-8")
    store = StreamHealthStore(path, max_history=3)

    store.record_result("tv", "https://other.test", {"status": "ok"})

    saved = {s["url"]: s for s in json.loads(path.read_text(encoding="utf-8"))["streams"]}
    assert len(saved["https://old.test"]["history"]) == 3


def test_the_store_file_is_written_compact(tmp_path):
    path = tmp_path / "health.json"
    _seed(StreamHealthStore(path), 1)

    assert "\n" not in path.read_text(encoding="utf-8")


def test_list_health_can_skip_the_history(monkeypatch, tmp_path):
    monkeypatch.setattr("core.stream_health_store.get_profile_data_dir", lambda: tmp_path)
    StreamHealthStore().record_result("tv", "https://tv.test", {"status": "ok"})

    assert "history" not in list_health(include_history=False)[0]


def test_concurrent_batches_do_not_lose_each_others_results(tmp_path, monkeypatch):
    import threading
    import time

    from core import stream_health_store as shs

    store = StreamHealthStore(tmp_path / "health.json")
    original_load = store._load_streams

    def slow_load():
        streams = original_load()
        time.sleep(0.05)  # ensancha la ventana leer-modificar-escribir
        return streams

    monkeypatch.setattr(store, "_load_streams", slow_load)
    batches = [
        [{"kind": "tv", "url": f"https://a.test/{i}", "status": "ok"} for i in range(5)],
        [{"kind": "radio", "url": f"https://b.test/{i}", "status": "ok"} for i in range(5)],
    ]
    threads = [threading.Thread(target=store.record_results, args=(batch,)) for batch in batches]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(shs.StreamHealthStore(tmp_path / "health.json").list()) == 10
