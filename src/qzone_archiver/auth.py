"""登录、会话持久化与 Cookie 校验。"""

from __future__ import annotations

import csv
import json
import os
import stat
import time
from collections.abc import Callable
from pathlib import Path
from threading import Event
from typing import Any
from urllib.parse import urlparse

import httpx

from .client import (
    USER_AGENT,
    QzoneClient,
    QzoneError,
    calc_gtk,
    cookie_to_str,
    parse_cookie,
    uin_from_cookie,
)

LOGIN_APP_ID = "549000912"
LOGIN_DAID = "5"
JUMP_URL = "https://qzs.qq.com/qzone/v5/loginsucc.html?para=izone"
XLOGIN_URL = (
    "https://xui.ptlogin2.qq.com/cgi-bin/xlogin"
    "?proxy_url=https://qzs.qq.com/qzone/v6/portal/proxy.html&daid=5"
    "&&hide_title_bar=1&low_login=0&qlogin_auto_login=1&no_verifyimg=1"
    "&link_target=blank&appid=549000912&style=22&target=self"
    "&s_url=https://qzs.qq.com/qzone/v5/loginsucc.html?para=izone"
    "&pt_qr_app=手机QQ空间&pt_qr_link=https://z.qzone.com/download.html"
    "&self_regurl=https://qzs.qq.com/qzone/v6/reg/index.html"
    "&pt_qr_help_link=https://z.qzone.com/download.html&pt_no_auth=0"
)


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "qzone-archiver"


def session_path() -> Path:
    return config_dir() / "session.json"


