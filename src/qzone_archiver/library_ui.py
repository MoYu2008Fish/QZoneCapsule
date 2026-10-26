"""Native, offline archive browser with account filters and a shared timeline."""

from __future__ import annotations

from html import escape
from pathlib import Path

from PySide6.QtCore import QSettings, QSize, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QImageReader, QKeySequence, QPixmap, QShortcut, QTextDocument
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from .emotions import emotion_description, plain_qq_text, qq_html
from .feed_ui import FeedList, media_items
from .library import local_media, read_library, read_run_issues


class LibraryLoad(QThread):
    loaded = Signal(object, object)

    def __init__(self, roots, parent):
        super().__init__(parent)
        self.roots = roots

    def run(self):
        try:
            entries, errors = read_library(self.roots)
        except Exception:  # noqa: BLE001 - worker boundary keeps the library usable
            entries, errors = [], ["无法读取所选存档目录，请检查目录权限。"]
        self.loaded.emit(entries, errors)


class LocalBrowser(QTextBrowser):
    def loadResource(self, resource_type, url):
        # Documents supplied by the app only reference decoded image resources.
        # Never allow QTextBrowser to fetch a remote URL or arbitrary local file.
        return None


class LibraryWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings("QZoneCapsule", "ArchiveLibrary")
        self.roots = [Path(p) for p in self.settings.value("roots", [], type=list)]
        self.entries = []
        self.run_issues = []
        self.filtered = []
        self.loader = None
        self.pending_refresh = False
        self.album = None
        self.images = []
        box = QVBoxLayout(self)
        box.setContentsMargins(24, 24, 24, 20)
        hero = QFrame()
        hero.setObjectName("spaceHero")
        hero.setStyleSheet(
            "QFrame#spaceHero {background:qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "stop:0 #387dc0,stop:1 #78b8dd);border-radius:14px;}"
            "QFrame#spaceHero QLabel {color:white;background:transparent;}"
        )
        hero_box = QVBoxLayout(hero)
        hero_box.setContentsMargins(25, 22, 25, 20)
        hero_box.addWidget(QLabel("QZONE  /  我的离线空间"))
        self.profile_title = QLabel("把每一年的回忆，放回空间里。")
        self.profile_title.setStyleSheet("font-size:25px;font-weight:700;")
        hero_box.addWidget(self.profile_title)
        hint = QLabel("说说 · 相册 · 照片    全部保存在本地，支持多个账号合并浏览。")
        hint.setWordWrap(True)
        hero_box.addWidget(hint)
        box.addWidget(hero)
        row = QHBoxLayout()
        self.account = QComboBox()
        self.account.addItem("合并查看全部账号", "")
        self.account.setMinimumWidth(260)
        self.kind = QComboBox()
        for title, value in (("时间线", "timeline"), ("相册", "album"), ("照片", "photo"), ("说说", "mood")):
            self.kind.addItem(title, value)
        self.year = QComboBox()
        self.year.addItem("全部年份", "")
        self.mode = QComboBox()
        self.mode.addItem("空间动态 · 预览全部", "feed")
        self.mode.addItem("列表与详情", "list")
        self.search = QLineEdit()
        self.search.setPlaceholderText("搜索内容、相册名称或日期")
        row.addWidget(self.account)
        row.addWidget(self.kind)
        row.addWidget(self.year)
        row.addWidget(self.search, 1)
        box.addLayout(row)
        row = QHBoxLayout()
        add = QPushButton("添加已有存档")
        add.clicked.connect(self.choose_root)
        refresh = QPushButton("刷新")
        refresh.clicked.connect(self.refresh)
        self.back = QPushButton("返回相册")
        self.back.clicked.connect(self.leave_album)
        self.back.hide()
        row.addWidget(add)
        row.addWidget(refresh)
        self.report_button = QPushButton("查看归档结果 / 未完成项")
        self.report_button.clicked.connect(self.show_run_issues)
        row.addWidget(self.report_button)
        row.addWidget(self.back)
        row.addStretch()
        row.addWidget(self.mode)
        box.addLayout(row)
        self.summary = QLabel("导出后点击刷新，或添加已有存档文件夹。无需登录也可以查看。")
        self.summary.setWordWrap(True)
        summary_row = QHBoxLayout()
        summary_row.addWidget(self.summary, 1)
        self.all_button = QPushButton("查看全部")
        self.all_button.clicked.connect(self.show_all)
        summary_row.addWidget(self.all_button)
        box.addLayout(summary_row)
        splitter = QSplitter()
        self.list = QListWidget()
        self.list.setSpacing(5)
        self.list.setMinimumWidth(260)
        self.list.setWordWrap(True)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.detail = LocalBrowser()
        self.detail.setOpenLinks(False)
        self.detail.anchorClicked.connect(self.preview)
        splitter.addWidget(self.list)
        splitter.addWidget(self.detail)
        splitter.setSizes([340, 520])
        self.views = QStackedWidget()
        self.feed = FeedList()
        self.feed.itemClicked.connect(self.open_feed_entry)
        self.feed.mediaClicked.connect(self.open_feed_image)
        self.views.addWidget(self.feed)
        self.views.addWidget(splitter)
        box.addWidget(self.views, 1)
        self.more = QPushButton("加载更多")
        self.more.clicked.connect(self.append_page)
        self.more.hide()
        box.addWidget(self.more)
        self.account.currentIndexChanged.connect(self.leave_album)
        self.kind.currentIndexChanged.connect(self.leave_album)
        self.year.currentIndexChanged.connect(self.filter_entries)
        self.mode.currentIndexChanged.connect(lambda i: self.views.setCurrentIndex(i))
        self.search.textChanged.connect(self.filter_entries)
        self.list.currentItemChanged.connect(self.show_entry)
        self.list.itemDoubleClicked.connect(self.enter_album)

    def add_root(self, root: Path, *, refresh=True):
        root = root.expanduser().resolve()
        if root not in self.roots:
            self.roots.append(root)
            self.settings.setValue("roots", [str(p) for p in self.roots])
        if refresh:
            self.refresh()

    def choose_root(self):
        folder = QFileDialog.getExistingDirectory(self, "选择存档或包含多个账号的根文件夹")
        if folder:
            self.add_root(Path(folder))

    def refresh(self):
        if self.loader:
            self.pending_refresh = True
            return
        self.summary.setText("正在读取本地存档…")
        self.loader = LibraryLoad(list(self.roots), self)
        self.loader.loaded.connect(self.on_loaded)
        self.loader.finished.connect(self.load_finished)
        self.loader.start()

    def load_finished(self):
        loader, self.loader = self.loader, None
        loader.deleteLater()
        if self.pending_refresh:
            self.pending_refresh = False
            self.refresh()

    def on_loaded(self, entries, errors):
        self.entries = entries
        selected = self.account.currentData()
        self.account.blockSignals(True)
        self.account.clear()
        self.account.addItem(f"合并查看全部账号 · {len({e['uin'] for e in entries})} 个账号", "")
        accounts = {e["uin"]: e["owner"] for e in entries}
        for uin, title in sorted(accounts.items()):
            self.account.addItem(title, uin)
        index = self.account.findData(selected)
        self.account.setCurrentIndex(max(0, index))
        self.account.blockSignals(False)
        chosen_year = self.year.currentData()
        self.year.blockSignals(True)
        self.year.clear()
        self.year.addItem("全部年份", "")
        years = sorted(
            {str(e.get("time") or e.get("last_upload_at") or e.get("created_at") or "")[:4] for e in entries},
            reverse=True,
        )
        for year in years:
            if len(year) == 4 and year.isdigit():
                self.year.addItem(f"{year} 年", year)
        self.year.setCurrentIndex(max(0, self.year.findData(chosen_year)))
        self.year.blockSignals(False)
        self.album = None
        self.back.hide()
        self.run_issues = read_run_issues(self.roots)
        self.filter_entries()
        if errors:
            self.summary.setText(self.summary.text() + " · " + errors[0])

    def leave_album(self, *_):
        self.album = None
        self.back.hide()
        self.filter_entries()

    def filter_entries(self, *_):
        uin = self.account.currentData()
        issues = [i for i in self.run_issues if not uin or i["uin"] == uin]
        failed = sum(issue["severity"] == "failed" for issue in issues)
        self.report_button.setText(f"归档结果 · 失败 {failed} · 暂不支持 {len(issues) - failed}")
        kind = self.kind.currentData()
        text = self.search.text().strip().lower()
        entries = [e for e in self.entries if not uin or e["uin"] == uin]
        counts = {k: sum(e["kind"] == k for e in entries) for k in ("album", "photo", "mood")}
        self.summary.setText(
            f"{len({e['uin'] for e in entries})} 个账号 · {counts['album']} 个相册 · "
            f"{counts['photo']} 张照片/视频 · {counts['mood']} 条说说"
        )
        if self.album:
            entries = [e for e in entries if e["kind"] == "photo" and (e["uin"], e["album_id"]) == self.album]
        elif kind != "timeline":
            entries = [e for e in entries if e["kind"] == kind]
        year = self.year.currentData()
        if year:
            entries = [
                e
                for e in entries
                if str(e.get("time") or e.get("last_upload_at") or e.get("created_at") or "").startswith(year)
            ]
        self.filtered = sorted(
            [
                e
                for e in entries
                if not text
                or text
                in " ".join(
                    plain_qq_text(str(e.get(k) or ""))
                    for k in ("name", "desc", "content", "time", "owner", "created_at", "location")
                ).lower()
            ],
            key=lambda e: e.get("time") or e.get("last_upload_at") or e.get("created_at") or "",
            reverse=True,
        )
        self.profile_title.setText("所有账号的空间" if not uin else self.account.currentText())
        self.summary.setText(self.summary.text() + f"   ·   当前筛选 {len(self.filtered)} 条，全部可浏览")
        self.feed.set_grid(kind in ("photo", "album") and not self.album)
        self.feed.clear()
        for entry in self.filtered:
            item = QListWidgetItem(plain_qq_text(entry.get("content") or entry.get("name") or "未命名"))
            item.setData(Qt.ItemDataRole.UserRole, entry)
            item.setToolTip(
                emotion_description("\n".join(str(entry.get(k) or "") for k in ("name", "desc", "content")))
            )
            self.feed.addItem(item)
        self.list.clear()
        self.detail.setPlainText(
            "选择左侧条目查看内容。双击相册可浏览其中的照片。"
            if self.filtered
            else "暂无匹配内容。可以添加已有存档，或切换账号、内容类型与搜索条件。"
        )
        self.append_page()

    def append_page(self):
        start = self.list.count()
        titles = {"album": "相册", "photo": "照片", "mood": "说说"}
        for entry in self.filtered[start:]:
            title = entry.get("content") if entry["kind"] == "mood" else entry.get("name")
            title = " ".join(plain_qq_text(title or "未命名").split())[:70]
            item = QListWidgetItem(
                f"{titles[entry['kind']]} · {title}\n{entry['owner']}\n"
                f"{entry.get('time') or entry.get('created_at') or '未知时间'}"
            )
            item.setData(Qt.ItemDataRole.UserRole, entry)
            item.setToolTip(
                emotion_description("\n".join(str(entry.get(k) or "") for k in ("name", "desc", "content")))
            )
            self.list.addItem(item)
        self.more.setVisible(self.list.count() < len(self.filtered))
        if start == 0 and self.list.count():
            self.list.setCurrentRow(0)

    def enter_album(self, item):
        entry = item.data(Qt.ItemDataRole.UserRole)
        if entry["kind"] == "album":
            self.album = (entry["uin"], entry["id"])
            self.back.show()
            self.search.clear()
            self.year.setCurrentIndex(0)
            self.filter_entries()

    def show_all(self):
        for combo in (self.account, self.kind, self.year, self.mode):
            combo.blockSignals(True)
            combo.setCurrentIndex(0)
            combo.blockSignals(False)
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self.views.setCurrentIndex(0)
        self.leave_album()

    def show_entry(self, item, _previous=None):
        if not item:
            return
        entry = item.data(Qt.ItemDataRole.UserRole)
        title = entry.get("name") or {"album": "未命名相册", "photo": "照片", "mood": "说说"}[entry["kind"]]
        text = entry.get("content") or entry.get("desc") or ""
        self.detail.clear()
        self.images = []
        html = f"<h2>{qq_html(title)}</h2><p>{escape(entry['owner'])}</p>"
        html += f"<p>{escape(entry.get('time') or entry.get('created_at') or '未知时间')}</p>"
        html += f"<p>{qq_html(text)}</p>"
        if entry.get("text_note"):
            html += f'<p style="color:#6d807b;font-size:small">{escape(entry["text_note"])}</p>'
        if entry["kind"] == "album":
            count = sum(
                e["kind"] == "photo" and e["uin"] == entry["uin"] and e["album_id"] == entry["id"]
                for e in self.entries
            )
            html += f'<p>{count} 张照片/视频</p><p><a href="album:open">浏览此相册 →</a></p>'
        media = entry.get("media", []) if entry["kind"] == "mood" else [entry]
        for image in media:
            path = local_media(entry["root"], image.get("path", ""))
            if not path:
                if entry["kind"] != "album":
                    html += "<p>图片尚未下载或文件已缺失；文字和时间信息仍可查看。</p>"
                continue
            decoded = self.read_image(path, 1000)
            if decoded.isNull():
                html += "<p>此媒体暂无法预览。</p>"
                continue
            index = len(self.images)
            self.images.append(path)
            resource = QUrl(f"archive-image:{index}")
            self.detail.document().addResource(QTextDocument.ResourceType.ImageResource, resource, decoded)
            width = min(480, decoded.width(), max(160, self.detail.viewport().width() - 35))
            height = max(1, round(decoded.height() * width / decoded.width()))
            html += (
                f'<p><a href="preview:{index}"><img src="{resource.toString()}" '
                f'width="{width}" height="{height}"></a></p>'
            )
        if entry.get("is_video"):
            html += "<p>视频仅保存了元数据，尚未下载视频源文件。</p>"
        self.detail.setHtml(html)

    def open_feed_entry(self, item):
        entry = item.data(Qt.ItemDataRole.UserRole)
        if entry["kind"] == "album":
            self.enter_album(item)
            return
        self.show_entry(item)
        dialog = QDialog(self)
        dialog.setWindowTitle("空间动态 · 内容详情")
        dialog.resize(820, 760)
        layout = QVBoxLayout(dialog)
        browser = LocalBrowser()
        browser.setOpenLinks(False)
        browser.setDocument(self.detail.document().clone(browser))
        browser.anchorClicked.connect(self.preview)
        layout.addWidget(browser)
        dialog.exec()

    def open_feed_image(self, entry, index):
        selected = local_media(entry["root"], media_items(entry)[index].get("path", ""))
        candidates = self.filtered if entry["kind"] == "photo" else [entry]
        self.images = [
            path
            for record in candidates
            for media in media_items(record)
            if (path := local_media(record["root"], media.get("path", "")))
        ]
        if selected and selected in self.images:
            self.preview(QUrl(f"preview:{self.images.index(selected)}"))

    def show_run_issues(self):
        issues = read_run_issues(self.roots)
        uin = self.account.currentData()
        issues = [i for i in issues if not uin or i["uin"] == uin]
        dialog = QDialog(self)
        dialog.setWindowTitle("归档结果 · 失败与暂不支持的内容")
        dialog.resize(840, 560)
        layout = QVBoxLayout(dialog)
        failed = sum(i["severity"] == "failed" for i in issues)
        layout.addWidget(QLabel(f"下载/读取失败 {failed} 项  ·  视频暂不支持 {len(issues) - failed} 项"))
        browser = LocalBrowser()
        rows = []
        for issue in issues:
            identity = str(issue.get("id", ""))
            entry = next(
                (
                    e
                    for e in self.entries
                    if e["root"] == issue["root"]
                    and (not issue["uin"] or e["uin"] == issue["uin"])
                    and (
                        str(e.get("sloc", "")) == identity
                        or (e.get("tid") and identity.startswith(str(e["tid"]) + ":"))
                    )
                ),
                None,
            )
            title = (
                (entry.get("name") or entry.get("content") or "未命名条目") if entry else "未定位到对应内容"
            )
            owner = entry["owner"] if entry else "本地存档"
            state = (
                "暂不支持 · 保留元数据" if issue["severity"] == "unsupported" else "下载/读取失败 · 可重试"
            )
            rows.append(
                f"<h3>{escape(state)}</h3><p>{escape(owner)}</p><p>{qq_html(title)}</p>"
                f"<p>{escape(issue.get('reason') or '')}</p><hr>"
            )
        browser.setHtml("".join(rows) or "<p>未发现未完成项；也可能尚未生成任务报告。</p>")
        layout.addWidget(browser)
        dialog.exec()

    @staticmethod
    def read_image(path, limit):
        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        size = reader.size()
        if size.isValid():
            reader.setScaledSize(size.scaled(QSize(limit, limit), Qt.AspectRatioMode.KeepAspectRatio))
        return reader.read()

    def preview(self, url):
        if url.scheme() == "album" and self.list.currentItem():
            self.enter_album(self.list.currentItem())
            return
        if url.scheme() != "preview":
            return
        try:
            path = self.images[int(url.path())]
        except (ValueError, IndexError):
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(path.name)
        dialog.resize(1000, 760)
        layout = QVBoxLayout(dialog)
        scroll = QScrollArea()
        picture = QLabel()
        picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll.setWidget(picture)
        scroll.setWidgetResizable(True)
        layout.addWidget(scroll)
        controls = QHBoxLayout()
        previous, following = QPushButton("← 上一张"), QPushButton("下一张 →")
        position = QLabel()
        controls.addWidget(previous)
        controls.addWidget(position, 1, Qt.AlignmentFlag.AlignCenter)
        controls.addWidget(following)
        layout.addLayout(controls)
        current = [self.images.index(path)]

        def show(offset=0):
            current[0] = (current[0] + offset) % len(self.images)
            image = self.read_image(self.images[current[0]], 1600)
            bounds = QSize(max(300, dialog.width() - 60), max(250, dialog.height() - 110))
            picture.setPixmap(
                QPixmap.fromImage(image).scaled(
                    bounds, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
                )
            )
            position.setText(f"{current[0] + 1} / {len(self.images)}")

        previous.clicked.connect(lambda: show(-1))
        following.clicked.connect(lambda: show(1))
        QShortcut(QKeySequence("Left"), dialog).activated.connect(lambda: show(-1))
        QShortcut(QKeySequence("Right"), dialog).activated.connect(lambda: show(1))
        show()
        dialog.exec()

    def wait_for_load(self):
        if self.loader:
            self.loader.wait()
