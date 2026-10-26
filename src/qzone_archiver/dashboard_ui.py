"""Reference-led native dashboard, with local data and working export controls."""

from collections import Counter
from datetime import date
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

ASSETS = Path(__file__).parent / "assets"


def icon(name):
    return QIcon(str(ASSETS / f"{name}.svg"))


class ArchiveChart(QWidget):
    """A chart of loaded local records, never a fabricated remote account total."""

    def __init__(self, timeline=False):
        super().__init__()
        self.timeline = timeline
        self.entries = []
        self.setMinimumHeight(106)
        self.setAccessibleName("本地回忆年份分布" if timeline else "本地内容统计")

    def set_entries(self, entries):
        self.entries = entries
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        colors = ["#5489ff", "#ad82f4", "#ff91b4", "#ffc875", "#6bd8b7", "#69c7f2", "#b89aef"]
        if self.timeline:
            years = list(range(date.today().year - 6, date.today().year + 1))
            counts = Counter(
                str(e.get("time") or e.get("created_at") or e.get("last_upload_at") or "")[:4]
                for e in self.entries
            )
            values = [counts[str(y)] for y in years]
            names = [str(y) for y in years]
        else:
            counts = Counter(e["kind"] for e in self.entries)
            values = [counts["mood"], None, counts["photo"], None, None, None, None]
            names = ["说说", "日志", "照片", "留言", "评论", "视频", "好友互动"]
        maximum = max([v or 0 for v in values] + [1])
        base, top = h - 28, 24
        left, span = 12, (w - 24) / 7
        p.setPen(QPen(QColor("#e5ecfb"), 1))
        for i in range(3):
            y = top + (base - top) * i / 2
            p.drawLine(8, int(y), w - 8, int(y))
        points = []
        for i, (name, value) in enumerate(zip(names, values)):
            x = left + span * (i + 0.5)
            height = (base - top - 16) * (value or 0) / maximum
            if self.timeline:
                points.append((x, base - height))
            elif value:
                gradient = QLinearGradient(0, base - height, 0, base)
                gradient.setColorAt(0, QColor(colors[i]))
                faded = QColor(colors[i])
                faded.setAlpha(110)
                gradient.setColorAt(1, faded)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(gradient)
                p.drawRoundedRect(
                    int(x - min(18, span / 3)),
                    int(base - height),
                    int(min(36, span * 2 / 3)),
                    int(height),
                    5,
                    5,
                )
            p.setPen(QColor("#7784a4"))
            p.drawText(int(x - span / 2), base + 7, int(span), 20, Qt.AlignmentFlag.AlignCenter, name)
            if not self.timeline:
                p.setPen(QColor("#28304b"))
                p.drawText(
                    int(x - span / 2),
                    int(base - height - 23),
                    int(span),
                    21,
                    Qt.AlignmentFlag.AlignCenter,
                    "—" if value is None else f"{value:,}",
                )
        if self.timeline:
            path = QPainterPath()
            path.moveTo(*points[0])
            for x, y in points[1:]:
                path.lineTo(x, y)
            fill = QPainterPath(path)
            fill.lineTo(points[-1][0], base)
            fill.lineTo(points[0][0], base)
            fill.closeSubpath()
            gradient = QLinearGradient(0, top, 0, base)
            gradient.setColorAt(0, QColor("#a6c9ff"))
            gradient.setColorAt(1, QColor("#f5f9ff"))
            p.fillPath(fill, gradient)
            p.setPen(QPen(QColor("#4388ff"), 2))
            p.drawPath(path)
            for x, y in points:
                p.setBrush(QColor("#4388ff"))
                p.setPen(QPen(QColor("white"), 2))
                p.drawEllipse(int(x - 4), int(y - 4), 8, 8)
            if not any(values):
                p.setPen(QColor("#7784a4"))
                p.drawText(0, 4, w, 24, Qt.AlignmentFlag.AlignCenter, "添加本地存档后，查看回忆的年份分布")
        p.end()


