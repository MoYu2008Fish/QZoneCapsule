import shutil
from pathlib import Path

import piexif

from qzone_archiver.exporter import export_bundle
from qzone_archiver.store import Store


def test_store_and_export(tmp_path: Path):
    db = tmp_path / "qzone.db"
    with Store(db) as store:
        store.upsert_account("123", "墨语")
        store.upsert_album(
            "123",
            {"id": "a1", "name": "旅行", "createtime": "2020-01-01 00:00:00", "total": 1},
        )
        store.upsert_photo(
            "123",
            "a1",
            {
                "sloc": "s1",
                "name": "海",
                "shoot_at": "2020-01-02 03:04:05",
                "upload_at": "2020-01-03 03:04:05",
                "time_source": "shoot",
                "chosen_url": "https://x/a.jpg",
                "quality": "raw",
            },
        )
        store.set_photo_file("123", "a1", "s1", "media/123/a1/20200102_030405_abc.jpg", 100, "written")
        store.upsert_mood(
            "123",
            {"tid": "t1", "content": "你好", "created_at": "2020-01-02 08:00:00"},
        )
        store.set_mood_media("123", "t1", 0, "image", "https://x/m.jpg", "media/123/m.jpg", 10)

        stats = store.stats("123")
        assert stats["albums"] == 1
        assert stats["photos"] == 1
        assert stats["downloaded"] == 1
        assert stats["moods"] == 1

        index = export_bundle(store, "123", tmp_path, "墨语")

    assert index.exists()
    assert (tmp_path / "data.js").exists()
    html = index.read_text(encoding="utf-8")
    assert "墨语" in html
    assert "data.js" in html
    data = (tmp_path / "data.js").read_text(encoding="utf-8")
    assert "media/123/a1/20200102_030405_abc.jpg" in data


def test_export_backfills_existing_jpegs_and_preserves_original_date(tmp_path, monkeypatch):
    from qzone_archiver import media

    monkeypatch.setattr(media, "EXIFTOOL", None)
    fixture = Path(__file__).parent / "fixtures" / "tiny.jpg"
    for name in ("album.jpg", "mood.jpg", "original.jpg"):
        shutil.copyfile(fixture, tmp_path / name)
    original = piexif.load(str(tmp_path / "original.jpg"))
    original["Exif"][piexif.ExifIFD.DateTimeOriginal] = b"2001:02:03 04:05:06"
    piexif.insert(piexif.dump(original), str(tmp_path / "original.jpg"))

    with Store(tmp_path / "qzone.db") as store:
        store.upsert_account("123")
        store.upsert_album("123", {"id": "a", "createtime": "2020-01-02 03:04:05"})
        for sloc, name in (("1", "album.jpg"), ("2", "original.jpg")):
            store.upsert_photo("123", "a", {"sloc": sloc})
            store.set_photo_file("123", "a", sloc, name, 1, "mtime-only")
        store.upsert_mood("123", {"tid": "t", "created_at": "2021-02-03 04:05:06"})
        store.set_mood_media("123", "t", 0, "image", "", "mood.jpg", 1)
        export_bundle(store, "123", tmp_path)
        assert store.photo_exists("123", "a", "1")["exif_status"] == "written"
        assert store.photo_exists("123", "a", "2")["exif_status"] == "preserved"

    album = piexif.load(str(tmp_path / "album.jpg"))["Exif"]
    assert album[piexif.ExifIFD.DateTimeOriginal] == b"2020:01:02 03:04:05"
    assert b"time_source=album_created" in album[piexif.ExifIFD.UserComment]
    mood = piexif.load(str(tmp_path / "mood.jpg"))["Exif"]
    assert mood[piexif.ExifIFD.DateTimeOriginal] == b"2021:02:03 04:05:06"
    assert b"time_source=mood_created" in mood[piexif.ExifIFD.UserComment]
    assert piexif.load(str(tmp_path / "original.jpg"))["Exif"][piexif.ExifIFD.DateTimeOriginal] == b"2001:02:03 04:05:06"
