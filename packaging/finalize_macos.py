"""Set Finder-visible bundle metadata before applying the final local signature."""

import plistlib
import sys
from pathlib import Path

bundle, version = Path(sys.argv[1]), sys.argv[2]
path = bundle / "Contents/Info.plist"
data = plistlib.loads(path.read_bytes())
data.update(
    {
        "CFBundleShortVersionString": version,
        "CFBundleVersion": version,
        "CFBundleDisplayName": "扣扣时光",
        "NSHumanReadableCopyright": "Copyright © 2026 MoYu. MIT License.",
        "NSHighResolutionCapable": True,
    }
)
path.write_bytes(plistlib.dumps(data))
