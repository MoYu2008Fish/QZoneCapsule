import pytest

from qzone_archiver.client import (
    QzoneClient,
    QzoneError,
    calc_gtk,
    cookie_to_str,
    parse_cookie,
    parse_jsonp,
    uin_from_cookie,
)


def test_calc_gtk_is_stable():
    # g_tk 只依赖 p_skey，值固定后才能保证接口签名一致。
    assert calc_gtk("") == "5381"
    assert calc_gtk("abc") == calc_gtk("abc")
    assert calc_gtk("abc") != calc_gtk("abd")


def test_parse_and_join_cookie():
    cookies = parse_cookie("uin=o012345; p_skey=abc==; pt4_token=xyz; empty=")
    assert cookies["p_skey"] == "abc=="
    assert "empty=" not in cookie_to_str(cookies)


def test_uin_from_cookie():
    assert uin_from_cookie({"uin": "o0012345"}) == "12345"
    assert uin_from_cookie({"p_uin": "o123456"}) == "123456"
    assert uin_from_cookie({}) == ""


def test_parse_jsonp():
    assert parse_jsonp('shine_Callback({"code":0,"data":{"x":1}});') == {
        "code": 0,
        "data": {"x": 1},
    }


def test_photo_control_characters_and_plain_json():
    assert parse_jsonp('cb({"code":0,"data":{"desc":"第一行\n第二行\t尾部"}})')["data"]["desc"] == (
        "第一行\n第二行\t尾部"
    )
    assert parse_jsonp('\ufeff {"code":0,"data":{}}')["code"] == 0


def test_photo_broken_string_keeps_ids_and_media_urls():
    payload = (
        'cb({"code":0,"data":{"topic":{"name":"旧相册\\",\n'
        '"desc":"说明"},"totalInAlbum":2,"photoList":['
        '{"sloc":"p1","url":"https://example.com/1.jpg"},'
        '{"sloc":"p2","url":"https://example.com/2.jpg"}]}});'
    )
    with pytest.raises(QzoneError):
        parse_jsonp(payload)
    data = parse_jsonp(payload, repair=True)["data"]
    assert data["totalInAlbum"] == 2
    assert [(p["sloc"], p["url"]) for p in data["photoList"]] == [
        ("p1", "https://example.com/1.jpg"),
        ("p2", "https://example.com/2.jpg"),
    ]


@pytest.mark.parametrize(
    "payload",
    [
        "<html>secret cookie</html>",
        'cb({"code":0,"data":{"photoList":[',
        'cb({"code":0,"data":{"secret":"broken"quote"}})',
    ],
)
def test_unrecoverable_responses_are_not_empty_success(payload):
    with pytest.raises(QzoneError) as error:
        parse_jsonp(payload, repair=True)
    assert "secret" not in str(error.value)


def test_repaired_photo_response_still_checks_business_error(respx_mock):
    import httpx

    url = "https://user.qzone.qq.com/proxy/domain/photo.qzone.qq.com/fcgi-bin/cgi_list_photo"
    respx_mock.get(url).mock(
        return_value=httpx.Response(200, text='cb({"code":-1,"message":"denied","data":{"photoList":[],}})')
    )
    with (
        QzoneClient("p_uin=o123; p_skey=test", interval=0) as client,
        pytest.raises(QzoneError, match="code=-1"),
    ):
        client.get_jsonp(url)
