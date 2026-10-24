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
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setattr(desktop, "load_session", lambda: None)
    app = QApplication.instance() or QApplication([])
    win = desktop.Window()
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
