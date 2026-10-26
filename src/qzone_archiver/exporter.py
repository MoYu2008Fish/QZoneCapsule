"""导出：data.js + 离线 HTML 查看器。"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .emotions import EMOTIONS
from .store import Store
from .text import photo_text_candidate, recover_photo_text
from .theme import css_variables


def export_bundle(
    store: Store, uin: str, out_dir: Path, nickname: str = "", *, merged: bool | None = None
) -> Path:
    """把存档导出为可在浏览器直接打开的离线站点。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    if merged is None:
        merged = store.db.execute("SELECT COUNT(*) FROM accounts").fetchone()[0] > 1
    if merged:
        accounts = list(store.db.execute("SELECT uin, nickname FROM accounts ORDER BY uin"))
        data = combine_data([build_data(store, row["uin"]) for row in accounts])
        data["accounts"] = [dict(row) for row in accounts]
        nickname = "多账号合并存档"
    else:
        data = build_data(store, uin)
    data["nickname"] = nickname
    data["emotions"] = {key: {"name": name, "emoji": emoji} for key, (name, emoji) in EMOTIONS.items()}

    # 用 data.js 而不是 data.json：file:// 下 fetch 会被浏览器拦截，script 不会。
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    (out_dir / "data.js").write_text(f"window.__QZONE_DATA__ = {payload};", encoding="utf-8")

    env = Environment(
        loader=FileSystemLoader(Path(__file__).parent / "templates"),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("index.html.j2")
    html = template.render(
        uin="" if merged else uin,
        nickname=nickname or uin,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        stats=data["stats"],
        theme_variables=css_variables(),
    )
    index = out_dir / "index.html"
    index.write_text(html, encoding="utf-8")
    return index


def combine_data(bundles: list[dict[str, Any]]) -> dict[str, Any]:
    """Namespace content identities by account while keeping media paths intact."""
    result: dict[str, Any] = {"uin": "", "albums": [], "photos": [], "moods": [], "stats": {}}
    for data in bundles:
        uin = data["uin"]
        for photo in data["photos"]:
            result["photos"].append({**photo, "uin": uin, "album_id": f"{uin}:{photo['album_id']}"})
        for album in data["albums"]:
            result["albums"].append(
                {
                    **album,
                    "uin": uin,
                    "id": f"{uin}:{album['id']}",
                    "photos": [{**photo, "uin": uin} for photo in album["photos"]],
                }
            )
        result["moods"].extend({**mood, "uin": uin} for mood in data["moods"])
        for key, value in data["stats"].items():
            result["stats"][key] = result["stats"].get(key, 0) + value
    for key in ("photos", "moods"):
        result[key].sort(key=lambda item: item.get("time") or "", reverse=True)
    return result


def build_data(store: Store, uin: str) -> dict[str, Any]:
    def decoded(value):
        return recover_photo_text(value or "")[0]

    albums = []
    album_map: dict[str, dict[str, Any]] = {}
    for row in store.iter_albums(uin):
        album = {
            "id": row["album_id"],
            "name": decoded(row["name"]) or "未命名相册",
            "desc": decoded(row["description"]),
            "text_note": recover_photo_text(row["description"] or "")[1],
            "created_at": row["created_at"],
            "last_upload_at": row["last_upload_at"],
            "cover": _rel(row["cover_url"]),
            "photos": [],
        }
        albums.append(album)
        album_map[row["album_id"]] = album

    photos = []
    for row in store.iter_photos(uin):
        item = {
            "album_id": row["album_id"],
            "sloc": row["sloc"],
            "name": decoded(row["name"]),
            "desc": decoded(row["description"]),
            "text_note": recover_photo_text(row["description"] or "")[1],
            "original_desc": row["description"] or "",
            "time": row["shoot_at"] or row["upload_at"],
            "time_source": row["time_source"],
            "upload_at": row["upload_at"],
            "quality": row["quality"],
            "exif_status": row["exif_status"],
            "is_video": bool(row["is_video"]),
            "path": _rel(row["local_path"]),
            "bytes": row["bytes"] or 0,
        }
        photos.append(item)
        if row["album_id"] in album_map:
            album_map[row["album_id"]]["photos"].append(item)

    moods = []
    for row in store.iter_moods(uin):
        media = [
            {"kind": m["kind"], "path": _rel(m["local_path"]), "url": m["url"]}
            for m in store.mood_media(uin, row["tid"])
        ]
        moods.append(
            {
                "tid": row["tid"],
                "content": row["content"] or "",
                "time": row["created_at"],
                "location": row["location"] or "",
                "like_count": row["like_count"] or 0,
                "comment_count": row["comment_count"] or 0,
                "media": media,
            }
        )

    _restore_photo_descriptions(photos, moods, store.path.parent)

    return {
        "uin": uin,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "stats": {
            "albums": len(albums),
            "photos": len([p for p in photos if not p["is_video"]]),
            "videos": len([p for p in photos if p["is_video"]]),
            "moods": len(moods),
            "downloaded": len([p for p in photos if p["path"]]),
        },
        "albums": albums,
        "photos": photos,
        "moods": moods,
    }


def _restore_photo_descriptions(photos: list[dict], moods: list[dict], root: Path) -> None:
    """Use original post text only when the same local image and matching words prove the source."""
    from .library import local_media

    by_digest: dict[bytes, set[str]] = {}
    cache = {}

    def digest(relative):
        if relative not in cache:
            path = local_media(root, relative)
            try:
                if path:
                    checksum = hashlib.sha256()
                    with path.open("rb") as stream:
                        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                            checksum.update(chunk)
                    cache[relative] = checksum.digest()
                else:
                    cache[relative] = None
            except OSError:
                cache[relative] = None
        return cache[relative]

    damaged = [photo for photo in photos if photo_text_candidate(photo["original_desc"]) is not None]
    if not damaged:
        return
    for mood in moods:
        for media in mood["media"]:
            key = digest(media["path"])
            if key:
                by_digest.setdefault(key, set()).add(mood["content"])

    def words(value):
        value = re.sub(r"\[em\].*?\[/em\]", "", value)
        return "".join(re.findall(r"[\u4e00-\u9fffA-Za-z0-9]", value))

    for photo in damaged:
        candidates = by_digest.get(digest(photo["path"]), set())
        matches = [
            value
            for value in candidates
            if SequenceMatcher(
                None, words(photo_text_candidate(photo["original_desc"]) or photo["desc"]), words(value)
            ).ratio()
            >= 0.8
        ]
        if len(matches) == 1:
            photo["desc"] = matches[0]
            photo["text_note"] = "已用同一图片关联的说说原文校对编码；原始照片说明保留在数据库中"


def _rel(path: str | None) -> str:
    """数据库里存的是相对备份根目录的路径，导出时保持相对即可。"""
    if not path:
        return ""
    return str(path).replace("\\", "/").lstrip("/")
