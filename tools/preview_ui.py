"""Reproducible offline previews. Never reads login state or real archives."""

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import QPoint, QSettings, QTimer
from PySide6.QtGui import QColor, QFont, QImage, QPainter
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QScrollArea

from qzone_archiver import desktop, library_ui
from qzone_archiver.exporter import export_bundle
from qzone_archiver.store import Store


def main():
    destination = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/previews/2026-10-26-ui")
    destination.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    app.setStyle("Fusion")
    app.setFont(QFont("PingFang SC", 11))
    app.setStyleSheet(desktop.STYLE)
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        settings = QSettings(str(root / "preview.ini"), QSettings.Format.IniFormat)
        settings.setValue("export_root", "演示存档（本地）")
        with (
            patch.object(desktop, "load_session", return_value=None),
            patch.object(library_ui, "QSettings", return_value=settings),
            patch.object(library_ui.LibraryWidget, "refresh"),
        ):
            window = desktop.Window()
            window.library.roots = []
            window.show()
            app.processEvents()

            def capture(name, widget=window):
                app.processEvents()
                assert widget.grab().save(str(destination / (name + ".png")))

            capture("01-export")
            window.resize(680, 850)
            capture("02-export-narrow")
            scroll = window.pages.widget(0).findChild(QScrollArea)
            scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
            capture("13-task-empty")
            window.on_progress(
                "演示：正在保存图片…",
                {"albums": 1, "photos": 9, "moods": 1, "downloaded": 6, "skipped": 0, "failed": 0},
            )
            window.progress.setRange(0, 9)
            window.progress.setValue(6)
            capture("14-task-progress")
            window.resize(1180, 940)
            library = window.library
            photos = []
            for i in range(9):
                image = QImage(480, 360, QImage.Format.Format_RGB32)
                image.fill(QColor(["#b9d7ea", "#d3e4d4", "#eddfca"][i % 3]))
                painter = QPainter(image)
                painter.setPen(QColor("#42657e"))
                painter.setFont(QFont("PingFang SC", 24))
                painter.drawText(36, 190, f"本地演示素材  {i + 1:02}")
                painter.end()
                image.save(str(root / f"demo-{i}.png"))
                photos.append({"path": f"demo-{i}.png"})
            common = {"uin": "demo-a", "owner": "演示空间 A", "root": root}
            entries = [
                {
                    **common,
                    "kind": "mood",
                    "tid": "sample",
                    "time": "2026-10-26 14:30",
                    "content": "把平凡的一天，放进时光里。[em]e100[/em]\n这些图片与文字均为合成演示内容。",
                    "media": photos,
                    "like_count": 12,
                    "comment_count": 3,
                },
                {
                    **common,
                    "kind": "album",
                    "id": "demo-album",
                    "name": "演示相册 · 日常拾光",
                    "time": "2025-08-20",
                    "photos": photos,
                },
            ]
            entries += [
                {
                    **common,
                    **p,
                    "kind": "photo",
                    "sloc": f"photo-{i}",
                    "album_id": "demo-album",
                    "name": f"演示照片 {i + 1:02}",
                    "time": "2025-08-20",
                }
                for i, p in enumerate(photos)
            ]
            entries += [
                {
                    **common,
                    "uin": "demo-b",
                    "owner": "演示空间 B",
                    "kind": "mood",
                    "tid": str(i),
                    "time": "2024-06-01",
                    "content": f"合成回忆 {i + 1} · 仅供界面演示",
                    "media": [],
                }
                for i in range(120)
            ]
            entries.extend(
                [
                    {
                        **common,
                        "kind": "album",
                        "id": f"demo-extra-{i}",
                        "name": ["演示相册 · 海风", "演示相册 · 四季"][i],
                        "time": "2025-07-01",
                        "photos": [photos[i + 1]],
                    }
                    for i in range(2)
                ]
            )
            library.on_loaded(entries, [])
            window.resize(1500, 1120)
            window.navigate("overview")
            capture("19-overview-local-data")
            window.resize(1180, 940)
            window.pages.setCurrentIndex(1)
            capture("03-feed")
            window.resize(1180, 1360)
            capture("15-feed-full")
            window.resize(1180, 940)
            library.kind.setCurrentIndex(library.kind.findData("album"))
            capture("04-albums")
            library.enter_album(library.feed.item(0))
            capture("05-album-photos")
            library.show_all()
            library.account.setCurrentIndex(library.account.findData("demo-b"))
            library.year.setCurrentIndex(library.year.findData("2024"))
            library.search.setText("合成回忆 12")
            capture("06-filters")
            library.search.setText("没有此演示内容")
            capture("07-empty")
            library.show_all()

            def dialog_capture(name, action):
                def grab():
                    dialog = app.activeModalWidget()
                    if isinstance(dialog, QDialog):
                        capture(name, dialog)
                        dialog.accept()

                QTimer.singleShot(120, grab)
                action()

            dialog_capture("08-content-detail", lambda: library.open_feed_entry(library.feed.item(0)))
            issues = [
                {**common, "id": "sample:0", "severity": "failed", "reason": "演示：图片读取超时，可重试。"},
                {
                    **common,
                    "id": "video-demo",
                    "severity": "unsupported",
                    "reason": "演示：视频仅保留元数据。",
                },
            ]
            with patch.object(library_ui, "read_run_issues", return_value=issues):
                dialog_capture("09-result-detail", library.show_run_issues)
            dialog_capture("10-photo-viewer", lambda: library.open_feed_image(entries[0], 0))
            library.feed.scrollToBottom()
            capture("11-feed-end")
            window.resize(680, 850)
            library.feed.scrollToTop()
            capture("12-library-narrow")
            library.feed.setFocus()
            QTest.mouseMove(library.feed.viewport(), QPoint(100, 40))
            capture("16-hover-focus")
            library.year.showPopup()
            capture("17-year-dropdown", library.year.view().window())
            library.year.hidePopup()
            window.close()
            chrome = shutil.which("google-chrome") or shutil.which("chromium")
            mac_chrome = Path("/Applications") / "Google Chrome.app/Contents/MacOS/Google Chrome"
            if not chrome and mac_chrome.is_file():
                chrome = str(mac_chrome)
            if chrome:
                with Store(root / "qzone.db") as store:
                    store.upsert_account("demo-a", "演示空间 A")
                    store.upsert_mood(
                        "demo-a",
                        {
                            "tid": "sample",
                            "content": "合成演示内容 · 把平凡的一天放进时光里。",
                            "created_at": "2026-10-26 14:30:00",
                        },
                    )
                    index = export_bundle(store, "demo-a", root, "演示空间 A")
                subprocess.run(
                    [
                        chrome,
                        "--headless",
                        "--disable-gpu",
                        "--hide-scrollbars",
                        "--disable-background-networking",
                        f"--user-data-dir={root / 'browser'}",
                        "--window-size=1280,1100",
                        "--virtual-time-budget=1000",
                        "--force-prefers-reduced-motion",
                        "--no-pdf-header-footer",
                        f"--screenshot={destination.resolve() / '18-offline-html.png'}",
                        index.as_uri(),
                    ],
                    check=True,
                    capture_output=True,
                )
                assert (destination / "18-offline-html.png").is_file()


if __name__ == "__main__":
    main()
