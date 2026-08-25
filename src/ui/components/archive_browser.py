import logging
import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QAbstractItemView, QFileIconProvider, QListWidget, QListWidgetItem

logger = logging.getLogger(__name__)

_ARCHIVE_STYLE = """
    QListWidget {
        outline: none;
    }
    QListWidget::item:selected {
        background-color: #4A90E2;
        color: white;
    }
    QListWidget::item:selected:!active {
        background-color: #7FB3E8;
        color: white;
    }
    QListWidget::item:hover {
        background-color: #C8E0F4;
        border: 1px solid #4A90E2;
    }
    QListWidget::item:selected:hover {
        background-color: #5A9FE8;
    }
"""


class ArchiveBrowser(QListWidget):
    item_activated = Signal(str, bool)
    item_clicked = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setStyleSheet(_ARCHIVE_STYLE)
        self.hide()

        icon_provider = QFileIconProvider()
        self.folder_icon = icon_provider.icon(QFileIconProvider.IconType.Folder)
        self.file_icon = icon_provider.icon(QFileIconProvider.IconType.File)

    def populate_from_path(self, path):
        self.clear()
        try:
            for item in os.listdir(path):
                full_path = os.path.join(path, item)
                is_dir = os.path.isdir(full_path)
                lw_item = QListWidgetItem(item)
                lw_item.setData(Qt.ItemDataRole.UserRole, full_path)
                lw_item.setIcon(self.folder_icon if is_dir else self.file_icon)
                self.addItem(lw_item)
        except Exception as e:
            logger.exception("Error populating archive browser: %s", e)  # noqa: TRY401

    def populate_shell_items(self, items):
        self.clear()
        for item in items:
            lw_item = QListWidgetItem(item["name"])
            lw_item.setData(Qt.ItemDataRole.UserRole, item["path"])
            lw_item.setData(Qt.ItemDataRole.DisplayRole + 1, item["is_dir"])
            lw_item.setIcon(self.folder_icon if item["is_dir"] else self.file_icon)
            self.addItem(lw_item)

    def get_selected_paths(self):
        return [item.data(Qt.ItemDataRole.UserRole) for item in self.selectedItems()]

    def select_item_by_path(self, path):
        for i in range(self.count()):
            item = self.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == path:
                self.setCurrentItem(item)
                self.setFocus()
                return True
        return False

    def select_item_by_name(self, name):
        for i in range(self.count()):
            item = self.item(i)
            if item.text() == name:
                self.setCurrentItem(item)
                self.scrollToItem(item)
                self.setFocus()
                return True
        return False

    def invert_selection(self):
        for i in range(self.count()):
            item = self.item(i)
            item.setSelected(not item.isSelected())

    def get_visible_items_text(self):
        return [self.item(i).text() for i in range(self.count())]

    def filter_items(self, pattern_lower):
        for i in range(self.count()):
            item = self.item(i)
            item.setHidden(pattern_lower not in item.text().lower())
