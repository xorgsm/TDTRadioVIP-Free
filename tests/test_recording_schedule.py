from core import recording_schedule as schedule


def _recording(title, start, stop, status="pending"):
    return schedule.ScheduledRecording(
        tvg_id=title,
        channel_name="Canal",
        channel_url="https://stream.test/live",
        title=title,
        start=start,
        stop=stop,
        status=status,
    )


def test_find_conflicts_detects_overlap_and_ignores_touching_intervals():
    existing = _recording("Noticias", "20260824200000", "20260824210000")

    assert schedule.find_conflicts(
        _recording("Película", "20260824203000", "20260824220000"), [existing]
    ) == [existing]
    assert schedule.find_conflicts(
        _recording("Después", "20260824210000", "20260824220000"), [existing]
    ) == []


def test_find_conflicts_ignores_failed_and_same_reservation():
    failed = _recording("Fallida", "20260824200000", "20260824210000", "error")
    same = _recording("Programa", "20260824200000", "20260824210000")

    assert schedule.find_conflicts(same, [failed, same]) == []


def test_find_conflicts_accepts_xmltv_timezone_suffix():
    existing = _recording(
        "Noticias", "20260824200000 +0200", "20260824210000 +0200"
    )
    candidate = _recording(
        "Película", "20260824203000 +0200", "20260824220000 +0200"
    )

    assert schedule.find_conflicts(candidate, [existing]) == [existing]
