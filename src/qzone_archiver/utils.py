"""通用工具：时间解析、文件名清洗、短哈希。"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from urllib.parse import urlparse

_INVALID_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def parse_qzone_time(value: object) -> datetime | None:
    """解析 QQ 空间返回的时间：Unix 秒/毫秒、`YYYY-MM-DD HH:MM:SS` 或日期串。"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        stamp = float(value)
        if stamp <= 0:
            return None
        if stamp > 1e12:  # 毫秒
            stamp /= 1000
        return datetime.fromtimestamp(stamp)

    text = str(value).strip()
    if not text or text == "0":
        return None
    if text.isdigit():
        return parse_qzone_time(int(text))

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def to_iso(value: datetime | None) -> str | None:
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else None


def safe_filename(name: str, fallback: str = "untitled", limit: int = 80) -> str:
    """清洗成跨平台可用的文件名。"""
    cleaned = _INVALID_CHARS.sub("_", (name or "").strip()).strip(". ")
    cleaned = re.sub(r"\s+", " ", cleaned)
    if not cleaned:
        cleaned = fallback
    return cleaned[:limit]


def short_hash(text: str, length: int = 10) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:length]


def guess_ext(url: str, content_type: str = "", default: str = ".jpg") -> str:
    """优先从 Content-Type 猜扩展名，其次看 URL 路径。"""
    mapping = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "image/heic": ".heic",
        "video/mp4": ".mp4",
        "video/quicktime": ".mov",
    }
    for key, ext in mapping.items():
        if key in content_type.lower():
            return ext

    path = urlparse(url).path.lower()
    for ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".heic", ".mp4", ".mov"):
        if path.endswith(ext):
            return ".jpg" if ext == ".jpeg" else ext
    return default


def media_time(dt: datetime) -> tuple[str, str]:
    """返回 (文件名用的 YYYYMMDD_HHMMSS, 时间轴用的 YYYY/MM)。"""
    return dt.strftime("%Y%m%d_%H%M%S"), f"{dt:%Y}/{dt:%m}"
