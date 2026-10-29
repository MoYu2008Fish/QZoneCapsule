"""Reference-led native dashboard, with local data and working export controls."""

from collections import Counter
from datetime import date
from pathlib import Path
from shutil import disk_usage

from PySide6.QtCore import QByteArray, QPointF, QRectF, QSize, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QFontMetrics,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

ASSETS = Path(__file__).parent / "assets"

GEAR_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24">'
    '<g fill="none" stroke="#7c8bad" stroke-width="1.6" stroke-linecap="round" '
    'stroke-linejoin="round"><circle cx="12" cy="12" r="3.2"/>'
    '<circle cx="12" cy="12" r="6.4"/>'
    '<path d="M12 2.9v2M12 19.1v2M2.9 12h2M19.1 12h2'
    'M5.6 5.6l1.4 1.4M17 17l1.4 1.4M5.6 18.4l1.4-1.4M17 7l1.4-1.4"/></g></svg>'
)


def icon(name):
    return QIcon(str(ASSETS / f"{name}.svg"))


def tinted_icon(name, color="#5b7099", size=48):
    """Recolour a line icon so active navigation keeps the reference look."""
    path = ASSETS / f"{name}.svg"
    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return QIcon(str(path))
    source = (
        source.replace('stroke="#59709b"', f'stroke="{color}"')
        .replace('stroke="#63798d"', f'stroke="{color}"')
        .replace('stroke="white"', f'stroke="{color}"')
    )
    return svg_icon(source, size)


def svg_icon(source, size=48):
    renderer = QSvgRenderer(QByteArray(source.encode("utf-8")))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)


def elevate(widget, blur=28, offset=8, alpha=26):
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, offset)
    color = QColor("#16304f")
    color.setAlpha(alpha)
    effect.setColor(color)
    widget.setGraphicsEffect(effect)


def _chart_font(painter, size, weight=QFont.Weight.Normal):
    font = QFont(painter.font())
    font.setPixelSize(size)
    font.setWeight(weight)
    return font


def _smooth_path(points):
    path = QPainterPath(points[0])
    for index in range(len(points) - 1):
        previous = points[index - 1] if index else points[0]
        current = points[index]
        following = points[index + 1]
        after = points[index + 2] if index + 2 < len(points) else following
        first = QPointF(
            current.x() + (following.x() - previous.x()) / 6,
            current.y() + (following.y() - previous.y()) / 6,
        )
        second = QPointF(
            following.x() - (after.x() - current.x()) / 6,
            following.y() - (after.y() - current.y()) / 6,
        )
        path.cubicTo(first, second, following)
    return path


