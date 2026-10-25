# Third-party notices

QZoneCapsule's original source is MIT licensed. Dependencies retain their licenses.

- **Qt for Python / PySide6 Essentials / Shiboken:** upstream licensing includes LGPLv3, GPL and commercial options. This preview uses the open-source LGPLv3 option for the dynamically linked runtime. [Licensing](https://doc.qt.io/qtforpython-6/licenses.html) · [PySide source](https://code.qt.io/cgit/pyside/pyside-setup.git/) · [Qt source](https://code.qt.io/cgit/qt/)
- **HTTPX / HTTPCore, Jinja2 / MarkupSafe, Typer, Rich, json-repair**, and their transitive dependencies retain their upstream licenses. Build-time `packaging/collect_notices.py` gathers installed version metadata and available license files into the application.
- **ExifTool** is optional external software, not bundled. [Upstream](https://exiftool.org/)

The packaged Qt libraries are dynamically linked and may be replaced by compatible modified versions. This project imposes no additional restriction on debugging those modifications. The source and build scripts for QZoneCapsule are available in this repository.

Project references (not bundled source): QZoneExport, QzonePhoto and QZAlbumTool. Their names and marks remain those of their owners. No Tencent logos or official affiliation are claimed.
