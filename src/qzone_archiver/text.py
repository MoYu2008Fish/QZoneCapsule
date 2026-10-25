"""Conservative recovery of photo CGI's UTF-8-as-GBK text; raw responses stay intact."""

from __future__ import annotations

import re

_MARKERS = frozenset("杩锛鍐鎴鎯濂棰鍚鏈閮闂鏄鐨鈥缁绁炰簡鈧鐪鍙鏉娌浣涓枃")


def _damage(text: str) -> int:
    return sum(c in _MARKERS for c in text) + 2 * sum("\ue000" <= c <= "\uf8ff" for c in text)


def photo_text_candidate(text: str) -> str | None:
    if not text or _damage(text) < 2:
        return None
    try:
        return text.encode("gb18030").decode("utf-8", errors="replace").replace("\\n", "\n")
    except UnicodeError:
        return None


def recover_photo_text(text: str) -> tuple[str, str]:
    """Return recovered text and provenance; never apply a lossy change without a note."""
    recovered = photo_text_candidate(text)
    if recovered is None:
        return text, ""
    missing = recovered.count("\ufffd")
    chinese = len(re.findall(r"[\u4e00-\u9fff]", recovered))
    if chinese < 2 or _damage(recovered) >= _damage(text) or missing > max(1, len(recovered) // 8):
        return text, ""
    return recovered, "部分原始字符已损坏，� 表示无法还原的字符" if missing else "已修复接口文字编码"
