"""UI-independent archive jobs, with progress, cancellation and a saved result report."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from threading import Event

from .client import QzoneClient, QzoneError
from .collectors import fetch_albums, fetch_moods, fetch_photos
from .exporter import export_bundle
from .media import DownloadCancelled, DownloadError, MediaDownloader, apply_time
from .store import Store
from .utils import media_time, parse_qzone_time, short_hash


class Cancelled(Exception):
    """Stopped between requests; committed records remain available."""


@dataclass
class SyncOptions:
    out: Path
    albums: bool = True
    moods: bool = True
    media: bool = True
    album_ids: set[str] | None = None
    limit: int = 0
    interval: float = 0.8
    merge_accounts: bool = False


@dataclass
class SyncReport:
    state: str = "complete"
    albums: int = 0
    photos: int = 0
    moods: int = 0
    downloaded: int = 0
    skipped: int = 0
    failed: int = 0
    issues: list[dict] = field(default_factory=list)
    index: str = ""


Progress = Callable[[str, dict], None]


def run_sync(
    session: dict, options: SyncOptions, emit: Progress | None = None, cancel: Event | None = None
) -> SyncReport:
    """Re-scan selected sources; retry missing files without duplicating stored records."""
    if not options.albums and not options.moods:
        raise ValueError("请至少选择说说或相册")
    if options.albums and options.album_ids == set():
        raise ValueError("请至少选择一个相册，或勾选全部相册")
    uin = str(session.get("uin", ""))
    if not uin.isdigit() or not session.get("cookie"):
        raise ValueError("请先扫码登录")
    out = options.out.expanduser().resolve()
    report = SyncReport()
    cancel = cancel or Event()

    def check() -> None:
        if cancel.is_set():
            raise Cancelled()

    def notify(message: str) -> None:
        if emit:
            emit(message, asdict(report))

    def issue(kind: str, identity: str, reason: str) -> None:
        report.failed += 1
        report.issues.append({"kind": kind, "id": identity, "reason": reason})
        notify(f"{reason}，已保留记录，可重新导出补下载")

    def photos_for(album_id: str):
        try:
            yield from fetch_photos(client, uin, album_id)
        except QzoneError:
            check()
            issue("album_photos", album_id, "此相册照片读取失败，继续归档其他相册和说说")

    with (
        Store(out / "qzone.db") as store,
        QzoneClient(session["cookie"], uin=uin, interval=options.interval, cancel=cancel) as client,
        MediaDownloader(out, cancel=cancel) as downloader,
    ):
        accounts = store.db.execute("SELECT uin FROM accounts").fetchall()
        if not options.merge_accounts and any(row["uin"] != uin for row in accounts):
            raise ValueError("此文件夹已有其他账号的存档，请另选文件夹")
        store.upsert_account(uin, session.get("nickname", ""))
        try:
            check()
            if options.albums:
                notify("正在读取相册清单…")
                for album in fetch_albums(client, uin):
                    check()
                    if options.album_ids is not None and album["id"] not in options.album_ids:
                        continue
                    if options.limit > 0 and report.albums >= options.limit:
                        break
                    store.upsert_album(uin, album, cover=album.get("cover", ""))
                    report.albums += 1
                    notify(f"正在归档相册：{album['name']}")
                    for photo in photos_for(album["id"]):
                        check()
                        existing = store.photo_exists(uin, album["id"], photo["sloc"])
                        has_file = bool(existing and _has_file(out, existing["local_path"]))
                        if has_file:
                            photo = {
                                **photo,
                                "chosen_url": existing["chosen_url"],
                                "quality": existing["quality"],
                            }
                        store.upsert_photo(uin, album["id"], photo)
                        report.photos += 1
                        if not options.media:
                            continue
                        if photo.get("is_video"):
                            issue("video", photo["sloc"], "视频源解析尚未支持，仅保存元数据")
                            continue
                        if has_file:
                            report.skipped += 1
                            continue
                        moment = parse_qzone_time(photo.get("shoot_at")) or parse_qzone_time(
                            photo.get("upload_at")
                        )
                        stamp = media_time(moment)[0] if moment else "unknown"
                        dest = (
                            out
                            / "media"
                            / uin
                            / "photos"
                            / short_hash(album["id"])
                            / (f"{stamp}_{short_hash(photo['sloc'])}.jpg")
                        )
                        success = False
                        for url, quality in photo_candidates(photo):
                            check()
                            try:
                                final, size = downloader.download(url, dest)
                            except (DownloadError, OSError):
                                continue
                            status = apply_time(
                                final,
                                photo.get("shoot_at"),
                                photo.get("upload_at"),
                                photo.get("time_source", "none"),
                            )
                            photo.update(chosen_url=url, quality=quality)
                            store.upsert_photo(uin, album["id"], photo)
                            store.set_photo_file(
                                uin,
                                album["id"],
                                photo["sloc"],
                                final.relative_to(out).as_posix(),
                                size,
                                status,
                            )
                            report.downloaded += 1
                            success = True
                            break
                        if not success:
                            issue("photo", photo["sloc"], "照片下载失败或没有可用地址")
                        notify(f"已读取 {report.photos} 张照片")
            if options.moods:
                notify("正在读取说说…")
                for mood in fetch_moods(client, uin):
                    check()
                    store.upsert_mood(uin, mood)
                    report.moods += 1
                    tid = mood["tid"]
                    previous = {m["idx"]: m for m in store.mood_media(uin, tid)}
                    for image in mood.get("images", []):
                        check()
                        idx = int(image["index"])
                        store.set_mood_media(uin, tid, idx, image["kind"], image["url"])
                        if not options.media:
                            continue
                        if idx in previous and _has_file(out, previous[idx]["local_path"]):
                            report.skipped += 1
                            continue
                        dest = out / "media" / uin / "moods" / f"{short_hash(tid)}_{idx}.jpg"
                        try:
                            final, size = downloader.download(image["url"], dest)
                            apply_time(final, mood.get("created_at"), None, "upload")
                            store.set_mood_media(
                                uin,
                                tid,
                                idx,
                                image["kind"],
                                image["url"],
                                final.relative_to(out).as_posix(),
                                size,
                            )
                            report.downloaded += 1
                        except (DownloadError, OSError):
                            issue("mood_image", f"{tid}:{idx}", "说说配图下载失败")
                    notify(f"已读取 {report.moods} 条说说")
        except (Cancelled, DownloadCancelled):
            report.state = "cancelled"
        except Exception:  # noqa: BLE001 - job boundary preserves progress and hides credentials
            # Never put raw network exceptions (which can contain signed URLs) into reports.
            if cancel.is_set():
                report.state = "cancelled"
            else:
                report.state = "error"
                issue("source", "", "内容读取中断，请重新登录后重试；已获取的内容已保存")
        finally:
            if report.state == "complete" and report.failed:
                report.state = "partial"
            report.index = str(
                export_bundle(store, uin, out, session.get("nickname", ""), merged=options.merge_accounts)
            )
            (out / "last-run.json").write_text(
                json.dumps(asdict(report), ensure_ascii=False, indent=2), encoding="utf-8"
            )
            if options.merge_accounts:
                (out / f"last-run-{uin}.json").write_text(
                    json.dumps(asdict(report), ensure_ascii=False, indent=2), encoding="utf-8"
                )
    notify(
        {
            "complete": "导出完成",
            "partial": "导出结束，部分内容未下载",
            "cancelled": "已停止，已保存当前进度",
            "error": "导出中断，已保存获取的内容",
        }[report.state]
    )
    return report


def _has_file(out: Path, relative: str | None) -> bool:
    if not relative:
        return False
    path = out / relative
    return path.is_file() and path.stat().st_size > 0


def photo_candidates(photo: dict) -> list[tuple[str, str]]:
    result = []
    seen = set()
    for key, quality in (("url_raw", "raw"), ("url_origin", "origin"), ("url_normal", "normal")):
        url = photo.get(key)
        if not url:
            continue
        for candidate in (url.replace("b&bo=", "o&bo=", 1), url):
            if candidate not in seen:
                result.append((candidate, quality))
                seen.add(candidate)
    return result
