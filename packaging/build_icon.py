"""Render the editable iOS-style icon source into PNG and macOS ICNS assets."""

import os
import subprocess
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

root = Path(__file__).resolve().parents[1]
app = QApplication.instance() or QApplication([])
source = root / "docs/images/icon.svg"
renderer = QSvgRenderer(str(source))
iconset = root / "packaging/QZoneCapsule.iconset"
iconset.mkdir(exist_ok=True)
for size in (16, 32, 128, 256, 512):
    for scale in (1, 2):
        pixels = size * scale
        image = QImage(pixels, pixels, QImage.Format.Format_ARGB32_Premultiplied)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        renderer.render(painter)
        painter.end()
        image.save(str(iconset / f"icon_{size}x{size}{'@2x' if scale == 2 else ''}.png"))
        if pixels == 1024:
            image.save(str(root / "src/qzone_archiver/assets/app-icon.png"))
            image.save(str(root / "docs/images/app-icon.png"))
subprocess.run(
    ["iconutil", "-c", "icns", str(iconset), "-o", str(root / "packaging/QZoneCapsule.icns")], check=True
)
