"""Native desktop client. Network work never runs on the GUI thread."""

from __future__ import annotations

import sys
from pathlib import Path
from threading import Event

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QLabel,
    QMainWindow,
    QPushButton,
    QTreeWidgetItem,
    QVBoxLayout,
)

from . import __version__
from .auth import load_session, login_with_qrcode, save_session, session_path
from .client import QzoneClient
from .collectors import fetch_albums
from .sync import SyncOptions, run_sync
from .theme import STYLE


class Job(QThread):
    progress = Signal(str, object)
    qr = Signal(bytes)
    result = Signal(object)
    error = Signal(str)

    def __init__(self, kind: str, session: dict | None = None, options: SyncOptions | None = None):
        super().__init__()
        self.kind, self.session, self.options = kind, session, options
        self.cancel = Event()

    def run(self) -> None:
        try:
            if self.kind == "login":
                result = login_with_qrcode(
                    on_qrcode=self.qr.emit,
                    cancel=self.cancel,
                    on_status=lambda text: self.progress.emit(text, {}),
                )
                if self.cancel.is_set():
                    return
                save_session(result["cookie"], result.get("nickname", ""))
            elif self.kind == "albums":
                result = []
                with QzoneClient(
                    self.session["cookie"], uin=self.session["uin"], cancel=self.cancel
                ) as client:
                    for album in fetch_albums(client, self.session["uin"]):
                        if self.cancel.is_set():
                            return
                        result.append(album)
                        self.progress.emit(f"已读取 {len(result)} 个相册…", {})
            else:
                result = run_sync(self.session, self.options, self.progress.emit, self.cancel)
            self.result.emit(result)
        except Exception:  # noqa: BLE001 - job boundary preserves progress and hides credentials
            # Do not expose cookies, signed media URLs or response bodies in the UI.
            self.error.emit(
                "已取消操作"
                if self.cancel.is_set()
                else {
                    "login": "扫码登录未完成，二维码可能过期或网络不可用。请重新扫码。",
                    "albums": "读取相册失败。请检查网络或重新扫码登录。",
                    "sync": "无法导出。请检查目录写入权限、剩余空间和登录状态。",
                }[self.kind]
            )


def label(text: str, name: str = "", wrap: bool = False) -> QLabel:
    item = QLabel(text)
    item.setTextFormat(Qt.TextFormat.PlainText)
    item.setWordWrap(wrap)
    if name:
        item.setObjectName(name)
    return item


