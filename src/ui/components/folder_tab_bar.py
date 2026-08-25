import logging
import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QTabBar

logger = logging.getLogger(__name__)


class FolderTabBar(QTabBar):
    tab_path_changed = Signal(int, str)
    tab_close_requested = Signal(int)
    new_tab_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTabsClosable(True)
        self.setMovable(True)
        self.setExpanding(False)
        self.setElideMode(Qt.TextElideMode.ElideRight)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tabCloseRequested.connect(self._on_tab_close)
        self.currentChanged.connect(self._on_current_changed)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def add_tab(self, path, select=True):
        label = self._path_label(path)
        idx = self.addTab(label)
        self.setTabData(idx, path)
        if select:
            self.setCurrentIndex(idx)
        return idx

    def update_tab(self, index, path):
        if 0 <= index < self.count():
            self.setTabData(index, path)
            self.setTabText(index, self._path_label(path))

    def get_tab_path(self, index):
        if 0 <= index < self.count():
            return self.tabData(index)
        return None

    def current_path(self):
        return self.get_tab_path(self.currentIndex())

    def _path_label(self, path):
        if not path:
            return ""
        name = os.path.basename(path.rstrip(os.sep))
        drive = os.path.splitdrive(path)[0]
        if not name and drive:
            return drive + os.sep
        if not name:
            return path
        return name

    def _on_current_changed(self, index):
        path = self.get_tab_path(index)
        if path is not None:
            self.tab_path_changed.emit(index, path)

    def _on_tab_close(self, index):
        if self.count() <= 1:
            return
        self.tab_close_requested.emit(index)

    def _show_context_menu(self, pos):
        idx = self.tabAt(pos)
        if idx < 0:
            return
        menu = QMenu(self)
        close_act = QAction("Tancar pestanya", self)
        close_act.triggered.connect(lambda: self._on_tab_close(idx))
        menu.addAction(close_act)

        new_act = QAction("Nova pestanya", self)
        new_act.triggered.connect(self.new_tab_requested.emit)
        menu.addAction(new_act)

        menu.exec(self.mapToGlobal(pos))