class ArchiveChart(QWidget):
    """A chart of loaded local records, never a fabricated remote account total."""

    def __init__(self, timeline=False):
        super().__init__()
        self.timeline = timeline
        self.entries = []
        self.setMinimumHeight(120 if timeline else 124)
        self.setAccessibleName("本地回忆年份分布" if timeline else "本地内容统计")

    def set_entries(self, entries):
        self.entries = entries
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        colors = ["#4f8cff", "#b78bfa", "#ff9db8", "#ffcf87", "#6bdcb8", "#6cc9f2", "#c0a6f5"]
        counts = Counter(e["kind"] for e in self.entries)
        if self.timeline:
            years = list(range(date.today().year - 6, date.today().year + 1))
            dated = Counter(
                str(e.get("time") or e.get("created_at") or e.get("last_upload_at") or "")[:4]
                for e in self.entries
            )
            values = [dated[str(year)] for year in years]
            names = [str(year) for year in years]
        else:
            values = [counts["mood"], None, counts["photo"], None, None, None, None]
            names = ["说说", "日志", "照片", "留言", "评论", "视频", "好友互动"]
        maximum = max([v or 0 for v in values] + [1])
        for i in range(3):
            y = 18 + (h - 46 - 18) * i / 2
            p.setPen(QPen(QColor("#eef3fb"), 1))
            p.drawLine(6, int(y), w - 6, int(y))
        if self.timeline:
            self._paint_timeline(p, w, h, values, names)
        else:
            self._paint_bars(p, w, h, colors, values, names, maximum)
        p.end()

    def _paint_bars(self, p, w, h, colors, values, names, maximum):
        label_band = 28
        base = h - label_band
        top = 24
        span = (w - 12) / 7
        for i, (name, value) in enumerate(zip(names, values)):
            x = 6 + span * (i + 0.5)
            bar_width = min(30, span * 0.52)
            if value:
                height = max(6.0, (base - top - 22) * value / maximum)
                gradient = QLinearGradient(0, base - height, 0, base)
                gradient.setColorAt(0, QColor(colors[i]))
                faded = QColor(colors[i])
                faded.setAlpha(120)
                gradient.setColorAt(1, faded)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(gradient)
                p.drawRoundedRect(
                    QRectF(x - bar_width / 2, base - height, bar_width, height), bar_width / 2, bar_width / 2
                )
                caption = f"{value:,}"
                p.setFont(_chart_font(p, 10, QFont.Weight.DemiBold))
                p.setPen(QColor("#43527a"))
                p.drawText(
                    QRectF(x - span / 2, base - height - 19, span, 16),
                    Qt.AlignmentFlag.AlignCenter,
                    caption,
                )
            else:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor("#eaf0fa"))
                p.drawRoundedRect(QRectF(x - bar_width / 2, base - 4, bar_width, 4), 2, 2)
                p.setFont(_chart_font(p, 10, QFont.Weight.DemiBold))
                p.setPen(QColor("#b3bfd6"))
                p.drawText(
                    QRectF(x - span / 2, base - 28, span, 18),
                    Qt.AlignmentFlag.AlignCenter,
                    "0" if value == 0 else "—",
                )
            p.setPen(QColor("#8a99ba"))
            p.setFont(_chart_font(p, 10))
            p.drawText(QRectF(x - span / 2, base + 6, span, 18), Qt.AlignmentFlag.AlignCenter, name)

    def _paint_timeline(self, p, w, h, values, names):
        top, base = 54, h - 26
        points = []
        span = (w - 28) / (len(values) - 1 or 1)
        maximum = max(values + [1])
        for index, value in enumerate(values):
            x = 14 + span * index
            y = base - (base - top) * value / maximum
            points.append(QPointF(x, y))
        path = _smooth_path(points)
        area = QPainterPath(path)
        area.lineTo(points[-1].x(), base)
        area.lineTo(points[0].x(), base)
        area.closeSubpath()
        gradient = QLinearGradient(0, top, 0, base)
        gradient.setColorAt(0, QColor("#cfe2ff"))
        gradient.setColorAt(1, QColor("#ffffff"))
        p.fillPath(area, gradient)
        p.setPen(QPen(QColor("#3a78f5"), 2.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        for point in points:
            p.setBrush(QColor("#ffffff"))
            p.setPen(QPen(QColor("#3a78f5"), 2))
            p.drawEllipse(point, 4, 4)
        p.setFont(_chart_font(p, 10))
        for point, name in zip(points, names):
            p.setPen(QColor("#94a1bd"))
            p.drawText(
                QRectF(point.x() - span / 2, base + 8, span, 16),
                Qt.AlignmentFlag.AlignCenter,
                name,
            )
        if not any(values):
            p.setPen(QColor("#94a1bd"))
            p.drawText(
                QRectF(0, 6, w, 24),
                Qt.AlignmentFlag.AlignCenter,
                "添加本地存档后，查看回忆的年份分布",
            )
            return
        last = points[-1]
        box = QRectF(min(max(last.x() - 48, 6), w - 102), last.y() - 50, 96, 38)
        if box.top() < 2:
            box.moveTop(last.y() + 12)
        p.setPen(QPen(QColor("#e6eefb"), 1))
        p.setBrush(QColor("#ffffff"))
        p.drawRoundedRect(box, 10, 10)
        p.setPen(QColor("#94a1bd"))
        p.setFont(_chart_font(p, 9))
        p.drawText(box.adjusted(10, 5, 0, 0), Qt.AlignmentFlag.AlignLeft, names[-1])
        p.setPen(QColor("#2f5cf5"))
        p.setFont(_chart_font(p, 12, QFont.Weight.DemiBold))
        p.drawText(
            box.adjusted(10, 0, -6, -4),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom,
            f"{values[-1]:,} 条",
        )


class ActionButton(QPushButton):
    """Gradient call-to-action with a title and a quieter caption line."""

    def __init__(self, title, caption, colors, glyph, parent=None):
        super().__init__(parent)
        self.title = title
        self.caption = caption
        self.colors = tuple(QColor(color) for color in colors)
        self.glyph = QIcon(str(ASSETS / f"{glyph}.svg"))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(86)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(title)

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        top, bottom = self.colors
        if not self.isEnabled():
            top, bottom = QColor("#cfdcf5"), QColor("#c6cbf0")
        elif self.isDown():
            top, bottom = top.darker(107), bottom.darker(107)
        elif self.underMouse():
            top, bottom = top.lighter(108), bottom.lighter(106)
        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        gradient.setColorAt(0, top)
        gradient.setColorAt(1, bottom)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(gradient)
        p.drawRoundedRect(rect, 14, 14)
        sheen = QLinearGradient(rect.topLeft(), QPointF(rect.left(), rect.center().y()))
        sheen.setColorAt(0, QColor(255, 255, 255, 46))
        sheen.setColorAt(1, QColor(255, 255, 255, 0))
        p.setBrush(sheen)
        p.drawRoundedRect(rect, 14, 14)
        title_font = QFont(self.font())
        title_font.setPixelSize(15)
        title_font.setWeight(QFont.Weight.DemiBold)
        caption_font = QFont(self.font())
        caption_font.setPixelSize(11)
        caption_color = QColor(255, 255, 255, 205) if self.isEnabled() else QColor("#f2f5fc")
        title_width = QFontMetrics(title_font).horizontalAdvance(self.title)
        caption_width = QFontMetrics(caption_font).horizontalAdvance(self.caption)
        text_width = max(title_width, caption_width)
        total = 28 + 12 + text_width
        left = rect.left() + (rect.width() - total) / 2
        pixmap = self.glyph.pixmap(QSize(28, 28))
        p.drawPixmap(int(left), int(rect.center().y() - 14), pixmap)
        text_left = left + 40
        p.setFont(title_font)
        p.setPen(QColor("#ffffff") if self.isEnabled() else QColor("#f4f7fd"))
        p.drawText(
            QRectF(text_left, rect.center().y() - 21, text_width + 4, 22),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self.title,
        )
        p.setFont(caption_font)
        p.setPen(caption_color)
        p.drawText(
            QRectF(text_left, rect.center().y() + 1, text_width + 4, 20),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            self.caption,
        )
        if self.hasFocus():
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(255, 255, 255, 160), 1.5))
            p.drawRoundedRect(rect.adjusted(3, 3, -3, -3), 11, 11)
        p.end()