def button(text: str, handler, primary: bool = False) -> QPushButton:
    item = QPushButton(text)
    if primary:
        item.setObjectName("primary")
    item.clicked.connect(handler)
    return item


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"扣扣时光 · QZoneCapsule {__version__}")
        self.resize(1544, 900)
        self.setMinimumSize(680, 650)
        self.setWindowIcon(QIcon(str(Path(__file__).parent / "assets" / "app-icon.png")))
        self.setStyleSheet(STYLE)
        self.session = load_session()
        self.job: Job | None = None
        self.qr_dialog: QDialog | None = None
        self.close_requested = False
        self.index: Path | None = None
        self.album_owner = ""
        from .dashboard_ui import build_dashboard

        self.version = __version__
        build_dashboard(self)
        self.update_account()
        self.update_controls()
        remembered_archives = bool(self.library.roots)
        self.library.add_root(Path(self.path.text()), refresh=False)
        if remembered_archives:
            self.library.refresh()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "sidebar"):
            self.sidebar.setVisible(self.width() >= 1080)
            self.compact_nav.setVisible(self.width() < 1080)
            self.tagline.setVisible(self.width() >= 800)

    def select_navigation(self, destination):
        self.compact_nav.setCurrentIndex(self.compact_nav.findData(destination))
        for item in self.nav_buttons:
            previous = item.blockSignals(True)
            item.setChecked(item.property("destination") == destination)
            item.blockSignals(previous)

    def navigate(self, destination):
        self.log.setVisible(destination == "logs")
        self.select_navigation(destination)
        if destination == "library":
            self.open_archive()
            return
        self.pages.setCurrentIndex(0)
        if destination == "overview":
            self.export_scroll.verticalScrollBar().setValue(0)
        else:
            self.export_scroll.ensureWidgetVisible(self.anchors[destination], 0, 16)

    def update_dashboard(self):
        from collections import Counter

        counts = Counter(entry["kind"] for entry in self.library.entries)
        accounts = len({entry["uin"] for entry in self.library.entries})
        self.local_accounts.setText(f"{accounts} 个")
        self.local_records.setText(f"{len(self.library.entries):,} 条")
        self.local_moods.setText(f"{counts['mood']:,} 条")
        self.local_photos.setText(f"{counts['photo']:,} 张")
        for key, caption in self.selection_counts.items():
            caption.setText(f"{counts[key]:,} {'条' if key == 'mood' else '个'}已存")
        self.content_chart.set_entries(self.library.entries)
        self.timeline_chart.set_entries(
            [entry for entry in self.library.entries if entry["kind"] in {"mood", "photo"}]
        )

    def update_account(self):
        self.account.setText(
            (self.session.get("nickname") or "我的 QQ 空间") if self.session else "尚未连接 QQ 空间"
        )
        uin = self.session.get("uin") if self.session else ""
        self.account_id.setText(f"QQ空间ID {uin}" if uin else "QQ空间ID —")
        self.copy_button.setVisible(bool(uin))
        self.login_button.setText("重新扫码" if self.session else "扫码登录")
        if self.job is None:
            self.status.setText(
                "准备就绪 · 选择内容后即可开始" if self.session else "准备就绪 · 登录后即可开始"
            )

    def copy_uin(self):
        if not self.session:
            return
        QApplication.clipboard().setText(str(self.session["uin"]))
        self.copy_button.setText("已复制")
        QTimer.singleShot(1600, lambda: self.copy_button.setText("复制"))

    def update_controls(self, *_):
        busy = self.job is not None
        logged = bool(self.session and self.session.get("cookie"))
        for item in (
            self.login_button,
            self.path,
            self.browse_button,
            self.moods,
            self.albums,
            self.media,
            self.export_mode,
        ):
            item.setEnabled(not busy)
        self.forget_button.setEnabled(logged and not busy)
        self.load_button.setEnabled(logged and not busy and self.albums.isChecked())
        self.all_albums.setEnabled(not busy and self.albums.isChecked())
        self.tree.setEnabled(not busy and self.albums.isChecked() and not self.all_albums.isChecked())
        self.start_button.setEnabled(logged and not busy)
        self.stop_button.setEnabled(busy)

    def browse(self):
        selected = QFileDialog.getExistingDirectory(self, "选择备份文件夹", self.path.text())
        if selected:
            self.path.setText(selected)
            self.index = None
            self.open_button.setEnabled(True)

    def launch(self, job: Job):
        self.job = job
        job.progress.connect(self.on_progress)
        job.qr.connect(self.show_qr)
        job.result.connect(self.on_result)
        job.error.connect(self.on_error)
        job.finished.connect(self.on_finished)
        self.progress.setRange(0, 0)
        self.update_controls()
        job.start()

    def login(self):
        self.status.setText("正在获取 QQ 登录二维码…")
        self.launch(Job("login"))

    def forget(self):
        try:
            session_path().unlink(missing_ok=True)
        except OSError:
            self.on_error("无法删除本地登录凭据，请检查文件权限。")
            return
        self.session = None
        self.tree.clear()
        self.tree.hide()
        self.album_owner = ""
        self.all_albums.setChecked(True)
        self.status.setText("已退出登录，本地存档仍可打开")
        self.update_account()
        self.update_controls()

    def show_qr(self, data):
        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            self.on_error("未收到有效二维码，请重新扫码。")
            self.stop()
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("用手机 QQ 扫码")
        box = QVBoxLayout(dialog)
        box.setContentsMargins(30, 24, 30, 24)
        box.addWidget(label("用手机 QQ 扫码，并确认登录", "cardtitle"))
        picture = QLabel()
        picture.setPixmap(
            pixmap.scaled(
                260, 260, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation
            )
        )
        picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(picture)
        self.qr_status = label("二维码有效期约 3 分钟，过期后请重新扫码。", wrap=True)
        box.addWidget(self.qr_status)
        box.addWidget(button("取消登录", dialog.reject))
        dialog.rejected.connect(self.stop)
        self.qr_dialog = dialog
        dialog.show()

    def read_albums(self):
        self.status.setText("正在读取相册…")
        self.launch(Job("albums", dict(self.session)))

    def start_sync(self):
        if not self.moods.isChecked() and not self.albums.isChecked():
            self.on_error("请至少勾选说说或相册。")
            return
        ids = None
        if self.albums.isChecked() and not self.all_albums.isChecked():
            ids = {
                self.tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole)
                for i in range(self.tree.topLevelItemCount())
                if self.tree.topLevelItem(i).checkState(0) == Qt.CheckState.Checked
            }
            if not ids or self.album_owner != self.session["uin"]:
                self.on_error("请读取相册并勾选，或选择全部相册。")
                return
        if not self.path.text().strip():
            self.on_error("请先选择保存文件夹。")
            return
        root = Path(self.path.text()).expanduser()
        merged = self.export_mode.currentData()
        out = root / ("合并存档" if merged else self.session["uin"])
        self.library.settings.setValue("export_root", str(root))
        self.library.add_root(root, refresh=False)
        options = SyncOptions(
            out,
            self.albums.isChecked(),
            self.moods.isChecked(),
            self.media.isChecked(),
            ids,
            merge_accounts=merged,
        )
        self.task_row.setText(0, "QQ空间备份")
        self.task_row.setText(
            1,
            " + ".join(
                name
                for name, selected in [("说说", self.moods.isChecked()), ("相册", self.albums.isChecked())]
                if selected
            ),
        )
        self.task_row.setText(2, "进行中")
        self.task_row.setForeground(2, QBrush(QColor("#3a6bff")))
        self.task_row.setText(3, "正在读取")
        self.log.clear()
        self.exported_value.setText("0")
        self.index = None
        self.open_button.setEnabled(True)
        self.launch(Job("sync", dict(self.session), options))

    def stop(self):
        if self.job:
            self.job.cancel.set()
            self.status.setText("正在停止，等待当前请求结束并保存进度…")
            self.stop_button.setEnabled(False)

    def on_progress(self, text, data):
        self.status.setText(text)
        if self.job and self.job.kind == "sync":
            self.task_row.setText(3, text)
        self.log.append(text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        if self.qr_dialog and self.qr_dialog.isVisible():
            self.qr_status.setText(text)
        if data:
            self.exported_value.setText(f"{data['downloaded']:,}")
            self.counts.setText(
                f"相册 {data['albums']}   /   照片 {data['photos']}   /   说说 {data['moods']}"
                f"   /   下载 {data['downloaded']}   /   跳过 {data['skipped']}   /   失败 {data['failed']}"
                f"   /   暂不支持 {data.get('unsupported', 0)}"
            )

    def on_result(self, result):
        if self.job.kind == "login":
            self.session = result
            if self.qr_dialog:
                self.qr_dialog.accept()
            self.tree.clear()
            self.tree.hide()
            self.album_owner = ""
            self.all_albums.setChecked(True)
            self.update_account()
            self.status.setText("登录成功，选择内容后即可导出")
        elif self.job.kind == "albums":
            self.tree.clear()
            for album in result:
                row = QTreeWidgetItem(
                    [album["name"], str(album["total"]), (album.get("lastuploadtime") or "")[:10]]
                )
                row.setData(0, Qt.ItemDataRole.UserRole, album["id"])
                row.setCheckState(0, Qt.CheckState.Checked)
                self.tree.addTopLevelItem(row)
            self.album_owner = self.session["uin"]
            self.tree.show()
            self.all_albums.setChecked(False)
            self.status.setText(f"已读取 {len(result)} 个相册，可取消勾选不需要的相册")
        else:
            labels = {
                "complete": "已完成",
                "partial": "部分完成",
                "cancelled": "已停止",
                "error": "读取中断",
            }
            self.task_row.setText(2, labels[result.state])
            self.task_row.setForeground(
                2,
                QBrush(
                    QColor(
                        {
                            "complete": "#1f9d6b",
                            "partial": "#d98a1a",
                            "cancelled": "#8a99ba",
                            "error": "#e0576f",
                        }[result.state]
                    )
                ),
            )
            self.task_row.setText(3, f"下载 {result.downloaded} / 失败 {result.failed}")
            self.index = Path(result.index)
            self.library.add_root(self.index.parent)
            self.open_button.setEnabled(self.index.is_file())
            self.status.setText(
                {
                    "complete": "导出完成，可以打开本地存档",
                    "partial": (
                        f"导出结束 · 下载/读取失败 {result.failed} 项 · "
                        f"视频暂不支持 {result.unsupported} 项；可在时光馆查看条目明细"
                    ),
                    "cancelled": "已停止，已获取的内容已保存",
                    "error": "读取中断，请检查网络或重新扫码后重试",
                }[result.state]
            )
            self.log.append(f"结果报告：{self.index.parent / 'last-run.json'}")

    def on_error(self, text):
        if self.job and self.job.kind == "sync":
            self.task_row.setText(2, "已中断")
            self.task_row.setForeground(2, QBrush(QColor("#e0576f")))
            self.task_row.setText(3, text)
        self.status.setText(text)
        self.log.append(text)
        if self.qr_dialog:
            self.qr_dialog.accept()

    def on_finished(self):
        job = self.job
        self.job = None
        if job.kind == "login" and self.qr_dialog:
            self.qr_dialog.accept()
            self.qr_dialog.deleteLater()
            self.qr_dialog = None
        if job.cancel.is_set() and job.kind != "sync":
            self.status.setText("已取消操作")
        self.progress.setRange(0, 1)
        self.progress.setValue(1)
        self.update_controls()
        job.deleteLater()
        if self.close_requested:
            self.close()

    def open_archive(self):
        self.library.add_root(Path(self.path.text()), refresh=False)
        if self.index and self.index.is_file():
            self.library.add_root(self.index.parent, refresh=False)
        if self.pages.currentIndex() == 1:
            self.library.refresh()
        else:
            self.pages.setCurrentIndex(1)

    def on_page_changed(self, index):
        if index == 1:
            self.select_navigation("library")
        else:
            self.update_dashboard()
            if self.compact_nav.currentData() == "library":
                self.select_navigation("overview")
        if index == 1:
            self.library.refresh()

    def closeEvent(self, event):
        if self.job:
            self.close_requested = True
            self.stop()
            event.ignore()
        else:
            self.library.wait_for_load()
            event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("QZoneCapsule")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("QZoneCapsule")
    app.setFont(QFont("PingFang SC" if sys.platform == "darwin" else "Microsoft YaHei", 11))
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = Window()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
