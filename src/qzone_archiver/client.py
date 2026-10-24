"""QQ 空间 HTTP 客户端：Cookie、g_tk、JSONP 解析、限速与重试。"""

from __future__ import annotations

import json
import random
import time
from threading import Event
from typing import Any

import httpx

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class QzoneError(RuntimeError):
    """QQ 空间接口返回的业务错误。"""


def calc_gtk(skey: str) -> str:
    """由 p_skey 计算 QQ 空间 CGI 需要的 g_tk（CSRF token）。"""
    h = 5381
    for ch in skey:
        h += (h << 5) + ord(ch)
    return str(h & 0x7FFFFFFF)


def parse_cookie(cookie: str) -> dict[str, str]:
    """把 `a=b; c=d` 形式的 Cookie 头解析成字典。"""
    result: dict[str, str] = {}
    for part in cookie.split(";"):
        key, sep, value = part.strip().partition("=")
        if sep and key:
            result[key] = value
    return result


def cookie_to_str(cookies: dict[str, str]) -> str:
    return "; ".join(f"{k}={v}" for k, v in cookies.items() if v)


def uin_from_cookie(cookies: dict[str, str]) -> str:
    """从 uin / p_uin 中取出纯数字 QQ 号。"""
    for key in ("uin", "p_uin"):
        raw = cookies.get(key, "").lstrip("o").lstrip("0")
        if raw.isdigit():
            return raw
    return ""


def parse_jsonp(text: str) -> dict[str, Any]:
    """剥离腾讯接口的 callback(...) 外壳并解析 JSON。"""
    start = text.find("(")
    end = text.rfind(")")
    if start == -1 or end <= start:
        raise QzoneError(f"不是合法的 JSONP 响应：{text[:120]}")
    return json.loads(text[start + 1 : end])


class QzoneClient:
    """带限速和重试的 QQ 空间 API 客户端。"""

    def __init__(
        self,
        cookie: str,
        *,
        uin: str | None = None,
        timeout: float = 20.0,
        interval: float = 0.8,
        retries: int = 3,
        cancel: Event | None = None,
    ) -> None:
        self.cookies = parse_cookie(cookie)
        self.cookie = cookie_to_str(self.cookies)
        self.uin = uin or uin_from_cookie(self.cookies)
        self.gtk = calc_gtk(self.cookies.get("p_skey") or self.cookies.get("skey", ""))
        self.interval = interval
        self.retries = retries
        self.cancel = cancel or Event()
        self._last_request = 0.0
        self._http = httpx.Client(
            timeout=timeout,
            follow_redirects=False,
            headers={
                "user-agent": USER_AGENT,
                "referer": f"https://user.qzone.qq.com/{self.uin}",
                "origin": "https://user.qzone.qq.com",
            },
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> QzoneClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _wait(self) -> None:
        """按配置的最小间隔限速，并加入少量抖动，降低触发风控的概率。"""
        if self.cancel.is_set():
            raise QzoneError("已停止请求")
        if self.interval <= 0:
            return
        elapsed = time.monotonic() - self._last_request
        delay = self.interval - elapsed + random.uniform(0, 0.2)
        if delay > 0 and self.cancel.wait(delay):
            raise QzoneError("已停止请求")
        self._last_request = time.monotonic()

    def get(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        """发 GET 请求；对限流和临时故障做指数退避。"""
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            self._wait()
            try:
                resp = self._http.get(
                    url,
                    params=params,
                    headers={"cookie": self.cookie},
                )
            except httpx.HTTPError as exc:
                last_error = exc
                self.cancel.wait(1.5 * (attempt + 1))
                continue

            # 接口可能在响应里补发 qq_photo_key，后续相册请求要带上。
            photo_key = resp.cookies.get("qq_photo_key")
            if photo_key and "qq_photo_key" not in self.cookies:
                self.cookies["qq_photo_key"] = photo_key
                self.cookie = cookie_to_str(self.cookies)

            if resp.status_code in (429, 500, 502, 503, 504):
                last_error = QzoneError(f"HTTP {resp.status_code}")
                self.cancel.wait(2.0 * (attempt + 1))
                continue

            if resp.status_code >= 400:
                raise QzoneError(f"HTTP {resp.status_code}: {resp.text[:200]}")

            return resp

        raise QzoneError(f"请求失败（已重试 {self.retries} 次）：{last_error}")

    def get_jsonp(
        self,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """请求 JSONP 接口并返回解析后的字典；code != 0 时抛出业务错误。"""
        resp = self.get(url, params)
        data = parse_jsonp(resp.text)
        code = int(data.get("code", 0) or 0)
        if code != 0:
            message = data.get("message") or data.get("msg") or "未知错误"
            raise QzoneError(f"接口错误 code={code}: {message}")
        return data

    def get_text(self, url: str, params: dict[str, Any] | None = None) -> str:
        return self.get(url, params).text
