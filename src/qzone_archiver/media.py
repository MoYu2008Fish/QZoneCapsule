"""媒体下载与时间回填：文件 mtime + EXIF。"""

from __future__ import annotations

import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from threading import Event

import httpx

from .utils import guess_ext

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".tif", ".tiff"}
EXIFTOOL = shutil.which("exiftool")


class DownloadError(RuntimeError):
    def __init__(self, message: str, *, safe_reason: str = "媒体下载失败"):
        super().__init__(message)
        self.safe_reason = safe_reason


class DownloadCancelled(RuntimeError):
    pass


class MediaDownloader:
    def __init__(self, root: Path | str, timeout: float = 20.0, cancel: Event | None = None) -> None:
        self.root = Path(root)
        self.cancel = cancel or Event()
        self.root.mkdir(parents=True, exist_ok=True)
        self._http = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"user-agent": "Mozilla/5.0", "referer": "https://user.qzone.qq.com/"},
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> MediaDownloader:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def download(self, url: str, dest: Path, retries: int = 2) -> tuple[Path, int]:
        """下载到 dest，返回 (最终文件路径, 字节数)。

        已存在且非空的文件直接跳过，天然支持断点续传。
        """
        if dest.exists() and dest.stat().st_size > 0:
            return dest, dest.stat().st_size

        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_suffix(dest.suffix + ".part")

        last_error: Exception | None = None
        for attempt in range(retries + 1):
            if self.cancel.is_set():
                raise DownloadCancelled()
            try:
                with self._http.stream("GET", url) as resp:
                    resp.raise_for_status()
                    content_type = resp.headers.get("content-type", "")
                    if any(kind in content_type.lower() for kind in ("text/", "json", "xml")):
                        raise DownloadError("非媒体响应", safe_reason="媒体地址返回了网页或错误信息")
                    ext = guess_ext(url, content_type, dest.suffix or ".jpg")
                    final = dest.with_suffix(ext)
                    if final.exists() and final.stat().st_size > 0:
                        return final, final.stat().st_size

                    total = 0
                    with part.open("wb") as fh:
                        for chunk in resp.iter_bytes(65536):
                            if self.cancel.is_set():
                                raise DownloadCancelled()
                            fh.write(chunk)
                            total += len(chunk)

                    expected = resp.headers.get("content-length")
                    if not total:
                        raise DownloadError("空媒体", safe_reason="媒体文件为空")
                    if expected and not resp.headers.get("content-encoding") and int(expected) != total:
                        raise DownloadError("文件长度不一致", safe_reason="媒体传输不完整")

                    os.replace(part, final)
                    return final, total
            except Exception as exc:
                last_error = exc
                part.unlink(missing_ok=True)
                if isinstance(exc, DownloadCancelled):
                    raise

        if isinstance(last_error, httpx.HTTPStatusError):
            reason = f"媒体服务器返回 HTTP {last_error.response.status_code}"
        elif isinstance(last_error, httpx.TimeoutException):
            reason = "媒体请求超时"
        elif isinstance(last_error, httpx.HTTPError):
            reason = "媒体网络连接失败"
        elif isinstance(last_error, OSError):
            reason = "媒体文件无法写入，请检查目录权限与剩余空间"
        elif isinstance(last_error, DownloadError):
            reason = last_error.safe_reason
        else:
            reason = "媒体下载失败"
        raise DownloadError(reason, safe_reason=reason) from None


def apply_time(
    path: Path,
    shoot_at: str | None,
    upload_at: str | None,
    time_source: str,
) -> str:
    """把时间写进文件系统与 EXIF，返回 exif 状态。

    返回状态：
    - preserved：原图自带拍摄时间，未覆盖
    - written：用接口时间写入 EXIF
    - mtime-only：没有 exiftool，只改了文件时间
    - failed：写入失败
    - skipped：非图片（视频只改 mtime）
    """
    chosen = _parse(shoot_at) or _parse(upload_at)
    if not chosen:
        return "skipped"

    timestamp = chosen.timestamp()
    try:
        os.utime(path, (timestamp, timestamp))
    except OSError:
        pass

    if path.suffix.lower() not in IMAGE_EXTS:
        return "skipped"

    if not EXIFTOOL:
        return "mtime-only"

    stamp = chosen.strftime("%Y:%m:%d %H:%M:%S")
    existing = _read_exif_datetime(path)
    if existing and not existing.startswith("0000"):
        return "preserved"

    args = [
        EXIFTOOL,
        "-q",
        "-overwrite_original",
        f"-DateTimeOriginal={stamp}",
        f"-CreateDate={stamp}",
        f"-ModifyDate={stamp}",
        f"-XMP-dc:Relation+=QZoneCapsule:time_source={time_source}",
    ]
    if upload_at:
        args.append(f"-XMP-dc:Relation+=QZoneCapsule:upload_time={upload_at}")
    args.append(str(path))

    try:
        subprocess.run(args, check=True, capture_output=True, timeout=30)
        return "written"
    except (subprocess.SubprocessError, OSError):
        return "failed"
    finally:
        # EXIF editors can change mtime while rewriting the file.
        try:
            os.utime(path, (timestamp, timestamp))
        except OSError:
            pass


def _read_exif_datetime(path: Path) -> str:
    if not EXIFTOOL:
        return ""
    try:
        result = subprocess.run(
            [EXIFTOOL, "-q", "-s3", "-DateTimeOriginal", str(path)],
            capture_output=True,
            check=False,
            text=True,
            timeout=20,
        )
        return result.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return ""


def _parse(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None
