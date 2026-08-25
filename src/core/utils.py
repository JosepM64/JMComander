"""
Utilitats compartides del core.
Funcions utilitzades per múltiples mòduls sense dependències de Qt.
"""

import re

_WINDOWS_SPECIAL_FILES = frozenset(
    {
        "nul",
        "con",
        "prn",
        "aux",
        "com1",
        "com2",
        "com3",
        "com4",
        "com5",
        "com6",
        "com7",
        "com8",
        "com9",
        "lpt1",
        "lpt2",
        "lpt3",
        "lpt4",
        "lpt5",
        "lpt6",
        "lpt7",
        "lpt8",
        "lpt9",
    }
)


def format_size(size: float, decimal_places: int = 1) -> str:
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024.0:
            return f"{size:.{decimal_places}f} {unit}"
        size /= 1024.0
    return f"{size:.{decimal_places}f} PB"


def is_windows_special_file(filepath: str) -> bool:
    filename = filepath.rsplit("\\", 1)[-1].rsplit("/", 1)[-1].lower()
    name_without_ext = filename.split(".")[0] if "." in filename else filename
    return name_without_ext in _WINDOWS_SPECIAL_FILES


def natural_sort_key(text: str):
    return [int(c) if c.isdigit() else c.lower() for c in re.split(r"(\d+)", str(text))]
