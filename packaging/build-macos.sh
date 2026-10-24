#!/bin/zsh
set -eu
cd -- "${0:A:h:h}"
.venv/bin/python packaging/collect_notices.py
.venv/bin/python -m PyInstaller --noconfirm --windowed --name 'QZoneCapsule' --icon "$PWD/packaging/QZoneCapsule.icns" \
  --osx-bundle-identifier com.moyu.qzonecapsule \
  --add-data "$PWD/src/qzone_archiver/templates:qzone_archiver/templates" \
  --add-data "$PWD/LICENSE:notices" \
  --add-data "$PWD/packaging/notices:notices" \
  --distpath release/0.2.0 --workpath build/desktop --specpath packaging \
  packaging/desktop_entry.py
