"""Browser de fitxers per a dispositius MTP (iPhone) amb columnes ordenables."""

import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QAbstractItemView, QStyledItemDelegate, QTreeWidget, QTreeWidgetItem

logger = logging.getLogger(__name__)

_SHELL_STYLE = """
    QTreeWidget {
        outline: none;
        border: none;
    }
    QTreeWidget::item:selected {
        background-color: #4A90E2;
        color: white;
    }
    QTreeWidget::item:selected:!active {
        background-color: #7FB3E8;
        color: white;
    }
    QTreeWidget::item:hover {
        background-color: #C8E0F4;
        border: 1px solid #4A90E2;
    }
    QTreeWidget::item:selected:hover {
        background-color: #5A9FE8;
    }
"""


def _format_size(size):
    if size <= 0:
        return ""
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return ""


class _SizeSortDelegate(QStyledItemDelegate):
    """Mostra la mida formatada (MB/KB) però ordena pel valor numèric de DisplayRole."""

    def displayText(self, value, locale):  # noqa: N802, ARG002
        return _format_size(int(value)) if isinstance(value, (int, float)) else str(value)


class ShellBrowser(QTreeWidget):
    item_activated = Signal(str, bool)
    item_clicked = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        self.setStyleSheet(_SHELL_STYLE)
        self.setRootIsDecorated(False)
        self.setUniformRowHeights(True)
        self.setSortingEnabled(True)
        self.setAllColumnsShowFocus(True)
        self.setColumnCount(3)
        self.setHeaderLabels(["Nom", "Mida", "Data de modificació"])
        self.header().setSortIndicator(0, Qt.SortOrder.AscendingOrder)
        self.header().setStretchLastSection(True)
        self.header().setSortIndicatorShown(True)
        # Ordenació numèrica per a la columna de mida (per DisplayRole)
        self.setItemDelegateForColumn(1, _SizeSortDelegate(self))
        self.hide()

    def populate_shell_items(self, items):
        self.setSortingEnabled(False)
        self.clear()
        for item in items:
            lw_item = QTreeWidgetItem([item["name"]])
            lw_item.setData(0, Qt.ItemDataRole.UserRole, item["path"])
            lw_item.setData(0, Qt.ItemDataRole.DisplayRole + 1, item["is_dir"])
            # Mida a la columna 1: DisplayRole = bytes (numèric), es mostra amb delegate
            lw_item.setData(1, Qt.ItemDataRole.DisplayRole, int(item.get("size", 0)))
            lw_item.setData(1, Qt.ItemDataRole.UserRole, int(item.get("size", 0)))
            # Data a la columna 2 (ordenable textualment)
            mtime = item.get("mtime") or ""
            lw_item.setText(2, str(mtime))
            lw_item.setData(2, Qt.ItemDataRole.UserRole, str(mtime))
            self.addTopLevelItem(lw_item)
        self.setSortingEnabled(True)
        self.sortByColumn(0, Qt.SortOrder.AscendingOrder)

    def get_selected_paths(self):
        return [item.data(0, Qt.ItemDataRole.UserRole) for item in self.selectedItems()]

    def select_item_by_name(self, name):
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            if item.text(0) == name:
                self.setCurrentItem(item)
                self.scrollToItem(item)
                self.setFocus()
                return True
        return False

    def select_item_by_path(self, path):
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            if item.data(0, Qt.ItemDataRole.UserRole) == path:
                self.setCurrentItem(item)
                self.setFocus()
                return True
        return False

    def invert_selection(self):
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            item.setSelected(not item.isSelected())

    def get_visible_items_text(self):
        return [self.topLevelItem(i).text(0) for i in range(self.topLevelItemCount())]

    def filter_items(self, pattern_lower):
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            item.setHidden(pattern_lower not in item.text(0).lower())
