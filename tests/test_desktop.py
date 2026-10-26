import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest

pytest.importorskip("PySide6")
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from qzone_archiver import desktop
from qzone_archiver.sync import SyncReport


@pytest.fixture
def window(monkeypatch, tmp_path):
    from PySide6.QtCore import QSettings

    from qzone_archiver import library_ui

    monkeypatch.setattr(
        library_ui,
        "QSettings",
        lambda *_: QSettings(str(tmp_path / "library.ini"), QSettings.Format.IniFormat),
    )
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setattr(desktop, "load_session", lambda: None)
    app = QApplication.instance() or QApplication([])
    win = desktop.Window()
    win.library.roots = []
    win.path.setText(str(tmp_path / "backup"))
    yield win, app
    win.close()
    win.deleteLater()
    app.processEvents()


def finish(win, app):
    deadline = time.monotonic() + 5
    while win.job is not None and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.005)
    assert win.job is None


def test_logged_out_and_invalid_selection(window):
    win, _ = window
    assert not win.start_button.isEnabled()
    win.session = {"uin": "123", "cookie": "test"}
    win.update_controls()
    assert win.start_button.isEnabled()
    win.albums.setChecked(False)
    win.moods.setChecked(False)
    win.start_sync()
    assert "至少" in win.status.text()
    assert win.job is None


def test_background_login_album_selection_and_export(window, monkeypatch, tmp_path):
    win, app = window
    monkeypatch.setattr(
        desktop, "login_with_qrcode", lambda **_: {"uin": "123", "cookie": "p_skey=test; p_uin=o123"}
    )
    win.login_button.click()
    finish(win, app)
    assert win.session["uin"] == "123"
    assert win.start_button.isEnabled()
    monkeypatch.setattr(
        desktop,
        "fetch_albums",
        lambda *_: iter([{"id": "a", "name": "旅行", "total": 10}, {"id": "b", "name": "日常", "total": 20}]),
    )
    win.load_button.click()
    finish(win, app)
    assert win.tree.topLevelItemCount() == 2
    assert not win.all_albums.isChecked()
    win.tree.topLevelItem(1).setCheckState(0, Qt.CheckState.Unchecked)
    captured = []
    index = tmp_path / "index.html"
    index.write_text("test")

    def export(session, options, emit, cancel):
        captured.append(options)
        emit(
            "正在读取说说", {"albums": 1, "photos": 2, "moods": 3, "downloaded": 2, "skipped": 0, "failed": 0}
        )
        return SyncReport(index=str(index))

    monkeypatch.setattr(desktop, "run_sync", export)
    win.start_button.click()
    finish(win, app)
    assert captured[0].album_ids == {"a"}
    assert captured[0].out.name == "123"
    assert win.open_button.isEnabled()
    assert "导出完成" in win.status.text()
    win.forget_button.click()
    assert win.session is None
    assert not desktop.session_path().exists()


def test_job_errors_are_sanitized(window, monkeypatch):
    win, app = window

    def fail(**_):
        raise RuntimeError("secret cookie")

    monkeypatch.setattr(desktop, "login_with_qrcode", fail)
    win.login()
    finish(win, app)
    assert "secret" not in win.log.toPlainText()
    assert win.login_button.isEnabled()


def test_close_cancels_and_waits_for_background_job(window, monkeypatch):
    win, app = window

    def login(**kwargs):
        kwargs["cancel"].wait(3)
        raise RuntimeError("cancelled")

    monkeypatch.setattr(desktop, "login_with_qrcode", login)
    win.show()
    win.login()
    win.close()
    assert win.close_requested
    finish(win, app)
    assert not win.isVisible()


def test_qr_is_displayed_in_dialog(window):
    from PySide6.QtCore import QBuffer, QByteArray, QIODevice
    from PySide6.QtGui import QImage

    win, app = window
    image = QImage(64, 64, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.white)
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    win.show_qr(bytes(data))
    app.processEvents()
    assert win.qr_dialog.isVisible()
    win.qr_dialog.reject()


