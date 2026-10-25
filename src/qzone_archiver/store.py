"""SQLite 存档：相册、照片、说说、媒体文件与同步游标。"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    uin         TEXT PRIMARY KEY,
    nickname    TEXT,
    updated_at  TEXT
);

CREATE TABLE IF NOT EXISTS albums (
    uin             TEXT NOT NULL,
    album_id        TEXT NOT NULL,
    name            TEXT,
    description     TEXT,
    created_at      TEXT,
    modified_at     TEXT,
    last_upload_at  TEXT,
    photo_count     INTEGER,
    cover_url       TEXT,
    raw_json        TEXT,
    fetched_at      TEXT,
    PRIMARY KEY (uin, album_id)
);

CREATE TABLE IF NOT EXISTS photos (
    uin           TEXT NOT NULL,
    album_id      TEXT NOT NULL,
    sloc          TEXT NOT NULL,
    name          TEXT,
    description   TEXT,
    upload_at     TEXT,
    shoot_at      TEXT,
    time_source   TEXT,
    url_raw       TEXT,
    url_origin    TEXT,
    url_normal    TEXT,
    chosen_url    TEXT,
    quality       TEXT,
    is_video      INTEGER DEFAULT 0,
    batch_id      TEXT,
    width         INTEGER,
    height        INTEGER,
    local_path    TEXT,
    bytes         INTEGER,
    exif_status   TEXT,
    raw_json      TEXT,
    fetched_at    TEXT,
    PRIMARY KEY (uin, album_id, sloc)
);

CREATE INDEX IF NOT EXISTS idx_photos_time ON photos (uin, shoot_at);

CREATE TABLE IF NOT EXISTS moods (
    uin            TEXT NOT NULL,
    tid            TEXT NOT NULL,
    content        TEXT,
    created_at     TEXT,
    location       TEXT,
    like_count     INTEGER,
    comment_count  INTEGER,
    raw_json       TEXT,
    fetched_at     TEXT,
    PRIMARY KEY (uin, tid)
);

CREATE INDEX IF NOT EXISTS idx_moods_time ON moods (uin, created_at);

CREATE TABLE IF NOT EXISTS mood_media (
    uin         TEXT NOT NULL,
    tid         TEXT NOT NULL,
    idx         INTEGER NOT NULL,
    kind        TEXT,
    url         TEXT,
    local_path  TEXT,
    bytes       INTEGER,
    PRIMARY KEY (uin, tid, idx)
);

CREATE TABLE IF NOT EXISTS sync_state (
    uin         TEXT NOT NULL,
    kind        TEXT NOT NULL,
    key         TEXT NOT NULL,
    cursor      TEXT,
    updated_at  TEXT,
    PRIMARY KEY (uin, kind, key)
);
"""