def save_session(cookie: str, nickname: str = "") -> Path:
    """保存登录凭证，文件权限设为 600，避免同机其他用户读取。"""
    path = session_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    cookies = parse_cookie(cookie)
    payload = {
        "uin": uin_from_cookie(cookies),
        "nickname": nickname,
        "cookie": cookie_to_str(cookies),
        "g_tk": calc_gtk(cookies.get("p_skey", "")),
        "saved_at": int(time.time()),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    return path


def load_session() -> dict[str, Any] | None:
    path = session_path()
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not str(payload.get("uin", "")).isdigit():
            return None
        if not isinstance(payload.get("cookie"), str) or not payload["cookie"]:
            return None
        return payload
    except (OSError, json.JSONDecodeError):
        return None


def login_with_cookie(cookie: str) -> dict[str, Any]:
    """校验手工粘贴的 Cookie，返回会话信息。"""
    cookies = parse_cookie(cookie)
    missing = [k for k in ("p_skey", "p_uin") if not cookies.get(k)]
    if missing:
        raise QzoneError(f"Cookie 缺少关键字段：{', '.join(missing)}")

    uin = uin_from_cookie(cookies)
    if not uin:
        raise QzoneError("无法从 Cookie 中解析出 QQ 号")

    # 用相册列表接口做一次轻量校验，避免把失效 Cookie 写进会话。
    with QzoneClient(cookie, uin=uin) as client:
        data = client.get_jsonp(
            "https://user.qzone.qq.com/proxy/domain/photo.qzone.qq.com/fcgi-bin/fcg_list_album_v3",
            {
                "g_tk": client.gtk,
                "callback": "shine_Callback",
                "hostUin": uin,
                "uin": uin,
                "appid": 4,
                "inCharset": "utf-8",
                "outCharset": "utf-8",
                "source": "qzone",
                "plat": "qzone",
                "format": "jsonp",
                "notice": 0,
                "filter": 1,
                "handset": 4,
                "needUserInfo": 1,
                "idcNum": 4,
                "mode": 2,
                "pageStart": 0,
                "pageNum": 30,
                "callbackFun": "shine",
            },
        )

    nickname = str((data.get("data") or {}).get("userInfo", {}).get("name") or "")
    return {"uin": uin, "nickname": nickname, "cookie": cookie_to_str(cookies)}


def login_with_qrcode(
    interval: float = 1.0,
    timeout: int = 180,
    *,
    on_qrcode: Callable[[bytes], None] | None = None,
    on_status: Callable[[str], None] | None = None,
    cancel: Event | None = None,
) -> dict[str, Any]:
    """走 ptlogin 扫码登录，二维码保存为 qrcode.png，登录成功后返回凭证。"""
    cancel = cancel or Event()
    with httpx.Client(timeout=20, follow_redirects=False) as http:
        headers = {"user-agent": USER_AGENT}

        # 1. 取 pt_login_sig
        resp = http.get(XLOGIN_URL, headers=headers)
        login_sig = resp.cookies.get("pt_login_sig", "")
        if not login_sig:
            raise QzoneError("获取 pt_login_sig 失败")

        # 2. 下载二维码，qrsig 写在 Set-Cookie 中
        resp = http.get(
            "https://ssl.ptlogin2.qq.com/ptqrshow",
            params={
                "appid": LOGIN_APP_ID,
                "e": 2,
                "l": "M",
                "s": 3,
                "d": "72",
                "v": 4,
                "t": str(time.time()),
                "daid": LOGIN_DAID,
                "pt_3rd_aid": 0,
            },
            headers=headers,
        )
        qrsig = resp.cookies.get("qrsig", "")
        if not qrsig:
            raise QzoneError("获取 qrsig 失败")
        if cancel.is_set():
            raise QzoneError("已取消登录")
        if on_qrcode:
            on_qrcode(resp.content)
        else:
            Path("qrcode.png").write_bytes(resp.content)

        ptqrtoken = 0
        for ch in qrsig:
            ptqrtoken += (ptqrtoken << 5) + ord(ch)
        ptqrtoken &= 0x7FFFFFFF

        # 3. 轮询扫码状态
        redirect = ""
        cookies: dict[str, str] = {"qrsig": qrsig}
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if cancel.wait(interval):
                raise QzoneError("已取消登录")
            poll = http.get(
                "https://ssl.ptlogin2.qq.com/ptqrlogin",
                params={
                    "u1": JUMP_URL,
                    "ptqrtoken": str(ptqrtoken),
                    "ptredirect": 0,
                    "h": 1,
                    "t": 1,
                    "g": 1,
                    "from_ui": 1,
                    "ptlang": 2052,
                    "action": f"0-0-{int(time.time() * 1000)}",
                    "js_ver": "21010623",
                    "js_type": 1,
                    "login_sig": login_sig,
                    "pt_uistyle": 40,
                    "aid": LOGIN_APP_ID,
                    "daid": LOGIN_DAID,
                    "has_onekey": 1,
                },
                headers={**headers, "cookie": f"qrsig={qrsig};"},
            )
            for key in ("ptcz", "RK"):
                value = poll.cookies.get(key)
                if value:
                    cookies[key] = value

            text = poll.text
            payload = text[text.find("(") + 1 : text.rfind(")")]
            fields = next(csv.reader([payload], quotechar="'", escapechar="\\", skipinitialspace=True))
            state = fields[0] if fields else ""

            if state == "65":
                raise QzoneError("二维码已过期，请重新运行 login --qrcode")
            if state == "67":
                if on_status:
                    on_status("已扫码，请在手机 QQ 上确认登录")
                continue
            if state == "0":
                redirect = fields[2]
                break
            if state not in ("66",):
                raise QzoneError(f"扫码登录失败，状态码：{state}")

        if not redirect:
            raise QzoneError("扫码登录超时")

        # 4. 跟随换票地址，收集空间 CGI 需要的 Cookie
        _validate_login_url(redirect)
        resp = http.get(redirect, headers=headers)
        _collect_cookies(resp, cookies)

        if "p_skey" not in cookies:
            location = resp.headers.get("location", "")
            if location:
                _validate_login_url(location)
                resp2 = http.get(location, headers=headers)
                _collect_cookies(resp2, cookies)

        if "p_skey" not in cookies:
            raise QzoneError("登录成功但未拿到 p_skey")

        cookie_str = cookie_to_str(cookies)
        uin = uin_from_cookie(cookies)
        if not uin:
            raise QzoneError("登录响应中缺少 QQ 号，请重新扫码")
        return {"uin": uin, "nickname": "", "cookie": cookie_str}


def _validate_login_url(url: str) -> None:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    if parsed.scheme != "https" or not (host == "qq.com" or host.endswith(".qq.com")):
        raise QzoneError("登录换票地址无效，请重新扫码")


def _collect_cookies(resp: httpx.Response, target: dict[str, str]) -> None:
    wanted = {
        "uin",
        "skey",
        "p_uin",
        "pt4_token",
        "p_skey",
        "ptcz",
        "RK",
        "pt2ggid",
        "pgv_pvid",
    }
    for key, value in resp.cookies.items():
        if key in wanted and value:
            target[key] = value
