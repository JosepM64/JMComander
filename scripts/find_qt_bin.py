#!/usr/bin/env python3
import os
import sys

try:
    import PySide6

    base = os.path.dirname(PySide6.__file__)
    candidates = [
        os.path.join(base, "Qt", "bin"),
        os.path.join(base, "Qt6", "bin"),
        os.path.join(base, "Qt", "bin64"),
    ]
    for path in candidates:
        if os.path.isdir(path):
            print(path)
            sys.exit(0)
except Exception:
    pass
print("")
sys.exit(1)
