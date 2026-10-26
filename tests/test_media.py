from threading import Event

import httpx
import pytest
import respx

from qzone_archiver.media import DownloadCancelled, DownloadError, MediaDownloader


@pytest.mark.parametrize(
    "body,content_type",
    [(b"<html>login</html>", "text/html"), (b"", "image/jpeg"), (b'{"error":1}', "application/json")],
)
def test_error_response_not_saved_as_photo(tmp_path, body, content_type):
    dest = tmp_path / "photo.jpg"
    with respx.mock:
        respx.get("https://media.test/photo").mock(
            return_value=httpx.Response(200, content=body, headers={"content-type": content_type})
        )
        with MediaDownloader(tmp_path) as downloader, pytest.raises(DownloadError):
            downloader.download("https://media.test/photo", dest, retries=0)
    assert not dest.exists()
    assert not dest.with_suffix(".jpg.part").exists()


def test_media_cancel_before_network(tmp_path):
    event = Event()
    event.set()
    with MediaDownloader(tmp_path, cancel=event) as downloader, pytest.raises(DownloadCancelled):
        downloader.download("https://media.test/photo", tmp_path / "photo.jpg")


def test_media_preserves_response_format(tmp_path):
    with respx.mock:
        respx.get("https://media.test/photo").mock(
            return_value=httpx.Response(200, content=b"GIF89a", headers={"content-type": "image/gif"})
        )
        with MediaDownloader(tmp_path) as downloader:
            final, size = downloader.download("https://media.test/photo", tmp_path / "photo.jpg")
    assert final.suffix == ".gif"
    assert size == 6


def test_media_failure_explains_status_without_signed_url(tmp_path):
    url = "https://media.test/photo?private_signature=example"
    with respx.mock:
        respx.get(url).mock(return_value=httpx.Response(403))
        with MediaDownloader(tmp_path) as downloader, pytest.raises(DownloadError) as error:
            downloader.download(url, tmp_path / "image.jpg", retries=0)
    assert "403" in error.value.safe_reason
    assert "private_signature" not in str(error.value)


def test_exif_uses_standard_provenance_tag_and_restores_mtime(tmp_path, monkeypatch):
    import subprocess
    from datetime import datetime

    from qzone_archiver import media

    path = tmp_path / "photo.jpg"
    path.write_bytes(b"test")
    calls = []
    monkeypatch.setattr(media, "EXIFTOOL", "/test/exiftool")
    monkeypatch.setattr(media, "_read_exif_datetime", lambda _: "")

    def run(args, **kwargs):
        calls.append(args)
        path.touch()
        return subprocess.CompletedProcess(args, 0)

    monkeypatch.setattr(media.subprocess, "run", run)
    assert media.apply_time(path, "2020-01-02 03:04:05", None, "shoot") == "written"
    assert "-XMP-dc:Relation+=QZoneCapsule:time_source=shoot" in calls[0]
    assert abs(path.stat().st_mtime - datetime(2020, 1, 2, 3, 4, 5).timestamp()) < 1
