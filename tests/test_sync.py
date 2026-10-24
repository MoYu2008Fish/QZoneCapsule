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
