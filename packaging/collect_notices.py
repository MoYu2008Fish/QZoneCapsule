"""Include dependency metadata and upstream license files with the local bundle."""

from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path

out = Path("packaging/notices")
out.mkdir(exist_ok=True)
entries = []
for name in (
    "PySide6_Essentials",
    "shiboken6",
    "httpx",
    "httpcore",
    "certifi",
    "anyio",
    "idna",
    "h11",
    "jinja2",
    "json-repair",
    "markupsafe",
    "typer",
    "click",
    "rich",
    "markdown-it-py",
    "mdurl",
    "pygments",
):
    try:
        d = distribution(name)
    except PackageNotFoundError:
        continue
    entries.append(
        f"## {d.metadata['Name']} {d.version}\n\n{d.metadata.get('License-Expression') or d.metadata.get('License') or 'See upstream project metadata.'}\n"
    )
    for file in d.files or []:
        if (
            any(word in str(file).lower() for word in ("license", "copying", "notice"))
            and d.locate_file(file).is_file()
        ):
            target = out / name / str(file)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(d.locate_file(file).read_bytes())
    (out / f"{name}-METADATA.txt").write_text(d.read_text("METADATA") or "", encoding="utf-8")
(out / "THIRD_PARTY_NOTICES.md").write_text(
    """# Third-party components

QZoneCapsule uses dynamically linked Qt for Python and Qt libraries. The original application's MIT license does not replace their licenses. Qt for Python source: https://code.qt.io/cgit/pyside/pyside-setup.git/ ; Qt source: https://code.qt.io/cgit/qt/ . License information: https://doc.qt.io/qtforpython-6/licenses.html . Users may replace the separately bundled dynamic libraries with compatible modified versions. No additional restriction on debugging such modifications is imposed by this project.

"""
    + "\n".join(entries),
    encoding="utf-8",
)

for license_file in Path("packaging/licenses").glob("*.txt"):
    (out / license_file.name).write_bytes(license_file.read_bytes())
