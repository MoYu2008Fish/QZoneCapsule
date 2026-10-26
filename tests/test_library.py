import pytest

from qzone_archiver.library import archive_databases, local_media, read_library
from qzone_archiver.store import Store


def make_archive(root, uin, *, image=False):
    with Store(root / "qzone.db") as store:
        store.upsert_account(uin, f"用户{uin}")
        store.upsert_album(uin, {"id": "same", "name": "旅行", "total": 1})
        store.upsert_photo(uin, "same", {"sloc": "same", "name": "海边", "upload_at": "2020-01-01"})
        store.upsert_mood(uin, {"tid": "same", "content": f"{uin}的回忆", "created_at": "2020-02-01"})
        if image:
            file = root / f"media/{uin}/photo.jpg"
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_bytes(b"photo")
            store.set_photo_file(uin, "same", "same", file.relative_to(root).as_posix(), 5, "mtime-only")


def test_discover_and_merge_accounts_without_identity_collisions(tmp_path):
    make_archive(tmp_path / "123", "123")
    make_archive(tmp_path / "456", "456")
    before = {p: p.read_bytes() for p in tmp_path.glob("*/qzone.db")}
    entries, errors = read_library([tmp_path, tmp_path / "123"])
    assert not errors
    assert len(entries) == 6
    assert len({e["key"] for e in entries}) == 6
    assert {e["uin"] for e in entries} == {"123", "456"}
    assert all(p.read_bytes() == content for p, content in before.items())


def test_duplicate_exports_prefer_downloaded_photo(tmp_path):
    make_archive(tmp_path / "a", "123", image=True)
    make_archive(tmp_path / "b", "123")
    entries, _ = read_library([tmp_path])
    photo = next(e for e in entries if e["kind"] == "photo")
    assert photo["root"] == tmp_path / "a"
    assert local_media(photo["root"], photo["path"])
    assert len(entries) == 3


def test_local_media_rejects_escape_and_external_sources(tmp_path):
    root = tmp_path / "archive"
    root.mkdir()
    secret = tmp_path / "other.jpg"
    secret.write_bytes(b"private")
    (root / "link.jpg").symlink_to(secret)
    for value in ("../other.jpg", str(secret), "link.jpg", "https://example.com/a.jpg"):
        assert local_media(root, value) is None
    assert not archive_databases([root])


def test_missing_db_readonly_does_not_create_file(tmp_path):
    import sqlite3

    with pytest.raises(sqlite3.OperationalError):
        Store(tmp_path / "qzone.db", readonly=True)
    assert not (tmp_path / "qzone.db").exists()


def test_damaged_archive_does_not_hide_valid_archive(tmp_path):
    make_archive(tmp_path / "good", "123")
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "qzone.db").write_text("not sqlite")
    entries, errors = read_library([tmp_path])
    assert len(entries) == 3
    assert len(errors) == 1


def test_nested_accounts_are_discovered_and_media_is_not_scanned(tmp_path):
    make_archive(tmp_path / "old" / "exports" / "123", "123")
    make_archive(tmp_path / "current" / "456", "456")
    make_archive(tmp_path / "media" / "not-an-archive", "789")
    entries, _ = read_library([tmp_path])
    assert {e["uin"] for e in entries} == {"123", "456"}


def test_legacy_video_issues_are_not_download_failures(tmp_path):
    import json

    from qzone_archiver.library import read_run_issues

    make_archive(tmp_path / "123", "123")
    report = {
        "failed": 3,
        "issues": [
            {"kind": "video", "id": "v1", "reason": "视频暂不支持"},
            {"kind": "video", "id": "v2", "reason": "视频暂不支持"},
            {"kind": "mood_image", "id": "m:0", "reason": "配图失败"},
        ],
    }
    (tmp_path / "123" / "last-run.json").write_text(json.dumps(report))
    (tmp_path / "123" / "last-run-123.json").write_text(json.dumps(report))
    issues = read_run_issues([tmp_path])
    assert len(issues) == 3  # per-account and latest report must not double-count
    assert sum(i["severity"] == "failed" for i in issues) == 1
    assert sum(i["severity"] == "unsupported" for i in issues) == 2
