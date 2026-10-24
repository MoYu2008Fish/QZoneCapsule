from pathlib import Path

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
