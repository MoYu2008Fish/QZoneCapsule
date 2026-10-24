from qzone_archiver.collectors.albums import normalize_photo
from qzone_archiver.collectors.moods import normalize_mood


def test_photo_prefers_raw_and_shoot_time():
    photo = normalize_photo(
        {
            "sloc": "abc",
            "raw": "https://x/raw.jpg?b&bo=1",
            "raw_upload": 1,
            "origin_url": "https://x/origin.jpg",
            "origin_upload": 0,
            "url": "https://x/preview.jpg",
            "uploadtime": "2020-01-02 03:04:05",
            "rawshoottime": "2019-12-31 23:59:59",
        }
    )
    assert photo["quality"] == "raw"
    assert photo["chosen_url"] == "https://x/raw.jpg?o&bo=1"
    assert photo["time_source"] == "shoot"
    assert photo["shoot_at"] == "2019-12-31 23:59:59"
    assert photo["upload_at"] == "2020-01-02 03:04:05"


def test_photo_falls_back_to_origin_then_normal():
    origin = normalize_photo(
        {"sloc": "a", "raw_upload": 0, "origin_url": "https://x/o.jpg", "origin_upload": 1}
    )
    assert origin["quality"] == "origin"
    assert origin["chosen_url"] == "https://x/o.jpg"
    assert origin["time_source"] == "none"

    normal = normalize_photo({"sloc": "b", "url": "https://x/n.jpg"})
    assert normal["quality"] == "normal"
    assert normal["chosen_url"] == "https://x/n.jpg"


def test_mood_merges_long_content_and_picks_origin_image():
    mood = normalize_mood(
        {
            "tid": "t1",
            "content": "短文本",
            "conlist": [{"con": "长文"}, {"con": "后半段"}],
            "created_time": 1577923200,
            "lbs": {"idname": "福州"},
            "likecount": 3,
            "commenttotal": 5,
            "pic": [{"url1": "thumb", "url3": "large", "origin_url": "origin"}],
        }
    )
    assert mood["content"] == "长文后半段"
    assert mood["created_at"] == "2020-01-02 08:00:00"
    assert mood["location"] == "福州"
    assert mood["like_count"] == 3
    assert mood["comment_count"] == 5
    assert mood["images"][0]["url"] == "origin"


def test_mood_forward_prepends_original():
    mood = normalize_mood({"tid": "t2", "content": "转发", "rt_con": {"name": "某人", "content": "原文"}})
    assert "//某人：原文" in mood["content"]


class AlbumClient:
    gtk = "test"
    uin = "123"

    def __init__(self, pages):
        self.pages = iter(pages)
        self.offsets = []

    def get_jsonp(self, url, params):
        self.offsets.append(params["pageStart"])
        return {"data": next(self.pages)}


def test_album_pagination_without_cursor():
    from qzone_archiver.collectors.albums import fetch_albums

    client = AlbumClient(
        [
            {"albumList": [{"id": "a"}], "albumsInUser": 2},
            {"albumList": [{"id": "b"}], "albumsInUser": 2},
        ]
    )
    assert [a["id"] for a in fetch_albums(client, "123")] == ["a", "b"]
    assert client.offsets == [0, 1]


def test_repeated_album_page_stops_with_error():
    import pytest

    from qzone_archiver.client import QzoneError
    from qzone_archiver.collectors.albums import fetch_albums

    page = {"albumList": [{"id": "a"}], "albumsInUser": 10, "nextPageStart": 0}
    with pytest.raises(QzoneError, match="重复"):
        list(fetch_albums(AlbumClient([page, page]), "123"))