class Dashboard(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("exportContent")
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(14, 14, 14, 14)
        self.grid.setSpacing(12)
        self.sections = []
        self.wide = None

    def arrange(self):
        wide = self.width() >= 1040
        if wide == self.wide:
            return
        self.wide = wide
        for frame in self.sections:
            self.grid.removeWidget(frame)
        placements = [
            (0, 0, 1, 7),
            (0, 7, 1, 5),
            (1, 0, 1, 7),
            (1, 7, 1, 5),
            (2, 0, 1, 7),
            (2, 7, 1, 5),
            (3, 0, 1, 7),
            (3, 7, 1, 5),
        ]
        for i, frame in enumerate(self.sections):
            self.grid.addWidget(frame, *(placements[i] if wide else (i, 0, 1, 12)))
        for column in range(12):
            self.grid.setColumnStretch(column, 1)
        for row in range(4):
            self.grid.setRowStretch(row, 0)
        self.grid.setRowStretch(3 if wide else 7, 1)

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
    masthead.setFixedHeight(68)
    heading = QHBoxLayout(masthead)
    heading.setContentsMargins(22, 10, 22, 10)
    heading.setSpacing(12)
    logo = QLabel()
    logo.setPixmap(
        QPixmap(str(ASSETS / "app-icon.png")).scaled(
            46, 46, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
    )
    heading.addWidget(logo)
    brand = QVBoxLayout()
    brand.setSpacing(1)
    brand.addWidget(label("QQ空间导出管理器", "brand"))
    brand.addWidget(label("扣扣时光 · 珍藏青春，留住回忆", "muted"))
    heading.addLayout(brand)
    heading.addStretch()
    win.tagline = label("让回忆，拥有更长的生命力 ✨", "tagline")
    heading.addWidget(win.tagline)
    settings = QPushButton()
    settings.setObjectName("mastheadAction")
    settings.setIcon(svg_icon(GEAR_SVG, 32))
    settings.setIconSize(QSize(16, 16))
    settings.setToolTip("前往存储设置")
    settings.setCursor(Qt.CursorShape.PointingHandCursor)
    settings.setAccessibleName("存储设置")
    settings.clicked.connect(lambda: win.navigate("storage"))
    heading.addWidget(settings)
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
    win.sidebar.setFixedWidth(196)
    nav = QVBoxLayout(win.sidebar)
    nav.setContentsMargins(12, 20, 12, 16)
    nav.setSpacing(6)
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
        item.setIcon(tinted_icon(glyph, "#2a5cf0" if target == "overview" else "#5b7099"))
        item.setIconSize(QSize(20, 20))
        item.setObjectName("navItem")
        item.setCursor(Qt.CursorShape.PointingHandCursor)
        item.setCheckable(True)
        item.setChecked(target == "overview")
        win.nav_group.addButton(item)
        item.toggled.connect(lambda checked, target=target: win.navigate(target) if checked else None)
        item.toggled.connect(
            lambda checked, item=item, glyph=glyph: item.setIcon(
                tinted_icon(glyph, "#2a5cf0" if checked else "#5b7099")
            )
        )
        item.setProperty("destination", target)
        nav.addWidget(item)
        win.nav_buttons.append(item)
    win.compact_nav.activated.connect(lambda index: win.navigate(win.compact_nav.itemData(index)))
    nav.addStretch()
    art = QLabel()
    art.setPixmap(
        QPixmap(str(ASSETS / "memories.svg")).scaledToWidth(168, Qt.TransformationMode.SmoothTransformation)
    )
    art.setAlignment(Qt.AlignmentFlag.AlignCenter)
    nav.addWidget(art)
    title = label("时光不散场", "sidebarTitle")
    slogan_font = QFont("Songti SC")
    slogan_font.setItalic(True)
    title.setFont(slogan_font)
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    nav.addWidget(title)
    subtitle = label("把青春的故事，\n好好保存下来。", "muted")
    subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
    nav.addWidget(subtitle)
    nav.addSpacing(22)
    footer = label(f"扣扣时光  v{win.version}   ·   本地保存", "muted")
    footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
    nav.addWidget(footer)
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

    def card(title, key, glyph):
        frame = QFrame()
        frame.setObjectName("card")
        elevate(frame)
        box = QVBoxLayout(frame)
        box.setContentsMargins(18, 10, 18, 10)
        box.setSpacing(8)
        header = QHBoxLayout()
        header.setSpacing(7)
        if glyph:
            mark = QLabel()
            mark.setPixmap(tinted_icon(glyph, "#8fa1c4").pixmap(17, 17))
            header.addWidget(mark)
        header.addWidget(label(title, "cardtitle"))
        header.addStretch()
        box.addLayout(header)
        win.dashboard.sections.append(frame)
        win.anchors[key] = frame
        return box, header

    account, account_header = card("账号信息", "account", "user")
    account_header.addWidget(label("本地优先 · 凭据不出本机", "pill"))
    row = QHBoxLayout()
    row.setSpacing(18)
    avatar = label("QQ", "avatar")
    avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
    avatar.setFixedSize(70, 70)
    row.addWidget(avatar, 0, Qt.AlignmentFlag.AlignTop)
    details = QVBoxLayout()
    details.setSpacing(5)
    win.account = label("", "accountName", True)
    details.addWidget(win.account)
    identity = QHBoxLayout()
    identity.setSpacing(6)
    win.account_id = label("QQ空间ID —", "accountId")
    identity.addWidget(win.account_id)
    win.copy_button = button("复制", win.copy_uin)
    win.copy_button.setFixedHeight(24)
    win.copy_button.setMaximumWidth(48)
    win.copy_button.setToolTip("复制 QQ 号")
    identity.addWidget(win.copy_button)
    identity.addStretch()
    details.addLayout(identity)
    details.addWidget(label("让回忆拥有更长的生命力 · 全部内容保存在本地", "muted"))
    details.addSpacing(4)
    login_row = QHBoxLayout()
    login_row.setSpacing(8)
    win.login_button = button("扫码登录", win.login, True)
    win.forget_button = button("退出登录", win.forget)
    login_row.addWidget(win.login_button)
    login_row.addWidget(win.forget_button)
    login_row.addStretch()
    details.addLayout(login_row)
    details.addStretch()
    row.addLayout(details, 1)
    summary = QFrame()
    summary.setObjectName("accountSummary")
    summary.setMinimumWidth(228)
    summary_box = QVBoxLayout(summary)
    summary_box.setContentsMargins(22, 3, 4, 3)
    summary_box.setSpacing(0)
    win.local_metrics = {}
    metrics = [
        ("user", "珍藏账号", "local_accounts", "0 个", "#eef3ff", "#4f7bf0"),
        ("content", "本地内容", "local_records", "0 条", "#f2edff", "#9a6cf0"),
        ("chat", "已存说说", "local_moods", "0 条", "#e9f7ff", "#2f9fe0"),
        ("photo", "已存照片", "local_photos", "0 张", "#fff1f5", "#e8709b"),
    ]
    for index, (glyph, name, attr, initial, tint, ink) in enumerate(metrics):
        line = QHBoxLayout()
        line.setSpacing(10)
        badge = QLabel()
        badge.setFixedSize(26, 26)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(f"background:{tint};border-radius:8px;")
        badge.setPixmap(tinted_icon(glyph, ink, 32).pixmap(15, 15))
        line.addWidget(badge)
        line.addWidget(label(name, "tileCount"))
        line.addStretch()
        value = label(initial, "metricValue")
        line.addWidget(value)
        summary_box.addLayout(line)
        if index < len(metrics) - 1:
            summary_box.addStretch(1)
        setattr(win, attr, value)
        win.local_metrics[attr] = value
    row.addWidget(summary)
    account.addLayout(row)

    stats, stats_header = card("空间内容统计", "statistics", "database")
    stats_header.addWidget(label("本地存档", "pill"))
    win.content_chart = ArchiveChart()
    stats.addWidget(win.content_chart, 1)
    stats.addWidget(label("统计范围：已加载的本地存档 · — 表示暂不支持", "muted", True))

    choose, choose_header = card("选择导出内容", "content", "content")
    choose_header.addWidget(label("说说 · 相册可导出", "pill"))
    row = QHBoxLayout()
    row.setSpacing(8)
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
        tile.setMinimumHeight(84)
        tile_box = QVBoxLayout(tile)
        tile_box.setContentsMargins(6, 4, 6, 6)
        tile_box.setSpacing(2)
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
        caption = label("可导出" if control is not None else "暂不支持", "tileCount")
        caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tile_box.addWidget(caption)
        if key:
            win.selection_counts[key] = caption
        row.addWidget(tile, 1)
    choose.addLayout(row)
    divider = QFrame()
    divider.setObjectName("tileDivider")
    choose.addWidget(divider)
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

    storage, storage_header = card("导出格式与存储", "storage", "folder")
    storage_header.addWidget(label("离线可看", "pill"))
    formats = QHBoxLayout()
    formats.setSpacing(8)
    for name, caption, badge, tint, ink in [
        ("HTML", "离线网页版", "HTML", "#eaf1ff", "#3a6bff"),
        ("JSON", "结构化数据", "JSON", "#f2edff", "#8b5cf6"),
        ("图片", "原始媒体", "IMG", "#fff0f5", "#e8709b"),
    ]:
        tile = QFrame()
        tile.setObjectName("formatTile")
        tile_box = QVBoxLayout(tile)
        tile_box.setContentsMargins(10, 6, 10, 6)
        tile_box.setSpacing(3)
        mark = QLabel(badge)
        mark.setObjectName("formatBadge")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setFixedSize(32, 18)
        mark.setStyleSheet(f"background:{tint};color:{ink};border-radius:6px;")
        row = QHBoxLayout()
        row.setSpacing(7)
        row.addWidget(mark)
        texts = QVBoxLayout()
        texts.setSpacing(0)
        texts.addWidget(label(name, "formatName"))
        texts.addWidget(label(caption, "formatCaption"))
        row.addLayout(texts, 1)
        tile_box.addLayout(row)
        formats.addWidget(tile, 1)
    storage.addLayout(formats)
    try:
        free = disk_usage(Path.home()).free
        storage_hint = f"磁盘可用 {free / 1024**3:.1f} GB"
    except OSError:
        storage_hint = "建议预留 5 GB 以上空间"
    field = QHBoxLayout()
    field.addWidget(label("保存位置", "fieldLabel"))
    field.addStretch()
    field.addWidget(label(storage_hint, "muted"))
    storage.addLayout(field)
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

    task, task_header = card("导出进度", "tasks", "download")
    win.stop_button = button("停止导出", win.stop)
    win.stop_button.setObjectName("stopButton")
    task_header.addWidget(win.stop_button)
    row = QHBoxLayout()
    row.setSpacing(14)
    thumb = QLabel()
    thumb.setObjectName("taskThumb")
    thumb.setFixedSize(54, 54)
    thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
    thumb.setPixmap(tinted_icon("download", "#5b79c8", 60).pixmap(26, 26))
    row.addWidget(thumb)
    texts = QVBoxLayout()
    texts.setSpacing(3)
    texts.addWidget(label("QQ 空间导出任务", "fieldLabel"))
    win.status = label("准备就绪 · 登录后即可开始", "muted", True)
    texts.addWidget(win.status)
    row.addLayout(texts, 1)
    exported = QVBoxLayout()
    exported.setSpacing(0)
    win.exported_value = label("0", "bigNumber")
    win.exported_value.setAlignment(Qt.AlignmentFlag.AlignRight)
    exported.addWidget(win.exported_value)
    caption = label("已导出项目", "bigNumberCaption")
    caption.setAlignment(Qt.AlignmentFlag.AlignRight)
    exported.addWidget(caption)
    row.addLayout(exported)
    task.addLayout(row)
    win.progress = QProgressBar()
    win.progress.setRange(0, 1)
    win.progress.setValue(0)
    win.progress.setTextVisible(False)
    task.addWidget(win.progress)
    win.counts = label("相册 0   /   照片 0   /   说说 0   /   下载 0   /   失败 0", "muted", True)
    task.addWidget(win.counts)

    actions = QWidget()
    actions.setObjectName("actionPanel")
    action_box = QHBoxLayout(actions)
    action_box.setContentsMargins(0, 0, 0, 0)
    action_box.setSpacing(12)
    win.start_button = ActionButton("开始导出", "根据已选内容导出到本地", ("#4aa6ff", "#4c5bff"), "play")
    win.start_button.clicked.connect(win.start_sync)
    action_box.addWidget(win.start_button)
    win.open_button = ActionButton("本地时光馆", "重温已保存的回忆", ("#c084f8", "#6a46fb"), "database")
    win.open_button.clicked.connect(win.open_archive)
    action_box.addWidget(win.open_button)
    win.dashboard.sections.append(actions)

    logs, logs_header = card("导出任务列表", "logs", "log")
    logs_header.addWidget(label("本次会话", "pill"))
    win.task_table = QTreeWidget()
    win.task_table.setObjectName("taskTable")
    win.task_table.setHeaderLabels(["任务名称", "内容范围", "状态", "结果"])
    win.task_table.setRootIsDecorated(False)
    win.task_table.setMinimumHeight(110)
    win.task_table.setMaximumHeight(120)
    header_view = win.task_table.header()
    header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
    header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
    header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
    header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
    win.task_table.setColumnWidth(2, 92)
    win.task_row = QTreeWidgetItem(["尚未开始导出", "—", "准备就绪", "—"])
    win.task_row.setForeground(2, QBrush(QColor("#8a99ba")))
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
    history, history_header = card("回忆时间分布", "timeline", "archive")
    history_header.addWidget(label("最近七年", "pill"))
    win.timeline_chart = ArchiveChart(timeline=True)
    history.addWidget(win.timeline_chart, 1)
    win.dashboard.arrange()
