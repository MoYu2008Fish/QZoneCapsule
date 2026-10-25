from pathlib import Path
from threading import Event

import pytest

from qzone_archiver import sync
from qzone_archiver.media import DownloadError
from qzone_archiver.store import Store

SESSION = {"uin": "123", "cookie": "p_uin=o123; p_skey=test"}


@pytest.fixture
def sources(monkeypatch):
    albums = [{"id": "a", "name": "相册", "total": 1}, {"id": "b", "name": "空相册", "total": 0}]
    photos = [{"sloc": "p", "url_raw": "https://media/raw.jpg", "url_normal": "https://media/normal.jpg"}]
    moods = [
        {
            "tid": "m",
            "content": "你好",
            "images": [{"index": 0, "kind": "image", "url": "https://media/m.jpg"}],
        }
    ]
    monkeypatch.setattr(sync, "fetch_albums", lambda *_: iter(albums))
    monkeypatch.setattr(sync, "fetch_photos", lambda _c, _u, a: iter(photos if a == "a" else []))
    monkeypatch.setattr(sync, "fetch_moods", lambda *_: iter(moods))
    monkeypatch.setattr(sync, "apply_time", lambda *_: "skipped")
    return photos


def test_integrated_export_fallback_and_repeat(tmp_path, monkeypatch, sources):
    calls = []

    def download(self, url, dest):
        calls.append(url)
        if "raw" in url:
            raise DownloadError("unavailable")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"image")
        return dest, 5

    monkeypatch.setattr(sync.MediaDownloader, "download", download)
    result = sync.run_sync(SESSION, sync.SyncOptions(tmp_path))
    assert result.state == "complete"
    assert (result.albums, result.moods, result.downloaded) == (2, 1, 2)
    assert "https://media/normal.jpg" in calls
    with Store(tmp_path / "qzone.db") as store:
        assert next(store.iter_photos("123"))["quality"] == "normal"
        assert store.stats("123")["mood_media"] == 1
    calls.clear()
    second = sync.run_sync(SESSION, sync.SyncOptions(tmp_path))
    assert second.skipped == 2
    assert not calls
    with Store(tmp_path / "qzone.db") as store:
        assert next(store.iter_photos("123"))["quality"] == "normal"
    assert (tmp_path / "index.html").is_file()
    assert "空相册" in (tmp_path / "data.js").read_text()


def test_failed_download_report_and_retry(tmp_path, monkeypatch, sources):
    def fail(*_):
        raise DownloadError("secret signed URL must not enter report")

    monkeypatch.setattr(sync.MediaDownloader, "download", fail)
    result = sync.run_sync(SESSION, sync.SyncOptions(tmp_path))
    assert result.state == "partial"
    assert result.failed == 2
    assert "secret" not in (tmp_path / "last-run.json").read_text()
    assert (tmp_path / "index.html").exists()


def test_cancel_preserves_archive(tmp_path, sources):
    event = Event()
    event.set()
    result = sync.run_sync(SESSION, sync.SyncOptions(tmp_path), cancel=event)
    assert result.state == "cancelled"
    assert Path(result.index).exists()


def test_source_failure_does_not_claim_success(tmp_path, monkeypatch, sources):
    def fail(*_):
        raise RuntimeError("private token")

    monkeypatch.setattr(sync, "fetch_moods", fail)
    result = sync.run_sync(SESSION, sync.SyncOptions(tmp_path, media=False))
    assert result.state == "error"
    assert result.albums == 2
    assert (tmp_path / "last-run.json").exists()


def test_album_selection(tmp_path, sources):
    result = sync.run_sync(SESSION, sync.SyncOptions(tmp_path, moods=False, media=False, album_ids={"b"}))
    assert result.albums == 1
    assert result.photos == 0


def test_video_metadata_is_not_a_download(tmp_path, sources):
    sources[0]["is_video"] = True
    result = sync.run_sync(SESSION, sync.SyncOptions(tmp_path, moods=False))
    assert result.state == "partial"
    assert result.downloaded == 0
    assert result.issues[0]["kind"] == "video"


def test_no_sources_rejected(tmp_path):
    with pytest.raises(ValueError):
        sync.run_sync(SESSION, sync.SyncOptions(tmp_path, albums=False, moods=False))


def test_other_account_rejected(tmp_path):
    with Store(tmp_path / "qzone.db") as store:
        store.upsert_account("456")
    with pytest.raises(ValueError):
        sync.run_sync(SESSION, sync.SyncOptions(tmp_path))


def test_bad_album_keeps_progress_and_continues_other_sources(tmp_path, monkeypatch, sources):
    from qzone_archiver.client import QzoneError

    visited = []

    def photos(_client, _uin, album_id):
        visited.append(album_id)
        if album_id == "a":
            yield sources[0]
            raise QzoneError("response contains private data")

    monkeypatch.setattr(sync, "fetch_photos", photos)
    report = sync.run_sync(SESSION, sync.SyncOptions(tmp_path, media=False))
    assert visited == ["a", "b"]
    assert report.state == "partial"
    assert (report.albums, report.photos, report.moods) == (2, 1, 1)
    assert report.issues[0]["kind"] == "album_photos"
    assert "response contains private data" not in (tmp_path / "last-run.json").read_text()
    with Store(tmp_path / "qzone.db") as store:
        assert len(list(store.iter_photos("123"))) == 1


def test_cancel_during_album_failure_is_cancelled(tmp_path, monkeypatch, sources):
    from qzone_archiver.client import QzoneError

    cancel = Event()

    def photos(*_):
        cancel.set()
        raise QzoneError("stopped")

    monkeypatch.setattr(sync, "fetch_photos", photos)
    report = sync.run_sync(SESSION, sync.SyncOptions(tmp_path), cancel=cancel)
    assert report.state == "cancelled"
    assert not report.issues


def test_merged_export_preserves_accounts_and_colliding_ids(tmp_path, sources):
    import json

    options = sync.SyncOptions(tmp_path, media=False, merge_accounts=True)
    sync.run_sync(SESSION, options)
    second = sync.run_sync({"uin": "456", "cookie": "p_uin=o456; p_skey=test"}, options)
    assert second.state == "complete"
    with Store(tmp_path / "qzone.db", readonly=True) as store:
        assert store.stats("123")["photos"] == store.stats("456")["photos"] == 1
        assert store.stats("123")["moods"] == store.stats("456")["moods"] == 1
    text = (tmp_path / "data.js").read_text()
    data = json.loads(text.removeprefix("window.__QZONE_DATA__ = ").removesuffix(";"))
    assert len(data["albums"]) == 4
    assert {p["album_id"] for p in data["photos"]} == {"123:a", "456:a"}
    assert {m["uin"] for m in data["moods"]} == {"123", "456"}
    assert {a["uin"] for a in data["accounts"]} == {"123", "456"}
    assert (tmp_path / "last-run-123.json").is_file()
    assert (tmp_path / "last-run-456.json").is_file()
