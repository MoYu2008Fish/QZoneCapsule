"""Native desktop client. Network work never runs on the GUI thread."""

from __future__ import annotations

import sys
from pathlib import Path
from threading import Event

from PySide6.QtCore import Qt, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QFont, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .auth import load_session, login_with_qrcode, save_session, session_path
from .client import QzoneClient
from .collectors import fetch_albums
from .sync import SyncOptions, run_sync

STYLE = """
QWidget { color: #253a3b; font-size: 14px; }
QMainWindow, QDialog { background: #f4f6f3; }
QFrame#sidebar { background: #143e3b; border-radius: 0; }
QFrame#sidebar QLabel { color: #c1d7cc; background: transparent; }
QFrame#sidebar QLabel#brand { color: white; font-size: 27px; font-weight: 700; }
QLabel#eyebrow { color: #38766a; font-size: 12px; font-weight: 700; }
QLabel#title { font-size: 28px; font-weight: 700; color: #153e39; }
QLabel#muted { color: #6d807b; }
QFrame#card { background: white; border: 1px solid #dfe7df; border-radius: 14px; }
QLabel#cardtitle { font-size: 16px; font-weight: 650; }
QPushButton { background: #edf3ed; border: 1px solid #d8e3d8; border-radius: 8px;
              padding: 10px 17px; color: #27584c; }
QPushButton:hover { background: #dfece2; }
QPushButton:disabled { color: #97a49c; background: #f0f2ee; border-color: #e5e9e2; }
QPushButton#primary { background: #246b56; color: white; border: none; font-weight: 650; }
QPushButton#primary:hover { background: #195542; }
QPushButton#primary:disabled { background: #a8c0b2; }
QLineEdit { background: #f8faf7; border: 1px solid #dce5da; border-radius: 7px; padding: 10px; }
QCheckBox { spacing: 9px; padding: 5px 0; }
QTreeWidget { border: 1px solid #e3e9df; border-radius: 8px; background: #fafcf8; }
QTreeWidget::item { padding: 7px 3px; }
QHeaderView::section { background: #edf3e9; color: #59705e; border: none; padding: 7px; }
QTextEdit { background: #f7f9f4; border: 1px solid #e0e8da; border-radius: 8px; padding: 8px; }
QProgressBar { border: none; background: #e6eee0; border-radius: 4px; height: 8px; }
QProgressBar::chunk { background: #4c8b64; border-radius: 4px; }
"""


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
                with QzoneClient(self.session["cookie"], uin=self.session["uin"]) as client:
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
        self.setWindowTitle("扣扣时光 · QZoneCapsule")
        self.resize(1100, 850)
        self.setMinimumSize(850, 650)
        self.session = load_session()
        self.job: Job | None = None
        self.qr_dialog: QDialog | None = None
        self.close_requested = False
        self.index: Path | None = None
        self.album_owner = ""
        root = QWidget()
        self.setCentralWidget(root)
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(26, 36, 24, 28)
        side.addWidget(label("扣扣时光", "brand"))
        side.addWidget(label("QZoneCapsule"))
        side.addSpacing(50)
        side.addWidget(label("01  扫码连接你的空间"))
        side.addSpacing(20)
        side.addWidget(label("02  选择想保存的内容"))
        side.addSpacing(20)
        side.addWidget(label("03  把回忆带回本地"))
        side.addStretch()
        side.addWidget(
            label("说说 · 相册 · 时间\n\n数据保存在你的电脑上。\n每一份回忆，都值得留下。", wrap=True)
        )
        side.addSpacing(20)
        side.addWidget(label("桌面预览版  0.2.0"))
        layout.addWidget(sidebar)
        right = QWidget()
        right_box = QVBoxLayout(right)
        right_box.setContentsMargins(0, 0, 0, 0)
        right_box.setSpacing(0)
        layout.addWidget(right, 1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        scroll.setWidget(content)
        body = QVBoxLayout(content)
        body.setContentsMargins(34, 28, 34, 28)
        body.setSpacing(14)
        body.addWidget(label("YOUR MEMORIES, AT HOME", "eyebrow"))
        body.addWidget(label("把空间里的时光，留在身边。", "title", True))
        body.addWidget(label("说说和相册一起保存，导出后随时离线翻看。", "muted", True))
        account = self.card(body, "01 / 连接空间")
        row = QHBoxLayout()
        self.account = label("")
        row.addWidget(self.account, 1)
        self.login_button = button("扫码登录", self.login, True)
        self.forget_button = button("退出登录", self.forget)
        row.addWidget(self.login_button)
        row.addWidget(self.forget_button)
        account.addLayout(row)
        account.addWidget(label("用手机 QQ 扫码确认，登录凭据仅保存在本机。", "muted", True))
        choose = self.card(body, "02 / 选择保存内容")
        row = QHBoxLayout()
        self.moods = QCheckBox("说说正文与配图")
        self.albums = QCheckBox("相册与照片")
        self.media = QCheckBox("下载图片到本地")
        for item in (self.moods, self.albums, self.media):
            item.setChecked(True)
            row.addWidget(item)
        choose.addLayout(row)
        row = QHBoxLayout()
        self.all_albums = QCheckBox("全部相册")
        self.all_albums.setChecked(True)
        row.addWidget(self.all_albums, 1)
        self.load_button = button("读取相册并选择", self.read_albums)
        row.addWidget(self.load_button)
        choose.addLayout(row)
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["相册", "条目数", "最近上传"])
        self.tree.setRootIsDecorated(False)
        self.tree.setMinimumHeight(130)
        self.tree.setColumnWidth(0, 280)
        self.tree.setVisible(False)
        choose.addWidget(self.tree)
        choose.addWidget(label("照片优先尝试原图；视频暂只保存元数据，结果中会单独提示。", "muted", True))
        self.albums.toggled.connect(self.update_controls)
        self.all_albums.toggled.connect(self.update_controls)
        target = self.card(body, "03 / 保存位置")
        row = QHBoxLayout()
        self.path = QLineEdit(str(Path.home() / "Pictures" / "扣扣时光归档"))
        self.path.setAccessibleName("备份根文件夹")
        row.addWidget(self.path, 1)
        self.browse_button = button("选择文件夹", self.browse)
        row.addWidget(self.browse_button)
        target.addLayout(row)
        target.addWidget(label("会在此处按 QQ 号建立文件夹。重复导出会补下缺失文件。", "muted", True))
        tasks = self.card(body, "导出任务")
        self.status = label("准备就绪 · 登录后即可开始", wrap=True)
        tasks.addWidget(self.status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        tasks.addWidget(self.progress)
        self.counts = label("相册 0   /   照片 0   /   说说 0   /   下载 0   /   失败 0", "muted", True)
        tasks.addWidget(self.counts)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(100)
        self.log.setPlaceholderText("进度与结果将在这里显示。")
        tasks.addWidget(self.log)
        row = QHBoxLayout()
        self.open_button = button("打开本地存档", self.open_archive)
        self.open_button.setEnabled(True)
        self.stop_button = button("停止", self.stop)
        self.start_button = button("开始导出", self.start_sync, True)
        row.addWidget(self.open_button)
        row.addStretch()
        row.addWidget(self.stop_button)
        row.addWidget(self.start_button)
        row.setContentsMargins(34, 12, 34, 16)
        right_box.addWidget(scroll, 1)
        right_box.addLayout(row)
        body.addWidget(
            label("非腾讯官方工具 · 网页接口可能变化，首次建议选择一个小相册验证。", "muted", True)
        )
        body.addStretch()
        self.update_account()
        self.update_controls()

    @staticmethod
    def card(body, title):
        frame = QFrame()
        frame.setObjectName("card")
        box = QVBoxLayout(frame)
        box.setContentsMargins(20, 16, 20, 16)
        box.setSpacing(10)
        box.addWidget(label(title, "cardtitle"))
        body.addWidget(frame)
        return box

    def update_account(self):
        self.account.setText(f"QQ {self.session['uin']} · 已保存登录" if self.session else "尚未登录 QQ 空间")
        self.login_button.setText("重新扫码" if self.session else "扫码登录")

    def update_controls(self, *_):
        busy = self.job is not None
        logged = bool(self.session and self.session.get("cookie"))
        for item in (self.login_button, self.path, self.browse_button, self.moods, self.albums, self.media):
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
        out = Path(self.path.text()).expanduser() / self.session["uin"]
        options = SyncOptions(
            out, self.albums.isChecked(), self.moods.isChecked(), self.media.isChecked(), ids
        )
        self.log.clear()
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
        self.log.append(text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
        if self.qr_dialog and self.qr_dialog.isVisible():
            self.qr_status.setText(text)
        if data:
            self.counts.setText(
                f"相册 {data['albums']}   /   照片 {data['photos']}   /   说说 {data['moods']}"
                f"   /   下载 {data['downloaded']}   /   跳过 {data['skipped']}   /   失败 {data['failed']}"
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
            self.index = Path(result.index)
            self.open_button.setEnabled(self.index.is_file())
            self.status.setText(
                {
                    "complete": "导出完成，可以打开本地存档",
                    "partial": "部分内容未下载，重新导出可补下载",
                    "cancelled": "已停止，已获取的内容已保存",
                    "error": "读取中断，请检查网络或重新扫码后重试",
                }[result.state]
            )
            self.log.append(f"结果报告：{self.index.parent / 'last-run.json'}")

    def on_error(self, text):
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
        if not self.index or not self.index.is_file():
            filename, _ = QFileDialog.getOpenFileName(
                self, "打开已有存档的 index.html", self.path.text(), "离线存档 (index.html)"
            )
            if not filename:
                return
            self.index = Path(filename)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.index)))

    def closeEvent(self, event):
        if self.job:
            self.close_requested = True
            self.stop()
            event.ignore()
        else:
            event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("QZoneCapsule")
    app.setOrganizationName("QZoneCapsule")
    app.setFont(QFont("PingFang SC" if sys.platform == "darwin" else "Microsoft YaHei", 11))
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = Window()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
