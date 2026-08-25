#!/usr/bin/env python3
import os

try:
    import PySide6

    print(os.path.dirname(PySide6.__file__))
except Exception:
    print("")
