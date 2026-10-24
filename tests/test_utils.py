from datetime import datetime

from qzone_archiver.utils import guess_ext, media_time, parse_qzone_time, safe_filename, short_hash


def test_parse_qzone_time_variants():
    assert parse_qzone_time(1577923200) == datetime(2020, 1, 2, 8, 0, 0)
    assert parse_qzone_time(1577923200000) == datetime(2020, 1, 2, 8, 0, 0)
    assert parse_qzone_time("2020-01-02 03:04:05") == datetime(2020, 1, 2, 3, 4, 5)
    assert parse_qzone_time("2020-01-02") == datetime(2020, 1, 2)
    assert parse_qzone_time("") is None
    assert parse_qzone_time("0") is None
    assert parse_qzone_time(None) is None


def test_safe_filename_strips_invalid_chars():
    assert safe_filename('a/b:c*d?"e"') == "a_b_c_d__e_"
    assert safe_filename("   ") == "untitled"
    assert len(safe_filename("x" * 200)) == 80


def test_guess_ext_prefers_content_type():
    assert guess_ext("https://x/a.jpg", "image/png") == ".png"
    assert guess_ext("https://x/a.PNG", "") == ".png"
    assert guess_ext("https://x/a", "", ".jpg") == ".jpg"


def test_media_time_and_hash():
    stamp, timeline = media_time(datetime(2020, 1, 2, 3, 4, 5))
    assert stamp == "20200102_030405"
    assert timeline == "2020/01"
    assert short_hash("abc") == short_hash("abc")
    assert len(short_hash("abc")) == 10
