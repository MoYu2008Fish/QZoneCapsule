"""导出：data.js + 离线 HTML 查看器。"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .store import Store


def export_bundle(store: Store, uin: str, out_dir: Path, nickname: str = "") -> Path:
    """把存档导出为可在浏览器直接打开的离线站点。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    data = build_data(store, uin)
    data["nickname"] = nickname

    # 用 data.js 而不是 data.json：file:// 下 fetch 会被浏览器拦截，script 不会。
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    (out_dir / "data.js").write_text(f"window.__QZONE_DATA__ = {payload};", encoding="utf-8")

    env = Environment(
        loader=FileSystemLoader(Path(__file__).parent / "templates"),
        autoescape=select_autoescape(["html"]),
    )
    template = env.get_template("index.html.j2")
    html = template.render(
        uin=uin,
        nickname=nickname or uin,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        stats=data["stats"],
    )
    index = out_dir / "index.html"
    index.write_text(html, encoding="utf-8")
    return index


def build_data(store: Store, uin: str) -> dict[str, Any]:
    albums = []
    album_map: dict[str, dict[str, Any]] = {}
    for row in store.iter_albums(uin):
        album = {
            "id": row["album_id"],
            "name": row["name"] or "未命名相册",
            "desc": row["description"] or "",
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
            "name": row["name"] or "",
            "desc": row["description"] or "",
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
        if row["album_id"] in album_map and item["path"]:
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


def _rel(path: str | None) -> str:
    """数据库里存的是相对备份根目录的路径，导出时保持相对即可。"""
    if not path:
        return ""
    return str(path).replace("\\", "/").lstrip("/")
