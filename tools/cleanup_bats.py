#!/usr/bin/env python3
"""Utility to clean up old .bat files from test artifacts.
:
- Scans current repo for .bat files older than 365 days and prompts for deletion.
- Default is a dry-run (no deletion) unless you confirm with 'y'.
"""

import time
from pathlib import Path


def is_old(path: Path, days: int = 365) -> bool:
    try:
        mtime = path.stat().st_mtime
        return (time.time() - mtime) > days * 24 * 3600
    except Exception:
        return False


def main():
    root = Path.cwd()
    bat_files = []
    for p in root.rglob("*.bat"):
        if is_old(p, 365):
            bat_files.append(p)
    if not bat_files:
        print("No old .bat files found.")
        return
    print("Old .bat files eligible for removal:")
    for p in bat_files:
        print(f" - {p}")
    answer = input("Delete these files? [y/N]: ")
    if answer.strip().lower() == "y":
        for p in bat_files:
            try:
                p.unlink()
                print(f"Deleted: {p}")
            except Exception as e:
                print(f"Failed to delete {p}: {e}")
    else:
        print("Dry run complete. No files were deleted.")


if __name__ == "__main__":
    main()
