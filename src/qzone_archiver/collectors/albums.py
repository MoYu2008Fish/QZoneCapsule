"""相册与照片采集。"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from ..client import QzoneClient, QzoneError
from ..utils import parse_qzone_time, to_iso

ALBUM_LIST_URL = "https://user.qzone.qq.com/proxy/domain/photo.qzone.qq.com/fcgi-bin/fcg_list_album_v3"
PHOTO_LIST_URL = "https://user.qzone.qq.com/proxy/domain/photo.qzone.qq.com/fcgi-bin/cgi_list_photo"

ALBUM_PAGE_SIZE = 30
PHOTO_PAGE_SIZE = 500


def fetch_albums(client: QzoneClient, target_uin: str) -> Iterator[dict[str, Any]]:
    """分页拉取相册列表。"""
    offset = 0
    seen_ids: set[str] = set()
    while True:
        data = client.get_jsonp(
            ALBUM_LIST_URL,
            {
                "g_tk": client.gtk,
                "callback": "shine_Callback",
                "hostUin": target_uin,
                "uin": client.uin,
                "appid": 4,
                "inCharset": "utf-8",
                "outCharset": "utf-8",
                "source": "qzone",
                "plat": "qzone",
                "format": "jsonp",
                "notice": 0,
                "filter": 1,
                "handset": 4,
                "pageNumModeSort": 40,
                "pageNumModeClass": 15,
                "needUserInfo": 1,
                "idcNum": 4,
                "mode": 2,
                "pageStart": offset,
                "pageNum": ALBUM_PAGE_SIZE,
                "callbackFun": "shine",
            },
        )

        payload = data.get("data") or {}
        albums = payload.get("albumList") or data.get("albumList") or []
        fresh = [
            album for album in albums if str(album.get("id") or album.get("albumId") or "") not in seen_ids
        ]
        if albums and not fresh:
            raise QzoneError("相册接口重复返回同一页，已停止以防循环")
        for album in fresh:
            normalized = normalize_album(album)
            seen_ids.add(normalized["id"])
            yield normalized

        total = int(payload.get("albumsInUser") or 0)
        next_start = int(payload.get("nextPageStart") or 0)
        if not albums or (total and len(seen_ids) >= total):
            break
        if next_start <= offset:
            if not total and len(albums) < ALBUM_PAGE_SIZE:
                break
            next_start = offset + len(albums)
        offset = next_start


def fetch_photos(client: QzoneClient, target_uin: str, album_id: str) -> Iterator[dict[str, Any]]:
    """分页拉取相册内照片；pos 按请求页大小递增。"""
    offset = 0
    seen = 0
    seen_ids: set[str] = set()
    while True:
        data = client.get_jsonp(
            PHOTO_LIST_URL,
            {
                "g_tk": client.gtk,
                "callback": "shine_Callback",
                "mode": 0,
                "idcNum": 4,
                "hostUin": target_uin,
                "topicId": album_id,
                "noTopic": 0,
                "uin": client.uin,
                "pageStart": offset,
                "pageNum": PHOTO_PAGE_SIZE,
                "skipCmtCount": 0,
                "singleurl": 1,
                "batchId": "",
                "notice": 0,
                "appid": 4,
                "inCharset": "utf-8",
                "outCharset": "utf-8",
                "source": "qzone",
                "plat": "qzone",
                "outstyle": "json",
                "format": "jsonp",
                "json_esc": 1,
                "callbackFun": "shine",
            },
        )

        payload = data.get("data") or {}
        photos = payload.get("photoList") or []
        fresh = [
            photo for photo in photos if str(photo.get("sloc") or photo.get("lloc") or "") not in seen_ids
        ]
        if photos and not fresh:
            raise QzoneError("照片接口重复返回同一页，已停止以防循环")
        for photo in fresh:
            normalized = normalize_photo(photo)
            seen_ids.add(normalized["sloc"])
            yield normalized

        seen += len(photos)
        total = int(payload.get("totalInAlbum") or payload.get("total") or 0)
        if not photos or (total and seen >= total) or (not total and len(photos) < PHOTO_PAGE_SIZE):
            break
        offset += PHOTO_PAGE_SIZE


def normalize_album(album: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(album.get("id") or album.get("albumId") or ""),
        "name": album.get("name") or "未命名相册",
        "desc": album.get("desc") or "",
        "createtime": to_iso(parse_qzone_time(album.get("createtime"))),
        "modifytime": to_iso(parse_qzone_time(album.get("modifytime"))),
        "lastuploadtime": to_iso(parse_qzone_time(album.get("lastuploadtime"))),
        "total": int(album.get("total") or album.get("photoCount") or 0),
        "cover": album.get("pre") or album.get("cover") or "",
        "raw": album,
    }


def normalize_photo(photo: dict[str, Any]) -> dict[str, Any]:
    """把接口字段规整成统一结构，并决定原图优先级。"""
    url_raw = str(photo.get("raw") or "")
    url_origin = str(photo.get("origin_url") or photo.get("origin") or "")
    url_normal = str(photo.get("downloadUrl") or photo.get("url") or "")

    # raw_upload / origin_upload 为 1 才代表真的存在该规格，否则只是字段占位。
    if str(photo.get("raw_upload", "1")) not in ("1", "True", "true"):
        url_raw = ""
    if str(photo.get("origin_upload", "1")) not in ("1", "True", "true"):
        url_origin = ""

    chosen, quality = url_raw, "raw"
    if not chosen:
        chosen, quality = url_origin, "origin"
    if not chosen:
        chosen, quality = url_normal, "normal"

    # 优先尝试原图参数；同步服务负责失败后回退到其他候选地址。
    chosen = chosen.replace("b&bo=", "o&bo=", 1)

    upload_at = parse_qzone_time(photo.get("uploadtime") or photo.get("uploadTime"))
    shoot_at = parse_qzone_time(photo.get("rawshoottime") or photo.get("shoottime") or photo.get("shootTime"))
    time_source = "shoot" if shoot_at else ("upload" if upload_at else "none")

    return {
        "sloc": str(photo.get("sloc") or photo.get("lloc") or ""),
        "name": photo.get("name") or "",
        "desc": photo.get("desc") or "",
        "upload_at": to_iso(upload_at),
        "shoot_at": to_iso(shoot_at),
        "time_source": time_source,
        "url_raw": url_raw,
        "url_origin": url_origin,
        "url_normal": url_normal,
        "chosen_url": chosen,
        "quality": quality,
        "is_video": bool(photo.get("is_video")),
        "batch_id": photo.get("batchId") or "",
        "width": int(photo.get("width") or 0),
        "height": int(photo.get("height") or 0),
        "raw": photo,
    }