class Store:
    def __init__(self, path: Path | str, *, readonly: bool = False) -> None:
        self.path = Path(path)
        if readonly:
            self.db = sqlite3.connect(self.path.resolve().as_uri() + "?mode=ro", uri=True, timeout=30)
            self.db.row_factory = sqlite3.Row
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.executescript(SCHEMA)
        self.db.commit()

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ---------- 账号 ----------

    def upsert_account(self, uin: str, nickname: str = "") -> None:
        self.db.execute(
            """INSERT INTO accounts (uin, nickname, updated_at) VALUES (?, ?, ?)
               ON CONFLICT(uin) DO UPDATE SET
                 nickname = COALESCE(NULLIF(excluded.nickname, ''), accounts.nickname),
                 updated_at = excluded.updated_at""",
            (uin, nickname, _now()),
        )
        self.db.commit()

    # ---------- 相册 ----------

    def upsert_album(self, uin: str, album: dict[str, Any], cover: str = "") -> None:
        self.db.execute(
            """INSERT INTO albums (
                   uin, album_id, name, description, created_at, modified_at,
                   last_upload_at, photo_count, cover_url, raw_json, fetched_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(uin, album_id) DO UPDATE SET
                   name = excluded.name,
                   description = excluded.description,
                   created_at = excluded.created_at,
                   modified_at = excluded.modified_at,
                   last_upload_at = excluded.last_upload_at,
                   photo_count = excluded.photo_count,
                   cover_url = excluded.cover_url,
                   raw_json = excluded.raw_json,
                   fetched_at = excluded.fetched_at""",
            (
                uin,
                str(album.get("id", "")),
                album.get("name", ""),
                album.get("desc", ""),
                album.get("createtime") or album.get("created_at"),
                album.get("modifytime") or album.get("modified_at"),
                album.get("lastuploadtime") or album.get("last_upload_at"),
                int(album.get("total") or album.get("photo_count") or 0),
                cover,
                json.dumps(album, ensure_ascii=False),
                _now(),
            ),
        )
        self.db.commit()

    # ---------- 照片 ----------

    def upsert_photo(self, uin: str, album_id: str, photo: dict[str, Any]) -> None:
        self.db.execute(
            """INSERT INTO photos (
                   uin, album_id, sloc, name, description, upload_at, shoot_at, time_source,
                   url_raw, url_origin, url_normal, chosen_url, quality, is_video, batch_id,
                   width, height, raw_json, fetched_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(uin, album_id, sloc) DO UPDATE SET
                   name = excluded.name,
                   description = excluded.description,
                   upload_at = excluded.upload_at,
                   shoot_at = excluded.shoot_at,
                   time_source = excluded.time_source,
                   url_raw = excluded.url_raw,
                   url_origin = excluded.url_origin,
                   url_normal = excluded.url_normal,
                   chosen_url = excluded.chosen_url,
                   quality = excluded.quality,
                   is_video = excluded.is_video,
                   batch_id = excluded.batch_id,
                   width = excluded.width,
                   height = excluded.height,
                   raw_json = excluded.raw_json,
                   fetched_at = excluded.fetched_at""",
            (
                uin,
                str(album_id),
                str(photo.get("sloc", "")),
                photo.get("name", ""),
                photo.get("desc", ""),
                photo.get("upload_at"),
                photo.get("shoot_at"),
                photo.get("time_source"),
                photo.get("url_raw", ""),
                photo.get("url_origin", ""),
                photo.get("url_normal", ""),
                photo.get("chosen_url", ""),
                photo.get("quality", ""),
                1 if photo.get("is_video") else 0,
                str(photo.get("batch_id", "") or ""),
                int(photo.get("width") or 0),
                int(photo.get("height") or 0),
                json.dumps(photo.get("raw"), ensure_ascii=False) if photo.get("raw") else None,
                _now(),
            ),
        )
        self.db.commit()

    def set_photo_file(
        self,
        uin: str,
        album_id: str,
        sloc: str,
        local_path: str,
        bytes_: int,
        exif_status: str,
    ) -> None:
        self.db.execute(
            """UPDATE photos SET local_path = ?, bytes = ?, exif_status = ?
               WHERE uin = ? AND album_id = ? AND sloc = ?""",
            (local_path, bytes_, exif_status, uin, str(album_id), sloc),
        )
        self.db.commit()

    def photo_exists(self, uin: str, album_id: str, sloc: str) -> sqlite3.Row | None:
        return self.db.execute(
            "SELECT * FROM photos WHERE uin = ? AND album_id = ? AND sloc = ?",
            (uin, str(album_id), sloc),
        ).fetchone()

    # ---------- 说说 ----------

    def upsert_mood(self, uin: str, mood: dict[str, Any]) -> None:
        self.db.execute(
            """INSERT INTO moods (
                   uin, tid, content, created_at, location, like_count, comment_count, raw_json, fetched_at
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(uin, tid) DO UPDATE SET
                   content = excluded.content,
                   created_at = excluded.created_at,
                   location = excluded.location,
                   like_count = excluded.like_count,
                   comment_count = excluded.comment_count,
                   raw_json = excluded.raw_json,
                   fetched_at = excluded.fetched_at""",
            (
                uin,
                str(mood.get("tid", "")),
                mood.get("content", ""),
                mood.get("created_at"),
                mood.get("location", ""),
                int(mood.get("like_count") or 0),
                int(mood.get("comment_count") or 0),
                json.dumps(mood.get("raw"), ensure_ascii=False) if mood.get("raw") else None,
                _now(),
            ),
        )
        self.db.commit()

    def set_mood_media(self, uin: str, tid: str, idx: int, kind: str, url: str,
                       local_path: str = "", bytes_: int = 0) -> None:
        self.db.execute(
            """INSERT INTO mood_media (uin, tid, idx, kind, url, local_path, bytes)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(uin, tid, idx) DO UPDATE SET
                   kind = excluded.kind,
                   url = excluded.url,
                   local_path = COALESCE(NULLIF(excluded.local_path, ''), mood_media.local_path),
                   bytes = COALESCE(NULLIF(excluded.bytes, 0), mood_media.bytes)""",
            (uin, tid, idx, kind, url, local_path, bytes_),
        )
        self.db.commit()

    # ---------- 同步游标 ----------

    def set_cursor(self, uin: str, kind: str, key: str, cursor: str) -> None:
        self.db.execute(
            """INSERT INTO sync_state (uin, kind, key, cursor, updated_at) VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(uin, kind, key) DO UPDATE SET
                   cursor = excluded.cursor, updated_at = excluded.updated_at""",
            (uin, kind, key, cursor, _now()),
        )
        self.db.commit()

    def get_cursor(self, uin: str, kind: str, key: str) -> str:
        row = self.db.execute(
            "SELECT cursor FROM sync_state WHERE uin = ? AND kind = ? AND key = ?",
            (uin, kind, key),
        ).fetchone()
        return row["cursor"] if row else ""

    # ---------- 导出与统计 ----------

    def iter_photos(self, uin: str) -> Iterator[sqlite3.Row]:
        yield from self.db.execute(
            "SELECT * FROM photos WHERE uin = ? ORDER BY COALESCE(shoot_at, upload_at) DESC",
            (uin,),
        )

    def iter_albums(self, uin: str) -> Iterator[sqlite3.Row]:
        yield from self.db.execute(
            "SELECT * FROM albums WHERE uin = ? ORDER BY COALESCE(last_upload_at, created_at) DESC",
            (uin,),
        )

    def iter_moods(self, uin: str) -> Iterator[sqlite3.Row]:
        yield from self.db.execute(
            "SELECT * FROM moods WHERE uin = ? ORDER BY created_at DESC", (uin,)
        )

    def mood_media(self, uin: str, tid: str) -> list[sqlite3.Row]:
        return list(
            self.db.execute(
                "SELECT * FROM mood_media WHERE uin = ? AND tid = ? ORDER BY idx ASC",
                (uin, tid),
            )
        )

    def stats(self, uin: str) -> dict[str, int]:
        def count(sql: str) -> int:
            return int(self.db.execute(sql, (uin,)).fetchone()[0])

        return {
            "albums": count("SELECT COUNT(*) FROM albums WHERE uin = ?"),
            "photos": count("SELECT COUNT(*) FROM photos WHERE uin = ?"),
            "downloaded": count(
                "SELECT COUNT(*) FROM photos WHERE uin = ? AND local_path IS NOT NULL AND local_path != ''"
            ),
            "moods": count("SELECT COUNT(*) FROM moods WHERE uin = ?"),
            "mood_media": count("SELECT COUNT(*) FROM mood_media WHERE uin = ? AND local_path != ''"),
        }


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