def test_in_app_library_account_filter_album_and_local_image(window, tmp_path):
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QImage, QTextDocument

    from qzone_archiver.store import Store

    win, app = window
    for uin in ("123", "456"):
        root = tmp_path / "archives" / uin
        with Store(root / "qzone.db") as store:
            store.upsert_account(uin)
            store.upsert_album(uin, {"id": "a", "name": "同名相册"})
            store.upsert_photo(uin, "a", {"sloc": "p", "name": "同名照片"})
            store.upsert_mood(uin, {"tid": "m", "content": f"{uin}的说说"})
            image = QImage(80, 60, QImage.Format.Format_RGB32)
            image.fill(Qt.GlobalColor.green)
            image.save(str(root / "image.png"))
            store.set_photo_file(uin, "a", "p", "image.png", 100, "mtime-only")
    win.library.add_root(tmp_path / "archives", refresh=False)
    win.open_archive()
    deadline = time.monotonic() + 5
    while win.library.loader and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.005)
    assert win.pages.currentWidget() is win.library
    library = win.library
    assert library.list.count() == library.feed.count() == 6  # albums are timeline events too
    library.account.setCurrentIndex(library.account.findData("456"))
    assert library.list.count() == 3
    assert all(e["uin"] == "456" for e in library.filtered)
    library.kind.setCurrentIndex(library.kind.findData("album"))
    assert library.list.count() == 1
    library.enter_album(library.list.item(0))
    assert library.list.count() == 1
    assert library.filtered[0]["kind"] == "photo"
    assert "QQ 456" in library.detail.toPlainText()
    assert len(library.images) == 1
    resource = library.detail.document().resource(
        QTextDocument.ResourceType.ImageResource, QUrl("archive-image:0")
    )
    assert isinstance(resource, QImage) and not resource.isNull()
    library.search.setText("不存在")
    assert library.list.count() == 0


def test_export_mode_targets_shared_archive(window, monkeypatch, tmp_path):
    win, app = window
    win.session = {"uin": "123", "cookie": "test"}
    win.update_controls()
    win.export_mode.setCurrentIndex(1)
    captured = []

    def export(_session, options, *_):
        captured.append(options)
        index = options.out / "index.html"
        index.parent.mkdir(parents=True)
        index.write_text("test")
        return SyncReport(index=str(index))

    monkeypatch.setattr(desktop, "run_sync", export)
    win.start_sync()
    finish(win, app)
    assert captured[0].merge_accounts
    assert captured[0].out.name == "合并存档"


def test_all_timeline_entries_and_account_year_filters(window, tmp_path, monkeypatch):
    win, app = window
    library = win.library
    entries = []
    for uin, year in (("123", "2021"), ("456", "2024")):
        for i in range(135):
            entries.append(
                {
                    "kind": "mood",
                    "uin": uin,
                    "owner": f"演示账号 {uin}",
                    "root": tmp_path,
                    "tid": str(i),
                    "key": (uin, "mood", str(i)),
                    "time": f"{year}-01-01 12:00:00",
                    "content": f"回忆 {i}[em]e100[/em]",
                    "media": [],
                }
            )
    library.on_loaded(entries, [])
    assert library.feed.count() == library.list.count() == 270
    assert not library.more.isVisible()
    assert "270 条" in library.summary.text()
    library.account.setCurrentIndex(library.account.findData("123"))
    assert library.feed.count() == 135
    library.account.setCurrentIndex(0)
    assert library.feed.count() == 270
    library.year.setCurrentIndex(library.year.findData("2021"))
    assert library.feed.count() == 135
    library.show_all()
    assert library.feed.count() == 270 and library.year.currentData() == ""
    library.search.setText("🙂")
    assert library.feed.count() == 270
    library.search.clear()
    monkeypatch.setattr(library, "refresh", lambda: None)
    win.show()
    win.pages.setCurrentIndex(1)
    app.processEvents()
    # Exercise actual delegate painting and scroll to the final item.
    library.feed.scrollToBottom()
    app.processEvents()
    assert not library.feed.grab().isNull()
    assert library.feed.visualItemRect(library.feed.item(269)).intersects(library.feed.viewport().rect())


def test_feed_detail_dialog_keeps_local_images_and_emoji(window, tmp_path, monkeypatch):
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QImage, QTextDocument

    from qzone_archiver import library_ui

    win, _ = window
    image = QImage(40, 40, QImage.Format.Format_RGB32)
    image.fill(Qt.GlobalColor.blue)
    image.save(str(tmp_path / "image.png"))
    entry = {
        "kind": "mood",
        "uin": "123",
        "owner": "演示账号",
        "root": tmp_path,
        "time": "2021-01-01",
        "content": "你好[em]e100[/em]",
        "tid": "m",
        "media": [{"path": "image.png"}],
    }
    win.library.on_loaded([entry], [])
    checked = []

    def inspect(dialog):
        browser = dialog.findChild(library_ui.LocalBrowser)
        assert "你好🙂" in browser.toPlainText()
        resource = browser.document().resource(
            QTextDocument.ResourceType.ImageResource, QUrl("archive-image:0")
        )
        assert isinstance(resource, QImage) and not resource.isNull()
        checked.append(True)
        return 0

    monkeypatch.setattr(library_ui.QDialog, "exec", inspect)
    win.library.open_feed_entry(win.library.feed.item(0))
    assert checked