class Dashboard(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("exportContent")
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(18, 18, 18, 18)
        self.grid.setSpacing(14)
        self.sections = []
        self.wide = None

    def arrange(self):
        wide = self.width() >= 1100
        if wide == self.wide:
            return
        self.wide = wide
        for frame in self.sections:
            self.grid.removeWidget(frame)
        placements = [
            (0, 0, 1, 7),
            (0, 7, 1, 5),
            (1, 0, 1, 7),
            (1, 7, 2, 5),
            (2, 0, 2, 7),
            (3, 7, 1, 5),
            (4, 0, 1, 8),
            (4, 8, 1, 4),
        ]
        for i, frame in enumerate(self.sections):
            self.grid.addWidget(frame, *(placements[i] if wide else (i, 0, 1, 12)))
        for column in range(12):
            self.grid.setColumnStretch(column, 1)
        for row in range(8):
            self.grid.setRowStretch(row, 0)
        self.grid.setRowStretch(4 if wide else 7, 1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.arrange()


def build_dashboard(win):
    from .desktop import button, label
    from .library_ui import LibraryWidget

    root = QWidget()
    root.setObjectName("appShell")
    win.setCentralWidget(root)
    layout = QVBoxLayout(root)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    masthead = QFrame()
    masthead.setObjectName("masthead")
    heading = QHBoxLayout(masthead)
    heading.setContentsMargins(20, 12, 24, 12)
    logo = QLabel()
    logo.setPixmap(
        QPixmap(str(ASSETS / "app-icon.png")).scaled(
            48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
    )
    heading.addWidget(logo)
    brand = QVBoxLayout()
    brand.setSpacing(2)
    brand.addWidget(label("QQ空间导出管理器", "brand"))
    brand.addWidget(label("扣扣时光 · 珍藏青春，留住回忆", "muted"))
    heading.addLayout(brand)
    heading.addStretch()
    win.tagline = label("让回忆，拥有更长的生命力 ✨", "tagline")
    heading.addWidget(win.tagline)
    win.compact_nav = QComboBox()
    win.compact_nav.setAccessibleName("页面导航")
    win.compact_nav.setFixedWidth(142)
    win.compact_nav.hide()
    heading.addWidget(win.compact_nav)
    layout.addWidget(masthead)
    shell = QHBoxLayout()
    shell.setContentsMargins(0, 0, 0, 0)
    shell.setSpacing(0)
    layout.addLayout(shell, 1)
    win.sidebar = QFrame()
    win.sidebar.setObjectName("sidebar")
    win.sidebar.setFixedWidth(200)
    nav = QVBoxLayout(win.sidebar)
    nav.setContentsMargins(12, 22, 12, 18)
    nav.setSpacing(8)
    win.nav_buttons = []
    win.nav_group = QButtonGroup(win)
    win.nav_group.setExclusive(True)
    actions = [
        ("总览", "home", "overview"),
        ("导出任务", "download", "tasks"),
        ("内容选择", "content", "content"),
        ("存储设置", "folder", "storage"),
        ("账号管理", "user", "account"),
        ("本地时光馆", "archive", "library"),
        ("日志中心", "log", "logs"),
    ]
    for title, glyph, target in actions:
        win.compact_nav.addItem(title, target)
        item = QPushButton(title)
        item.setIcon(icon(glyph))
        item.setIconSize(QSize(21, 21))
        item.setObjectName("navItem")
        item.setCheckable(True)
        item.setChecked(target == "overview")
        win.nav_group.addButton(item)
        item.toggled.connect(lambda checked, target=target: win.navigate(target) if checked else None)
        item.setProperty("destination", target)
        nav.addWidget(item)
        win.nav_buttons.append(item)
    win.compact_nav.activated.connect(lambda index: win.navigate(win.compact_nav.itemData(index)))
    nav.addStretch()
    art = QLabel()
    art.setPixmap(
        QPixmap(str(ASSETS / "memories.svg")).scaledToWidth(170, Qt.TransformationMode.SmoothTransformation)
    )
    art.setAlignment(Qt.AlignmentFlag.AlignCenter)
    nav.addWidget(art)
    nav.addWidget(label("时光不散场", "sidebarTitle"))
    nav.addWidget(label("把青春的故事，\n好好保存下来。", "muted"))
    nav.addSpacing(26)
    nav.addWidget(label(f"扣扣时光  v{win.version}", "muted"))
    nav.addWidget(label("本地保存 · 随时重温", "muted"))
    shell.addWidget(win.sidebar)
    win.pages = QTabWidget()
    win.pages.tabBar().hide()
    right = QWidget()
    right_box = QVBoxLayout(right)
    right_box.setContentsMargins(0, 0, 0, 0)
    win.pages.addTab(right, "总览")
    win.library = LibraryWidget()
    win.pages.addTab(win.library, "本地时光馆")
    win.pages.currentChanged.connect(win.on_page_changed)
    shell.addWidget(win.pages, 1)
    win.export_scroll = QScrollArea()
    win.export_scroll.setWidgetResizable(True)
    win.export_scroll.setFrameShape(QFrame.Shape.NoFrame)
    win.dashboard = Dashboard()
    win.export_scroll.setWidget(win.dashboard)
    right_box.addWidget(win.export_scroll)
    win.anchors = {}

    def card(title, key):
        frame = QFrame()
        frame.setObjectName("card")
        box = QVBoxLayout(frame)
        box.setContentsMargins(18, 12, 18, 12)
        box.setSpacing(7)
        box.addWidget(label(title, "cardtitle"))
        win.dashboard.sections.append(frame)
        win.anchors[key] = frame
        return box

    account = card("账号信息", "account")
    row = QHBoxLayout()
    row.setSpacing(16)
    avatar = label("QQ", "avatar")
    avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
    avatar.setFixedSize(76, 76)
    row.addWidget(avatar)
    details = QVBoxLayout()
    details.setSpacing(6)
    win.account = label("", "accountName", True)
    details.addWidget(win.account)
    details.addWidget(label("珍藏青春 · 留住回忆", "muted"))
    login_row = QHBoxLayout()
    win.login_button = button("扫码登录", win.login, True)
    win.forget_button = button("退出登录", win.forget)
    login_row.addWidget(win.login_button)
    login_row.addWidget(win.forget_button)
    login_row.addStretch()
    details.addLayout(login_row)
    row.addLayout(details, 1)
    summary = QFrame()
    summary.setObjectName("accountSummary")
    summary_box = QVBoxLayout(summary)
    summary_box.setContentsMargins(18, 0, 0, 0)
    summary_box.setSpacing(9)
    win.local_accounts = label("珍藏账号     0 个", "muted")
    win.local_records = label("本地内容     0 条", "muted")
    summary_box.addWidget(label("本地时光档案", "fieldLabel"))
    summary_box.addWidget(win.local_accounts)
    summary_box.addWidget(win.local_records)
    row.addWidget(summary)
    account.addLayout(row)
    account.addWidget(label("用手机 QQ 扫码确认，登录凭据仅保存在本机。", "muted", True))

    stats = card("空间内容统计", "statistics")
    win.content_chart = ArchiveChart()
    stats.addWidget(win.content_chart)
    stats.addWidget(label("统计范围：已加载的本地存档 · — 表示暂不支持", "muted", True))

    choose = card("选择导出内容", "content")
    row = QHBoxLayout()
    row.setSpacing(7)
    win.moods = QCheckBox()
    win.albums = QCheckBox()
    win.selection_counts = {}
    categories = [
        ("说说", "chat", win.moods, "mood"),
        ("日志", "journal", None, ""),
        ("相册", "photo", win.albums, "album"),
        ("留言板", "message", None, ""),
        ("评论", "comment", None, ""),
        ("视频", "video", None, ""),
        ("好友互动", "friends", None, ""),
    ]
    for title, glyph, control, key in categories:
        tile = QFrame()
        tile.setObjectName("contentTile" if control else "unavailableTile")
        tile_box = QVBoxLayout(tile)
        tile_box.setContentsMargins(5, 4, 5, 5)
        tile_box.setSpacing(3)
        check_row = QHBoxLayout()
        check_row.addStretch()
        if control is not None:
            control.setAccessibleName(title)
            control.setChecked(True)
            check_row.addWidget(control)
        else:
            check_row.addWidget(label("—", "muted"))
        tile_box.addLayout(check_row)
        picture = QLabel()
        picture.setPixmap(icon(glyph).pixmap(30, 30))
        picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tile_box.addWidget(picture)
        name = label(title, "tileTitle")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tile_box.addWidget(name)
        caption = label("可导出" if control is not None else "暂不支持", "muted")
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tile_box.addWidget(caption)
        if key:
            win.selection_counts[key] = caption
        row.addWidget(tile, 1)
    choose.addLayout(row)
    row = QHBoxLayout()
    win.media = QCheckBox("下载图片")
    win.media.setChecked(True)
    win.all_albums = QCheckBox("全部相册")
    win.all_albums.setChecked(True)
    row.addWidget(win.media)
    row.addWidget(win.all_albums)
    row.addStretch()
    win.load_button = button("选择相册", win.read_albums)
    row.addWidget(win.load_button)
    choose.addLayout(row)
    win.tree = QTreeWidget()
    win.tree.setHeaderLabels(["相册", "条目数", "最近上传"])
    win.tree.setRootIsDecorated(False)
    win.tree.setMinimumHeight(130)
    win.tree.setColumnWidth(0, 240)
    win.tree.hide()
    choose.addWidget(win.tree)
    win.albums.toggled.connect(win.update_controls)
    win.all_albums.toggled.connect(win.update_controls)

    storage = card("导出格式与存储", "storage")
    storage.addWidget(label("自动生成离线网页、结构化数据与媒体文件", "muted", True))
    formats = QHBoxLayout()
    for name, caption in [("HTML", "离线网页版"), ("JSON", "结构化数据"), ("图片", "原始媒体")]:
        tile = label(f"{name}\n{caption}", "formatTile")
        tile.setAlignment(Qt.AlignmentFlag.AlignCenter)
        formats.addWidget(tile, 1)
    storage.addLayout(formats)
    storage.addWidget(label("保存位置", "fieldLabel"))
    row = QHBoxLayout()
    win.path = QLineEdit(
        win.library.settings.value("export_root", str(Path.home() / "Pictures" / "扣扣时光归档"), type=str)
    )
    win.path.setMinimumWidth(60)
    win.path.setAccessibleName("备份根文件夹")
    row.addWidget(win.path, 1)
    win.browse_button = button("更换", win.browse)
    row.addWidget(win.browse_button)
    storage.addLayout(row)
    win.export_mode = QComboBox()
    win.export_mode.addItem("分开保存 · 每个账号一个文件夹", False)
    win.export_mode.addItem("合并保存 · 多个账号汇入同一存档", True)
    storage.addWidget(win.export_mode)

    task = card("导出进度", "tasks")
    top = QHBoxLayout()
    win.status = label("准备就绪 · 登录后即可开始", "taskStatus", True)
    top.addWidget(win.status, 1)
    win.stop_button = button("停止导出", win.stop)
    win.stop_button.setObjectName("stopButton")
    top.addWidget(win.stop_button)
    task.addLayout(top)
    win.progress = QProgressBar()
    win.progress.setRange(0, 1)
    win.progress.setValue(0)
    win.progress.setTextVisible(False)
    task.addWidget(win.progress)
    win.counts = label("相册 0   /   照片 0   /   说说 0   /   下载 0   /   失败 0", "muted", True)
    task.addWidget(win.counts)

    actions = QFrame()
    actions.setObjectName("actionPanel")
    action_box = QHBoxLayout(actions)
    action_box.setContentsMargins(0, 0, 0, 0)
    action_box.setSpacing(12)
    win.start_button = button("开始导出\n保存选定内容", win.start_sync)
    win.start_button.setObjectName("exportAction")
    win.start_button.setIcon(icon("play"))
    win.start_button.setIconSize(QSize(30, 30))
    win.start_button.setMinimumHeight(88)
    action_box.addWidget(win.start_button)
    win.open_button = button("本地时光馆\n重温已保存的回忆", win.open_archive)
    win.open_button.setObjectName("libraryAction")
    win.open_button.setIcon(icon("database"))
    win.open_button.setIconSize(QSize(30, 30))
    win.open_button.setMinimumHeight(88)
    action_box.addWidget(win.open_button)
    win.dashboard.sections.append(actions)

    logs = card("导出任务列表", "logs")
    win.task_table = QTreeWidget()
    win.task_table.setObjectName("taskTable")
    win.task_table.setHeaderLabels(["任务名称", "内容范围", "状态", "结果"])
    win.task_table.setRootIsDecorated(False)
    win.task_table.setMinimumHeight(108)
    win.task_table.setMaximumHeight(108)
    win.task_table.setColumnWidth(0, 200)
    win.task_table.setColumnWidth(1, 160)
    win.task_table.setColumnWidth(2, 100)
    win.task_row = QTreeWidgetItem(["尚未开始导出", "—", "准备就绪", "—"])
    win.task_table.addTopLevelItem(win.task_row)
    logs.addWidget(win.task_table)
    win.log = QTextEdit()
    win.log.setObjectName("taskLog")
    win.log.setReadOnly(True)
    win.log.setFixedHeight(56)
    win.log.setPlaceholderText("任务日志 · 导出后在此查看进度与结果。")
    logs.addWidget(win.log)
    win.log.hide()
    logs.addWidget(label("非腾讯官方工具 · 首次建议选择一个小相册验证。", "muted", True))
    history = card("回忆时间分布", "timeline")
    win.timeline_chart = ArchiveChart(timeline=True)
    history.addWidget(win.timeline_chart)
    history.addWidget(label("最近七年 · 本地说说与照片数量，按内容日期统计", "muted", True))
    win.dashboard.arrange()
