from threading import Event

import httpx
import pytest
import respx

from qzone_archiver.auth import XLOGIN_URL, QzoneError, _validate_login_url, login_with_qrcode


def test_qr_callback_and_ticket_cookie_flow(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    pictures = []
    with respx.mock:
        respx.get(XLOGIN_URL).mock(
            return_value=httpx.Response(
                200, headers={"set-cookie": "pt_login_sig=sig; Domain=qq.com; Path=/"}
            )
        )
        respx.get("https://ssl.ptlogin2.qq.com/ptqrshow").mock(
            return_value=httpx.Response(
                200, content=b"qr image", headers={"set-cookie": "qrsig=qr; Domain=qq.com; Path=/"}
            )
        )
        respx.get("https://ssl.ptlogin2.qq.com/ptqrlogin").mock(
            return_value=httpx.Response(
                200, text="ptuiCB('0','0','https://ptlogin2.qq.com/check_sig','0','登录成功','昵称,带逗号');"
            )
        )
        respx.get("https://ptlogin2.qq.com/check_sig").mock(
            return_value=httpx.Response(
                200,
                headers=[
                    ("set-cookie", "p_uin=o123; Domain=qq.com; Path=/"),
                    ("set-cookie", "p_skey=key; Domain=qq.com; Path=/"),
                ],
            )
        )
        result = login_with_qrcode(interval=0, on_qrcode=pictures.append)
    assert result["uin"] == "123"
    assert pictures == [b"qr image"]
    assert not (tmp_path / "qrcode.png").exists()


@pytest.mark.parametrize(
    "url", ["https://qq.com.evil.example/ticket", "http://ptlogin2.qq.com/ticket", "https://evil.example/"]
)
def test_login_redirect_rejects_other_hosts(url):
    with pytest.raises(QzoneError):
        _validate_login_url(url)


def test_login_cancellation(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    event = Event()
    with respx.mock:
        respx.get(XLOGIN_URL).mock(
            return_value=httpx.Response(200, headers={"set-cookie": "pt_login_sig=sig"})
        )
        respx.get("https://ssl.ptlogin2.qq.com/ptqrshow").mock(
            return_value=httpx.Response(200, content=b"qr", headers={"set-cookie": "qrsig=qr"})
        )
        with pytest.raises(QzoneError, match="取消"):
            login_with_qrcode(on_qrcode=lambda _: event.set(), cancel=event, interval=0)
