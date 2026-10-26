"""Virtualized space-style cards: every result exists in the model, images decode on paint."""

from __future__ import annotations

from collections import OrderedDict

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QImageReader, QPainter, QPainterPath, QPen, QTextDocument
from PySide6.QtWidgets import QListView, QListWidget, QStyle, QStyledItemDelegate

from .emotions import qq_html
from .library import local_media
from .theme import TOKENS


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
        self.documents = OrderedDict()

    def body(self, entry, width):
        key = (entry["kind"], entry.get("content"), entry.get("desc"), entry.get("name"), int(width))
        if key in self.documents:
            self.documents.move_to_end(key)
            return self.documents[key]
        document = QTextDocument()
        document.setDefaultFont(QFont(self.view.font().family(), 11))
        document.setDocumentMargin(0)
        document.setTextWidth(max(80, width))
        text = entry.get("content") or entry.get("desc") or ""
        if entry["kind"] != "mood":
            text = (entry.get("name") or "未命名") + ("\n" + text if text else "")
        document.setHtml(f'<div style="color:{TOKENS["text"]};line-height:165%">' + qq_html(text) + "</div>")
        self.documents[key] = document
        while len(self.documents) > 256:
            self.documents.popitem(last=False)
        return document

    def measures(self, entry, width):
        inner = max(120, width - 48)
        document = self.body(entry, inner)
        text_height = int(document.size().height())
        count = min(9, len(media_items(entry)))
        columns = 1 if entry["kind"] == "album" or count <= 1 else min(3, count)
        cell = min(300 if count == 1 else 164, (inner - (columns - 1) * 8) / columns)
        rows = (count + columns - 1) // columns
        image_height = rows * (cell + 8) if count else 0
        return document, text_height, count, columns, cell, int(146 + text_height + image_height)

    def sizeHint(self, option, index):
        entry = index.data(Qt.ItemDataRole.UserRole)
        width = self.view.card_width()
        if self.view.grid:
            return QSize(width, int((width - 8) * 0.72 + 82))
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
        if self.view.grid:
            self.paint_grid(painter, option, entry)
            return
        painter.save()
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        rect = QRectF(option.rect).adjusted(4, 5, -4, -5)
        active = option.state & (QStyle.StateFlag.State_MouseOver | QStyle.StateFlag.State_HasFocus)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(TOKENS["shadow_color"]))
        painter.drawRoundedRect(rect.translated(0, 2), TOKENS["radius"], TOKENS["radius"])
        painter.setPen(QPen(QColor(TOKENS["accent"] if active else TOKENS["line"]), 1))
        painter.setBrush(QColor("#ffffff"))
        painter.drawRoundedRect(rect, TOKENS["radius"], TOKENS["radius"])
        x, y = rect.x() + 20, rect.y() + 18
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(TOKENS["soft"]))
        painter.drawEllipse(QRectF(x, y, 36, 36))
        painter.setPen(QColor(TOKENS["accent"]))
        painter.setFont(QFont(self.view.font().family(), 12, QFont.Weight.Bold))
        painter.drawText(QRectF(x, y, 36, 36), Qt.AlignmentFlag.AlignCenter, "Q")
        painter.setPen(QColor(TOKENS["navy"]))
        painter.setFont(QFont(self.view.font().family(), 11, QFont.Weight.DemiBold))
        painter.drawText(
            QRectF(x + 48, y - 1, rect.width() - 85, 22),
            Qt.TextFlag.TextSingleLine,
            painter.fontMetrics().elidedText(
                entry["owner"], Qt.TextElideMode.ElideRight, int(rect.width() - 100)
            ),
        )
        when = entry.get("time") or entry.get("last_upload_at") or entry.get("created_at") or "未知时间"
        category = {"mood": "发表了说说", "photo": "上传了照片", "album": "更新了相册"}[entry["kind"]]
        if entry.get("is_video"):
            category = "视频 · 元数据"
        painter.setFont(QFont(self.view.font().family(), 9))
        painter.setPen(QColor(TOKENS["muted"]))
        painter.drawText(QRectF(x + 48, y + 22, rect.width() - 85, 20), f"{when}  ·  {category}")
        document, height, count, columns, cell, _ = self.measures(entry, option.rect.width())
        y += 60
        painter.save()
        painter.translate(x, y)
        document.drawContents(painter)
        painter.restore()
        y += height + 14
        for i, media in enumerate(media_items(entry)[:9]):
            tile = QRectF(x + (i % columns) * (cell + 8), y + (i // columns) * (cell + 8), cell, cell)
            painter.save()
            clip = QPainterPath()
            clip.addRoundedRect(tile, TOKENS["control_radius"], TOKENS["control_radius"])
            painter.setClipPath(clip)
            painter.fillRect(tile, QColor(TOKENS["panel_2"]))
            image = self.thumbnail(entry, media.get("path", ""))
            if image is not None and not image.isNull():
                size = image.size().scaled(
                    QSize(int(cell), int(cell)), Qt.AspectRatioMode.KeepAspectRatioByExpanding
                )
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
            painter.restore()
        y += ((count + columns - 1) // columns) * (cell + 8) if count else 0
        painter.setPen(QPen(QColor(TOKENS["line"]), 1))
        painter.drawLine(int(x), int(y + 2), int(rect.right() - 20), int(y + 2))
        painter.setPen(QColor(TOKENS["accent"]))
        painter.setFont(QFont(self.view.font().family(), 9))
        foot = (
            f"♡  赞 {entry.get('like_count', 0)}       评论 {entry.get('comment_count', 0)}   ·   查看详情"
            if entry["kind"] == "mood"
            else "查看相册 →"
            if entry["kind"] == "album"
            else "查看图片与说明 →"
        )
        if len(media_items(entry)) > 9:
            foot += f" · 共 {len(media_items(entry))} 张"
        painter.drawText(QRectF(x, y + 12, rect.width() - 40, 20), foot)
        painter.restore()

    def paint_grid(self, painter, option, entry):
        painter.save()
        painter.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        rect = QRectF(option.rect).adjusted(4, 5, -4, -5)
        active = option.state & (QStyle.StateFlag.State_MouseOver | QStyle.StateFlag.State_HasFocus)
        painter.setPen(QPen(QColor(TOKENS["accent"] if active else TOKENS["line"]), 1))
        painter.setBrush(QColor(TOKENS["panel"]))
        painter.drawRoundedRect(rect, TOKENS["radius"], TOKENS["radius"])
        tile = rect.adjusted(10, 10, -10, 0)
        tile.setHeight(rect.width() * 0.72 - 20)
        clip = QPainterPath()
        clip.addRoundedRect(tile, 6, 6)
        painter.save()
        painter.setClipPath(clip)
        painter.fillRect(tile, QColor(TOKENS["panel_2"]))
        media = media_items(entry)
        image = self.thumbnail(entry, media[0].get("path", "")) if media else None
        if image is not None and not image.isNull():
            size = image.size().scaled(tile.size().toSize(), Qt.AspectRatioMode.KeepAspectRatioByExpanding)
            target = QRectF(
                tile.center().x() - size.width() / 2,
                tile.center().y() - size.height() / 2,
                size.width(),
                size.height(),
            )
            painter.drawImage(target, image)
        else:
            painter.setPen(QColor(TOKENS["muted"]))
            painter.drawText(
                tile, Qt.AlignmentFlag.AlignCenter, "暂无封面" if entry["kind"] == "album" else "图片未下载"
            )
        painter.restore()
        painter.setPen(QColor(TOKENS["navy"]))
        painter.setFont(QFont(self.view.font().family(), 11, QFont.Weight.DemiBold))
        title = entry.get("name") or "未命名"
        painter.drawText(
            QRectF(rect.x() + 14, tile.bottom() + 12, rect.width() - 28, 24),
            painter.fontMetrics().elidedText(title, Qt.TextElideMode.ElideRight, int(rect.width() - 28)),
        )
        painter.setFont(QFont(self.view.font().family(), 9))
        painter.setPen(QColor(TOKENS["muted"]))
        caption = entry["owner"]
        if entry["kind"] == "album":
            caption += f" · {len(entry.get('photos', []))} 张/段"
        painter.drawText(
            QRectF(rect.x() + 14, tile.bottom() + 40, rect.width() - 28, 22),
            painter.fontMetrics().elidedText(caption, Qt.TextElideMode.ElideRight, int(rect.width() - 28)),
        )
        painter.restore()


class FeedList(QListWidget):
    mediaClicked = Signal(object, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.grid = False
        self.empty_text = "时光馆还空着\n添加已有存档，开始翻看回忆。"
        self.setMouseTracking(True)
        self.setAccessibleName("空间动态与相册")
        self.setObjectName("spaceFeed")
        self.setSpacing(10)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QListView.ScrollMode.ScrollPerPixel)
        self.setItemDelegate(FeedDelegate(self))
        self.setStyleSheet(
            f"QListWidget#spaceFeed {{background:{TOKENS['bg']};border:none;padding:0;}}"
            "QListWidget#spaceFeed::item {padding:0;border:none;background:transparent;}"
            "QListWidget#spaceFeed::item:hover {background:transparent;}"
        )

    def card_width(self):
        width = max(240, self.viewport().width())
        if self.grid:
            columns = max(1, width // 300)
            return max(240, (width - (columns + 1) * 20) // columns)
        return width

    def set_grid(self, grid):
        self.grid = grid
        self.setViewMode(QListView.ViewMode.IconMode if grid else QListView.ViewMode.ListMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setWrapping(grid)
        self.scheduleDelayedItemsLayout()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.count():
            painter = QPainter(self.viewport())
            painter.setPen(QColor(TOKENS["muted"]))
            painter.drawText(
                self.viewport().rect().adjusted(24, 24, -24, -24),
                Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                self.empty_text,
            )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.scheduleDelayedItemsLayout()

    def mouseReleaseEvent(self, event):
        item = self.itemAt(event.position().toPoint())
        if item and event.button() == Qt.MouseButton.LeftButton:
            entry = item.data(Qt.ItemDataRole.UserRole)
            if self.grid and entry["kind"] == "photo" and local_media(entry["root"], entry.get("path", "")):
                self.mediaClicked.emit(entry, 0)
                event.accept()
                return
            if entry["kind"] != "album":
                rect = self.visualItemRect(item)
                _, height, _, columns, cell, _ = self.itemDelegate().measures(entry, rect.width())
                for i, media in enumerate(media_items(entry)[:9]):
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
