"""Read existing archives locally, without requiring a QQ login or modifying databases."""

from __future__ import annotations

from pathlib import Path

from .exporter import build_data
from .store import Store


def archive_databases(roots: list[Path]) -> list[Path]:
    found: set[Path] = set()
    for root in roots:
        root = root.expanduser().resolve()
        if root.is_file():
            root = root.parent
        if not root.is_dir():
            continue
        candidates = [root / "qzone.db", *root.glob("*/qzone.db")]
        found.update(path.resolve() for path in candidates if path.is_file())
    return sorted(found)


def local_media(root: Path, relative: str) -> Path | None:
    """Only allow files belonging to this archive, including when symlinks exist."""
    if not relative or Path(relative).is_absolute():
        return None
    root = root.resolve()
    path = (root / relative).resolve()
    return path if path.is_relative_to(root) and path.is_file() else None


def read_library(roots: list[Path]) -> tuple[list[dict], list[str]]:
    entries: dict[tuple, dict] = {}
    errors = []
    for database in archive_databases(roots):
        try:
            with Store(database, readonly=True) as store:
                for account in store.db.execute("SELECT uin, nickname FROM accounts ORDER BY uin"):
                    uin = account["uin"]
                    owner = f"{account['nickname']} · QQ {uin}" if account["nickname"] else f"QQ {uin}"
                    data = build_data(store, uin)
                    for kind, items in (
                        ("album", data["albums"]),
                        ("photo", data["photos"]),
                        ("mood", data["moods"]),
                    ):
                        for item in items:
                            identity = (
                                (item["album_id"], item["sloc"])
                                if kind == "photo"
                                else (item["id"],)
                                if kind == "album"
                                else (item["tid"],)
                            )
                            key = (uin, kind, *identity)
                            entry = {
                                **item,
                                "kind": kind,
                                "uin": uin,
                                "owner": owner,
                                "root": database.parent,
                                "key": key,
                            }
                            # Repeated exports of one account are one logical record;
                            # prefer a copy with a local image over a metadata-only copy.
                            previous = entries.get(key)
                            if previous:

                                def media_count(record):
                                    media = record.get("media", []) if record["kind"] == "mood" else [record]
                                    return sum(
                                        bool(local_media(record["root"], m.get("path", ""))) for m in media
                                    )

                                if media_count(previous) > media_count(entry):
                                    continue
                            entries[key] = entry
        except Exception:  # noqa: BLE001 - one damaged archive must not hide the others
            errors.append("有一份存档无法读取，请确认文件完整且来自扣扣时光。")
    return list(entries.values()), errors