def test_narrow_library_controls_remain_inside_window(window):
    win, app = window
    win.resize(680, 850)
    win.show()
    win.pages.setCurrentIndex(1)
    app.processEvents()
    library = win.library
    for control in (
        library.account,
        library.kind,
        library.year,
        library.mode,
        library.search,
        library.report_button,
        library.all_button,
    ):
        rect = control.rect()
        assert win.rect().contains(control.mapTo(win, rect.topLeft()))
        assert win.rect().contains(control.mapTo(win, rect.bottomRight()))
    assert win.width() == 680


def test_photo_viewer_navigation_and_resize_with_synthetic_images(window, tmp_path, monkeypatch):
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QColor, QImage
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QLabel

    from qzone_archiver import library_ui

    win, app = window
    library = win.library
    for name, color in (("demo-blue.png", "#2479bd"), ("demo-white.png", "#ffffff")):
        image = QImage(600, 400, QImage.Format.Format_RGB32)
        image.fill(QColor(color))
        image.save(str(tmp_path / name))
        library.images.append(tmp_path / name)
    checked = []

    def inspect(dialog):
        dialog.show()
        app.processEvents()
        picture = next(label for label in dialog.findChildren(QLabel) if not label.pixmap().isNull())
        before = picture.pixmap().size()
        QTest.keyClick(dialog, Qt.Key.Key_Right)
        assert picture.pixmap().toImage().pixelColor(0, 0) == QColor("#ffffff")
        QTest.keyClick(dialog, Qt.Key.Key_Left)
        assert picture.pixmap().toImage().pixelColor(0, 0) == QColor("#2479bd")
        dialog.resize(640, 480)
        app.processEvents()
        assert picture.pixmap().height() < before.height()
        checked.append(True)
        dialog.close()
        return 0

    monkeypatch.setattr(library_ui.PhotoDialog, "exec", inspect)
    library.preview(QUrl("preview:0"))
    assert checked


def test_dashboard_navigation_survives_narrow_window_and_library_return(window, monkeypatch):
    win, app = window
    monkeypatch.setattr(win.library, "refresh", lambda: None)
    win.show()
    win.resize(1500, 980)
    app.processEvents()
    assert win.sidebar.isVisible()
    assert not win.compact_nav.isVisible()
    win.navigate("logs")
    app.processEvents()
    assert win.log.isVisible()
    assert win.compact_nav.currentData() == "logs"
    win.resize(680, 850)
    app.processEvents()
    assert not win.sidebar.isVisible()
    assert win.compact_nav.isVisible()
    win.compact_nav.activated.emit(win.compact_nav.findData("library"))
    assert win.pages.currentIndex() == 1
    win.compact_nav.activated.emit(win.compact_nav.findData("overview"))
    app.processEvents()
    assert win.pages.currentIndex() == 0
    assert win.export_scroll.verticalScrollBar().value() == 0
    assert win.dashboard.grid.columnCount() >= 1
    for control in (win.moods, win.albums, win.path, win.start_button, win.open_button):
        assert control.width() > 0
        assert control.mapTo(win.dashboard, control.rect().bottomRight()).x() < win.dashboard.width()


def test_dashboard_statistics_follow_loaded_local_records(window):
    win, _ = window
    entries = [
        {"kind": "mood", "time": "2026-10-26", "uin": "123"},
        {"kind": "photo", "time": "2025-02-02", "uin": "123"},
        {"kind": "album", "time": "2025-01-01", "uin": "123"},
    ]
    win.library.entries = entries
    win.update_dashboard()
    assert win.content_chart.entries == entries
    assert [e["kind"] for e in win.timeline_chart.entries] == ["mood", "photo"]
    win.library.entries = []
    win.update_dashboard()
    assert win.content_chart.entries == win.timeline_chart.entries == []


def test_sidebar_click_returns_from_library_to_overview(window, monkeypatch):
    from PySide6.QtTest import QTest

    win, app = window
    monkeypatch.setattr(win.library, "refresh", lambda: None)
    win.show()
    app.processEvents()
    library_button = next(item for item in win.nav_buttons if item.property("destination") == "library")
    overview_button = win.nav_buttons[0]
    QTest.mouseClick(library_button, Qt.MouseButton.LeftButton)
    app.processEvents()
    assert win.pages.currentIndex() == 1
    QTest.mouseClick(overview_button, Qt.MouseButton.LeftButton)
    app.processEvents()
    assert win.pages.currentIndex() == 0
    assert overview_button.isChecked()
    assert not library_button.isChecked()
    # macOS accessibility may toggle a checkable button without emitting clicked.
    library_button.setChecked(True)
    app.processEvents()
    assert win.pages.currentIndex() == 1
    overview_button.setChecked(True)
    app.processEvents()
    assert win.pages.currentIndex() == 0
