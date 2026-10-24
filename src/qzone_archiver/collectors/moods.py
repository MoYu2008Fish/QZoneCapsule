"""说说（动态）采集：列表分页、正文与配图提取。"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from ..client import QzoneClient
from ..utils import parse_qzone_time, to_iso

MOOD_LIST_URL = (
    "https://user.qzone.qq.com/proxy/domain/taotao.qq.com/cgi-bin/emotion_cgi_msglist_v6"
)

PAGE_SIZE = 20  # 网页端固定 20，pos 必须按这个步长递增


def fetch_moods(
    client: QzoneClient,
    target_uin: str,
    *,
    start_pos: int = 0,
    max_pages: int | None = None,
) -> Iterator[dict[str, Any]]:
    """按页产出说说。

    pos 不能按返回条数增加：不可见的说说仍占位置，但不会出现在 msglist 里。
    """
    pos = start_pos
    pages = 0
    while True:
        data = client.get_jsonp(
            MOOD_LIST_URL,
            {
                "uin": target_uin,
                "ftype": 0,
                "sort": 0,
                "pos": pos,
                "num": PAGE_SIZE,
                "replynum": 100,
                "g_tk": client.gtk,
                "callback": "shine_Callback",
                "code_version": 1,
                "format": "jsonp",
                "need_private_comment": 1,
                "cgi_host": "https://taotao.qq.com/cgi-bin/emotion_cgi_msglist_v6",
            },
        )

        messages = data.get("msglist") or []
        for message in messages:
            yield normalize_mood(message)

        pages += 1
        total = int((data.get("usrinfo") or {}).get("msgnum") or 0)

        # msglist 为 null/空且仍声明有更多数据：更早的说说被封存或无权查看。
        if not messages or pos + PAGE_SIZE >= total:
            break
        if max_pages is not None and pages >= max_pages:
            break
        pos += PAGE_SIZE


def normalize_mood(message: dict[str, Any]) -> dict[str, Any]:
    content = message.get("content") or ""
    # 转发说说：正文在 rt_con 里，需要拼上原说说内容。
    rt_con = message.get("rt_con") or {}
    if rt_con.get("content"):
        prefix = f"//{rt_con.get('name') or ''}：{rt_con.get('content')}"
        content = f"{content}\n{prefix}" if content else prefix

    # 长文可能被折叠在 conlist 中，按顺序拼接。
    conlist = message.get("conlist") or []
    if conlist:
        parts = [str(item.get("con") or "") for item in conlist if item.get("con")]
        joined = "".join(parts).strip()
        if len(joined) > len(content):
            content = joined

    created = parse_qzone_time(message.get("created_time") or message.get("createTime"))
    lbs = message.get("lbs") or {}
    location = lbs.get("idname") or lbs.get("name") or ""

    return {
        "tid": str(message.get("tid") or message.get("id") or ""),
        "content": content.strip(),
        "created_at": to_iso(created),
        "location": location,
        "like_count": int(message.get("likecount") or message.get("like_count") or 0),
        "comment_count": int(message.get("commenttotal") or message.get("cmtnum") or 0),
        "images": extract_mood_images(message),
        "raw": message,
    }


def extract_mood_images(message: dict[str, Any]) -> list[dict[str, str]]:
    """提取说说配图，优先原图地址。"""
    result: list[dict[str, str]] = []
    for idx, pic in enumerate(message.get("pic") or []):
        if not isinstance(pic, dict):
            continue
        url = (
            pic.get("origin_url")
            or pic.get("raw")
            or pic.get("url3")
            or pic.get("url2")
            or pic.get("url1")
            or pic.get("url")
            or ""
        )
        if not url:
            continue
        result.append({"index": str(idx), "url": str(url), "kind": "image"})
    return result
