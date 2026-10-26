# QZoneCapsule · 扣扣时光

**A local time capsule for your QQ Zone posts and albums.**

[简体中文](README.md) · [Downloads](https://github.com/MoYu2008Fish/QZoneCapsule/releases) · [Issues](https://github.com/MoYu2008Fish/QZoneCapsule/issues)

A Python / PySide6 desktop archive tool: scan a QQ login code, select posts and albums, export to your computer, and browse the archive offline.

> **0.5.0 preview:** the macOS application, live QR-code retrieval, and login cancellation have been checked. Local album metadata export has also been checked. Full media download and mood completeness still need acceptance testing. Test a small album first.

![Desktop interface in Chinese](docs/images/desktop.png)

Version 0.5.0 refreshes the dashboard layout, blue/purple palette, app icon and narrow-window navigation. [Privacy audit](docs/privacy-audit-0.5.0.md) (Chinese).

## Features

- Archive post text, timestamps, locations and images together with album metadata and photos.
- Select all albums or individual albums; export posts and albums independently.
- Try original photo URLs first, fall back to other candidates, and record the actual quality source.
- Preserve available timestamps; optionally fill missing EXIF dates using external ExifTool.
- Run jobs in the background, stop safely between requests, and retry missing files by exporting again.
- Keep SQLite records, an offline HTML viewer, and a `last-run.json` result report.
- Browse exported posts, albums and local photos inside the app, with search, account filters and image preview. No login is needed for local browsing.
- Export into separate account folders or a shared archive. View accounts separately or combine their timelines while retaining ownership and keeping account identities distinct.

The desktop interface is currently in Chinese.

## Install

For Apple Silicon Macs, download `QZoneCapsule-0.5.0-macos-arm64.zip` from [Releases](https://github.com/MoYu2008Fish/QZoneCapsule/releases), extract it and open `QZoneCapsule.app`. The app is locally ad-hoc signed, without Apple Developer ID signing or notarization. Other platforms do not yet have verified binary packages.

From source (Python 3.10+ and a system supported by PySide6):

```bash
git clone https://github.com/MoYu2008Fish/QZoneCapsule.git
cd QZoneCapsule
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[desktop]'
qzonecapsule
```

On Windows, activate with `.venv\Scripts\activate`. Windows/Linux compatibility still needs device testing.

## Use

1. Click the QR login button and confirm in the QQ mobile app.
2. Select posts, albums and image downloads; optionally load and select individual albums.
3. Choose a destination and export mode: separate account folders, or a shared archive in `合并存档`. Log in to another account and use the same destination/mode to add it to the shared archive.
4. Open the offline archive. Check `last-run.json` for incomplete items; exporting again retries missing files.

Session data is kept locally at `~/.config/qzone-archiver/session.json`, retaining the prototype's directory for compatibility. Desktop QR images remain in memory. Logging out removes the saved session.

CLI access is also available:

```bash
qzonecapsule-cli login --qrcode
qzonecapsule-cli sync --out ./backup
qzonecapsule-cli sync --out ./backup --no-moods --limit 1
```

Unlike the desktop app, CLI output directories are used directly. Use a separate directory per account.

## Limits and privacy

Videos currently retain album metadata only; video source downloads, full comment/reply archiving, byte-level resume, and independent failed-job retries are not implemented. Existing nonempty files are reused without full hash verification. ExifTool is optional and not bundled. Private web APIs may change at any time; inaccessible, deleted or original-quality content is not guaranteed.

Requests go directly to Tencent services and media URLs returned by those services. There is no project-hosted proxy, cloud upload or telemetry. Cookies are used for the required Tencent login/content requests. Stored raw responses, media URLs and archives may contain private data. Do not include cookies, QR images, signed URLs or personal archives in issues.

This is an independent project, not affiliated with or endorsed by Tencent, QQ or QQ Zone. Only archive content you are authorized to access.

## Development

```bash
python -m pip install -e '.[desktop,dev]'
ruff check .
TZ=Asia/Shanghai pytest -q
```

Automated checks use simulated responses and temporary fixtures. See [validation notes](docs/desktop-validation.md) for their limits, and [contribution guidance](CONTRIBUTING.md) for reporting bugs. Build the macOS app with `packaging/build-macos.sh` after installing PyInstaller.

Original project code: [MIT](LICENSE). Dependencies retain their own licenses; see [third-party notices](THIRD_PARTY_NOTICES.md).

References: [QZoneExport](https://github.com/ShunCai/QZoneExport), [QzonePhoto](https://github.com/11273/QzonePhoto), and [QZAlbumTool](https://github.com/kahotv/QZAlbumTool). Public feature descriptions informed the design; their source code was not copied.
