#!/bin/zsh
set -eu
cd -- "${0:A:h:h}"
APP_VERSION=$(.venv/bin/python -c 'from qzone_archiver import __version__; print(__version__)')
RELEASE_DIR="$PWD/release/$APP_VERSION"
.venv/bin/python packaging/build_icon.py
.venv/bin/python packaging/collect_notices.py
.venv/bin/python -m PyInstaller --noconfirm --windowed --name 'QZoneCapsule' --icon "$PWD/packaging/QZoneCapsule.icns" \
  --osx-bundle-identifier com.moyu.qzonecapsule \
  --add-data "$PWD/src/qzone_archiver/templates:qzone_archiver/templates" \
  --add-data "$PWD/src/qzone_archiver/assets:qzone_archiver/assets" \
  --add-data "$PWD/LICENSE:notices" \
  --add-data "$PWD/packaging/notices:notices" \
  --distpath "$RELEASE_DIR" --workpath build/desktop --specpath packaging \
  packaging/desktop_entry.py
.venv/bin/python packaging/finalize_macos.py "$RELEASE_DIR/QZoneCapsule.app" "$APP_VERSION"
codesign --force --deep --sign - "$RELEASE_DIR/QZoneCapsule.app"
codesign --verify --deep --strict "$RELEASE_DIR/QZoneCapsule.app"
ditto -c -k --sequesterRsrc --keepParent "$RELEASE_DIR/QZoneCapsule.app" "$RELEASE_DIR/QZoneCapsule-$APP_VERSION-macos-arm64.zip"
(cd "$RELEASE_DIR" && shasum -a 256 "QZoneCapsule-$APP_VERSION-macos-arm64.zip" > SHA256SUMS)
