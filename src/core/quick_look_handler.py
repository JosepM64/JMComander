import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap


class QuickLookHandler:
    IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg"}  # noqa: RUF012
    TEXT_EXT = {".txt", ".md", ".log", ".ini", ".json", ".py", ".xml", ".yml", ".yaml", ".csv"}  # noqa: RUF012

    @staticmethod
    def can_preview(path):
        if not path or not os.path.isfile(path):
            return False
        _, ext = os.path.splitext(path)
        return ext.lower() in QuickLookHandler.IMAGE_EXT | QuickLookHandler.TEXT_EXT

    @staticmethod
    def preview(path, label):
        _, ext = os.path.splitext(path)
        ext = ext.lower()

        if ext in QuickLookHandler.IMAGE_EXT:
            pixmap = QPixmap(path)
            if pixmap.width() > 800 or pixmap.height() > 800:
                pixmap = pixmap.scaled(800, 800, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            label.setPixmap(pixmap)
            label.setText("")
        else:
            try:
                with open(path, encoding="utf-8", errors="ignore") as f:
                    text = f.read(2000000)
                label.setPixmap(QPixmap())
                label.setText(text)
            except Exception:  # noqa: BLE001
                label.setText("[Error llegint el fitxer]")
