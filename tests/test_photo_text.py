import pytest

from qzone_archiver.exporter import build_data
from qzone_archiver.store import Store
from qzone_archiver.text import recover_photo_text


def garble(value):
    return value.encode("utf-8").decode("gb18030", errors="replace")


@pytest.mark.parametrize("text", ["旅行相册", "我的照片说明", "中文与 English 😊", "2021-05-01", "", "鍐鎴"])
def test_normal_text_is_unchanged(text):
    assert recover_photo_text(text) == (text, "")


def test_gbk_mojibake_recovers_readable_text():
    original = "这是我的照片说明"
    damaged = garble(original)
    repaired, note = recover_photo_text(damaged)
    assert repaired == original
    assert note
    assert damaged != repaired


def test_missing_bytes_are_marked_not_silently_dropped():
    repaired, note = recover_photo_text(garble("这是我的照片说明" * 2) + "翅")
    assert repaired.startswith("这是我的照片说明")
    assert "�" in repaired and "损坏" in note


def test_photo_description_recovers_from_same_image_without_changing_database(tmp_path):
    original = "这是我的照片说明"
    damaged = garble(original)
    (tmp_path / "photo.jpg").write_bytes(b"same-image")
    (tmp_path / "post.jpg").write_bytes(b"same-image")
    with Store(tmp_path / "qzone.db") as store:
        store.upsert_account("123")
        store.upsert_album("123", {"id": "a", "name": "旅行相册"})
        store.upsert_photo("123", "a", {"sloc": "p", "desc": damaged})
        store.set_photo_file("123", "a", "p", "photo.jpg", 10, "mtime-only")
        store.upsert_mood("123", {"tid": "m", "content": original})
        store.set_mood_media("123", "m", 0, "image", "", "post.jpg", 10)
        data = build_data(store, "123")
        photo = data["photos"][0]
        assert photo["desc"] == original
        assert photo["original_desc"] == damaged
        assert "同一图片" in photo["text_note"]
        assert data["albums"][0]["photos"][0]["desc"] == original
        assert store.photo_exists("123", "a", "p")["description"] == damaged
        # Different bytes must not be treated as the same photo.
        (tmp_path / "post.jpg").write_bytes(b"unrelated-image")
        assert "同一图片" not in build_data(store, "123")["photos"][0]["text_note"]


def test_ambiguous_source_posts_are_not_used(tmp_path):
    original = "这是我的照片说明"
    (tmp_path / "same.jpg").write_bytes(b"image")
    with Store(tmp_path / "qzone.db") as store:
        store.upsert_account("123")
        store.upsert_photo("123", "a", {"sloc": "p", "desc": garble(original)})
        store.set_photo_file("123", "a", "p", "same.jpg", 5, "mtime-only")
        for tid, content in (("m1", original), ("m2", original + "！")):
            store.upsert_mood("123", {"tid": tid, "content": content})
            store.set_mood_media("123", tid, 0, "image", "", "same.jpg", 5)
        assert "同一图片" not in build_data(store, "123")["photos"][0]["text_note"]
