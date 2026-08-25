from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QDockWidget, QLabel, QScrollArea, QVBoxLayout, QWidget

from src.core.quick_look_handler import QuickLookHandler


class QuickLook(QDockWidget):
    def __init__(self, parent=None):
        super().__init__("Quick Look  (F3)", parent)
        self.setObjectName("QuickLookDock")
        self.setAllowedAreas(Qt.RightDockWidgetArea | Qt.BottomDockWidgetArea)
        self.setFeatures(QDockWidget.DockWidgetClosable)

        self.label = QLabel()
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setWordWrap(True)
        self.label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.label.setMinimumSize(200, 100)

        scroll = QScrollArea()
        scroll.setWidget(self.label)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        central = QWidget()
        lay = QVBoxLayout(central)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.addWidget(scroll)
        self.setWidget(central)

        self.clear()

    def clear(self):
        self.label.setPixmap(QPixmap())
        self.label.setText("<i>Selecciona un fitxer compatible (F3 per activar)</i>")

    def update_preview(self, file_path):
        if not file_path or not QuickLookHandler.can_preview(file_path):
            self.clear()
            return
        QuickLookHandler.preview(file_path, self.label)
