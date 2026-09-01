import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from core import backup


def test_backup_preserves_stream_health_for_the_active_profile(tmp_path, monkeypatch):
    app_data = tmp_path / "app"
    profile_data = tmp_path / "profile"
    app_data.mkdir()
    profile_data.mkdir()
    health_path = profile_data / "stream_health.json"
    health = {"version": 1, "streams": [{"kind": "tv", "url": "https://stream.example", "history": []}]}
    health_path.write_text(json.dumps(health), encoding="utf-8")
    monkeypatch.setattr(backup, "get_app_data_dir", lambda: app_data)
    monkeypatch.setattr(backup, "get_profile_data_dir", lambda: profile_data)

    archive = tmp_path / "backup.json"
    backup.export_backup(str(archive))
    payload = json.loads(archive.read_text(encoding="utf-8"))

    assert payload["stream_health"] == health

    health_path.unlink()
    assert "stream_health" in backup.import_backup(str(archive))
    assert json.loads(health_path.read_text(encoding="utf-8")) == health


def test_backup_includes_recordings_reminders_and_recurring_rules(tmp_path, monkeypatch):
    # Antes el backup solo cubría favoritos/historial/canales propios y se
    # perdían silenciosamente las grabaciones programadas y las reglas
    # recurrentes al restaurar en otro PC -- ver core/backup.py.
    app_data = tmp_path / "app"
    profile_data = tmp_path / "profile"
    app_data.mkdir()
    profile_data.mkdir()

    (profile_data / "epg_recordings.json").write_text(
        json.dumps([{"tvg_id": "la1", "title": "Telediario"}]), encoding="utf-8"
    )
    (profile_data / "epg_reminders.json").write_text(
        json.dumps([{"tvg_id": "la1", "title": "Telediario"}]), encoding="utf-8"
    )
    (profile_data / "recurring_recordings.json").write_text(
        json.dumps([{"tvg_id": "la1", "days": [0, 1]}]), encoding="utf-8"
    )
    (profile_data / "recurring_recordings_sync.json").write_text(
        json.dumps({"rule-1": "2026-08-24"}), encoding="utf-8"
    )
    (profile_data / "tv_channels_hidden.json").write_text(
        json.dumps(["Canal oculto"]), encoding="utf-8"
    )

    monkeypatch.setattr(backup, "get_app_data_dir", lambda: app_data)
    monkeypatch.setattr(backup, "get_profile_data_dir", lambda: profile_data)

    archive = tmp_path / "backup.json"
    backup.export_backup(str(archive))
    payload = json.loads(archive.read_text(encoding="utf-8"))

    assert payload["epg_recordings"] == [{"tvg_id": "la1", "title": "Telediario"}]
    assert payload["recurring_recordings_sync"] == {"rule-1": "2026-08-24"}
    assert payload["hidden_tv_channels"] == ["Canal oculto"]

    for name in (
        "epg_recordings.json", "epg_reminders.json", "recurring_recordings.json",
        "recurring_recordings_sync.json", "tv_channels_hidden.json",
    ):
        (profile_data / name).unlink()

    restored = backup.import_backup(str(archive))
    assert "epg_recordings" in restored
    assert "recurring_recordings_sync" in restored
    assert json.loads((profile_data / "tv_channels_hidden.json").read_text(encoding="utf-8")) == ["Canal oculto"]


def test_automatic_backup_applies_interval_and_retention(tmp_path, monkeypatch):
    def fake_export(path):
        with open(path, "w", encoding="utf-8") as output:
            output.write("{}")

    monkeypatch.setattr(backup, "export_backup", fake_export)
    now = datetime(2026, 8, 24, 12, 0, 0)
    for index in range(3):
        old = tmp_path / f"TDTRadioVIP_auto_old{index}.json"
        old.write_text("{}", encoding="utf-8")
        timestamp = (now - timedelta(days=index + 2)).timestamp()
        os.utime(old, (timestamp, timestamp))

    result = backup.create_automatic_backup(tmp_path, retention=2, now=now)
    assert result is not None
    assert len(list(tmp_path.glob("TDTRadioVIP_auto_*.json"))) == 2
    assert backup.create_automatic_backup(tmp_path, retention=2, now=now) is None


def test_import_rejects_oversized_backup_before_reading(tmp_path, monkeypatch):
    archive = tmp_path / "backup.json"
    archive.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(backup, "MAX_BACKUP_BYTES", 1)

    with pytest.raises(ValueError, match="tamaño máximo"):
        backup.import_backup(str(archive))


def test_import_size_limit_is_enforced_again_during_read(tmp_path, monkeypatch):
    archive = tmp_path / "backup.json"
    archive.write_bytes(b"{}")
    monkeypatch.setattr(backup, "MAX_BACKUP_BYTES", 1)
    real_stat = Path.stat

    def stale_small_stat(path, *args, **kwargs):
        result = real_stat(path, *args, **kwargs)
        if path == archive:
            return type("Stat", (), {"st_size": 0})()
        return result

    monkeypatch.setattr(Path, "stat", stale_small_stat)

    with pytest.raises(ValueError, match="tamaño máximo"):
        backup.import_backup(str(archive))


def test_future_dated_backup_does_not_disable_automatic_backups(tmp_path, monkeypatch):
    monkeypatch.setattr(backup, "export_backup", lambda path: Path(path).write_text("{}"))
    now = datetime(2026, 8, 31, 12, 0, 0)
    future = tmp_path / "TDTRadioVIP_auto_future.json"
    future.write_text("{}", encoding="utf-8")
    future_timestamp = (now + timedelta(days=30)).timestamp()
    os.utime(future, (future_timestamp, future_timestamp))

    assert backup.create_automatic_backup(tmp_path, now=now) is not None


def test_automatic_backup_ignores_matching_directories(tmp_path, monkeypatch):
    monkeypatch.setattr(backup, "export_backup", lambda path: Path(path).write_text("{}"))
    (tmp_path / "TDTRadioVIP_auto_fake.json").mkdir()

    result = backup.create_automatic_backup(tmp_path, now=datetime(2026, 8, 31, 12, 0, 0))

    assert result is not None
