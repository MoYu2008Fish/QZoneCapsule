"""Virtualized space-style cards: every result exists in the model, images decode on paint."""

from __future__ import annotations

from collections import OrderedDict

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImageReader, QPainter, QPen, QTextDocument
from PySide6.QtWidgets import QListView, QListWidget, QStyledItemDelegate

from .emotions import qq_html
from .library import local_media


def media_items(entry):
    if entry["kind"] == "mood":
        return entry.get("media", [])
    if entry["kind"] == "album":
        return entry.get("photos", [])[:1]
    return [entry]


class FeedDelegate(QStyledItemDelegate):
    def __init__(self, view):
        super().__init__(view)
        self.view = view
        self.cache = OrderedDict()

    def body(self, entry, width):
        document = QTextDocument()
        document.setDefaultFont(QFont("PingFang SC", 12))
        document.setDocumentMargin(0)
        document.setTextWidth(max(80, width))
        text = entry.get("content") or entry.get("desc") or ""
        if entry["kind"] != "mood":
            text = (entry.get("name") or "未命名") + ("\n" + text if text else "")
        document.setHtml('<div style="color:#283b4b;line-height:150%">' + qq_html(text) + "</div>")
        return document

    def measures(self, entry, width):
        inner = max(120, width - 48)
        document = self.body(entry, inner)
        text_height = int(document.size().height())
        count = len(media_items(entry))
        columns = 1 if entry["kind"] == "album" or count <= 1 else min(3, count)
        cell = min(420 if count == 1 else 245, (inner - (columns - 1) * 8) / columns)
        rows = (count + columns - 1) // columns
        image_height = rows * (cell + 8) if count else 0
        return document, text_height, count, columns, cell, int(124 + text_height + image_height)

    def sizeHint(self, option, index):
        entry = index.data(Qt.ItemDataRole.UserRole)
        width = self.view.card_width()
        return QSize(width, self.measures(entry, width)[-1])

    def thumbnail(self, entry, relative):
        path = local_media(entry["root"], relative)
        if not path:
            return None
        key = (str(path), path.stat().st_mtime_ns)
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        reader = QImageReader(str(path))
        reader.setAutoTransform(True)
        size = reader.size()
        if size.isValid():
            reader.setScaledSize(size.scaled(QSize(480, 480), Qt.AspectRatioMode.KeepAspectRatio))
        image = reader.read()
        self.cache[key] = image
        while len(self.cache) > 96:
            self.cache.popitem(last=False)
        return image

    def paint(self, painter, option, index):
        entry = index.data(Qt.ItemDataRole.UserRole)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(option.rect).adjusted(4, 5, -4, -5)
        painter.setPen(QPen(QColor("#dbe5ee"), 1))
        painter.setBrush(QColor("#ffffff"))
        painter.drawRoundedRect(rect, 12, 12)
        x, y = rect.x() + 20, rect.y() + 18
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#e5f1fc"))
        painter.drawEllipse(QRectF(x, y, 36, 36))
        painter.setPen(QColor("#2782c5"))
        painter.setFont(QFont("PingFang SC", 12, QFont.Weight.Bold))
        painter.drawText(QRectF(x, y, 36, 36), Qt.AlignmentFlag.AlignCenter, "Q")
        painter.setPen(QColor("#2b668d"))
        painter.setFont(QFont("PingFang SC", 11, QFont.Weight.DemiBold))
        painter.drawText(
            QRectF(x + 48, y - 1, rect.width() - 85, 22), Qt.TextFlag.TextSingleLine, entry["owner"]
        )
        when = entry.get("time") or entry.get("last_upload_at") or entry.get("created_at") or "未知时间"
        category = {"mood": "发表了说说", "photo": "上传了照片", "album": "更新了相册"}[entry["kind"]]
        if entry.get("is_video"):
            category = "视频 · 元数据"
        painter.setFont(QFont("PingFang SC", 9))
        painter.setPen(QColor("#8a9ba8"))
        painter.drawText(QRectF(x + 48, y + 22, rect.width() - 85, 20), f"{when}  ·  {category}")
        document, height, count, columns, cell, _ = self.measures(entry, option.rect.width())
        y += 60
        painter.save()
        painter.translate(x, y)
        document.drawContents(painter)
        painter.restore()
        y += height + 14
        for i, media in enumerate(media_items(entry)):
            tile = QRectF(x + (i % columns) * (cell + 8), y + (i // columns) * (cell + 8), cell, cell)
            painter.fillRect(tile, QColor("#edf3f8"))
            image = self.thumbnail(entry, media.get("path", ""))
            if image is not None and not image.isNull():
                size = image.size().scaled(QSize(int(cell), int(cell)), Qt.AspectRatioMode.KeepAspectRatio)
                target = QRectF(
                    tile.x() + (cell - size.width()) / 2,
                    tile.y() + (cell - size.height()) / 2,
                    size.width(),
                    size.height(),
                )
                painter.drawImage(target, image)
            else:
                painter.setPen(QColor("#8295a5"))
                painter.drawText(
                    tile,
                    Qt.AlignmentFlag.AlignCenter,
                    "视频未下载" if entry.get("is_video") else "图片未下载",
                )
        y += ((count + columns - 1) // columns) * (cell + 8) if count else 0
        painter.setPen(QColor("#8a9ba8"))
        painter.setFont(QFont("PingFang SC", 9))
        foot = (
            f"♡ {entry.get('like_count', 0)}   评论 {entry.get('comment_count', 0)}   ·   查看详情"
            if entry["kind"] == "mood"
            else "查看相册 →"
            if entry["kind"] == "album"
            else "查看图片与说明 →"
        )
        painter.drawText(QRectF(x, y + 5, rect.width() - 40, 20), foot)
        painter.restore()


class FeedList(QListWidget):
    mediaClicked = Signal(object, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.grid = False
        self.setObjectName("spaceFeed")
        self.setSpacing(10)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.setItemDelegate(FeedDelegate(self))
        self.setStyleSheet(
            "QListWidget#spaceFeed {background:#edf3f8;border:none;}"
            "QListWidget#spaceFeed::item {padding:0;border:none;background:transparent;}"
        )

    def card_width(self):
        width = max(260, self.viewport().width() - 24)
        if self.grid:
            columns = max(1, width // 300)
            return max(260, (width - (columns - 1) * 14) // columns)
        return width

    def set_grid(self, grid):
        self.grid = grid
        self.setViewMode(QListView.ViewMode.IconMode if grid else QListView.ViewMode.ListMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setWrapping(grid)
        self.scheduleDelayedItemsLayout()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.scheduleDelayedItemsLayout()

    def mouseReleaseEvent(self, event):
        item = self.itemAt(event.position().toPoint())
        if item and event.button() == Qt.MouseButton.LeftButton:
            entry = item.data(Qt.ItemDataRole.UserRole)
            if entry["kind"] != "album":
                rect = self.visualItemRect(item)
                _, height, _, columns, cell, _ = self.itemDelegate().measures(entry, rect.width())
                for i, media in enumerate(media_items(entry)):
                    tile = QRectF(
                        rect.x() + 24 + (i % columns) * (cell + 8),
                        rect.y() + 97 + height + (i // columns) * (cell + 8),
                        cell,
                        cell,
                    )
                    if tile.contains(event.position()) and local_media(entry["root"], media.get("path", "")):
                        self.mediaClicked.emit(entry, i)
                        event.accept()
                        return
        super().mouseReleaseEvent(event)
