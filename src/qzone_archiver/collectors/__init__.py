"""采集器集合。"""

from .albums import fetch_albums, fetch_photos, normalize_album, normalize_photo
from .moods import fetch_moods, normalize_mood

__all__ = [
    "fetch_albums",
    "fetch_moods",
    "fetch_photos",
    "normalize_album",
    "normalize_mood",
    "normalize_photo",
]
