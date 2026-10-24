from qzone_archiver.client import calc_gtk, cookie_to_str, parse_cookie, parse_jsonp, uin_from_cookie


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
