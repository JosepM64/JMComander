import logging
import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFileIconProvider,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

logger = logging.getLogger(__name__)


class DirectoryHotlistDialog(QDialog):
    directory_selected = Signal(str)

    def __init__(self, current_path="", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Directoris freqüents")
        self.setMinimumSize(350, 400)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.Popup)
        self._current_path = current_path

        layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget)

        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Afegir actual")
        self.add_btn.clicked.connect(self._add_current)
        self.remove_btn = QPushButton("Eliminar")
        self.remove_btn.clicked.connect(self._remove_selected)
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.remove_btn)
        layout.addLayout(btn_layout)

        self._icon_provider = QFileIconProvider()
        self._folder_icon = self._icon_provider.icon(QFileIconProvider.IconType.Folder)
        self._load_items()

    def _get_default_paths(self):
        home = os.path.expanduser("~")
        return [
            ("Escriptori", os.path.join(home, "Desktop")),
            ("Documents", os.path.join(home, "Documents")),
            ("Descàrregues", os.path.join(home, "Downloads")),
            ("Imatges", os.path.join(home, "Pictures")),
            ("Música", os.path.join(home, "Music")),
            ("Vídeos", os.path.join(home, "Videos")),
            ("Arrel", "C:\\"),
            ("Usuari", home),
        ]

    def _load_items(self):
        self.list_widget.clear()
        for label, path in self._get_default_paths():
            if os.path.exists(path):
                item = QListWidgetItem(f"{label}  —  {path}")
                item.setData(Qt.ItemDataRole.UserRole, path)
                item.setIcon(self._folder_icon)
                self.list_widget.addItem(item)

    def _on_item_double_clicked(self, item):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and os.path.isdir(path):
            self.directory_selected.emit(path)
            self.accept()

    def _on_item_clicked(self, _item):
        if self.list_widget.selectedItems():
            self.remove_btn.setEnabled(True)
        else:
            self.remove_btn.setEnabled(False)

    def _add_current(self):
        if self._current_path and os.path.isdir(self._current_path):
            name = os.path.basename(self._current_path.rstrip(os.sep))
            if not name:
                name = self._current_path
            item = QListWidgetItem(f"{name}  —  {self._current_path}")
            item.setData(Qt.ItemDataRole.UserRole, self._current_path)
            item.setIcon(self._folder_icon)
            self.list_widget.addItem(item)
            self.list_widget.scrollToBottom()

    def _remove_selected(self):
        selected = self.list_widget.selectedItems()
        if selected:
            row = self.list_widget.row(selected[0])
            self.list_widget.takeItem(row)
