import logging
import os
import shutil
from datetime import UTC, datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from src.core.utils import format_size

logger = logging.getLogger(__name__)


class SyncDirsDialog(QDialog):
    sync_completed = Signal()

    def __init__(self, left_path, right_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle(
            f"Sincronitzar: {os.path.basename(left_path)} ↔ {os.path.basename(right_path)}"
        )
        self.setMinimumSize(800, 500)
        self._left_path = left_path
        self._right_path = right_path

        layout = QVBoxLayout(self)

        info_label = QLabel(f"Esquerra: {left_path}\nDreta: {right_path}")
        layout.addWidget(info_label)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Fitxer", "Mida", "Data", "Direcció"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.setAlternatingRowColors(True)
        layout.addWidget(self.tree)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        layout.addWidget(self.progress)

        btn_layout = QHBoxLayout()
        self.scan_btn = QPushButton("Analitzar")
        self.scan_btn.clicked.connect(self._scan)
        btn_layout.addWidget(self.scan_btn)

        self.sync_left_btn = QPushButton("← Copiar a esquerra")
        self.sync_left_btn.clicked.connect(lambda: self._sync("left"))
        self.sync_left_btn.setEnabled(False)
        btn_layout.addWidget(self.sync_left_btn)

        self.sync_right_btn = QPushButton("Copiar a dreta →")
        self.sync_right_btn.clicked.connect(lambda: self._sync("right"))
        self.sync_right_btn.setEnabled(False)
        btn_layout.addWidget(self.sync_right_btn)

        self.close_btn = QPushButton("Tancar")
        self.close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(self.close_btn)

        layout.addLayout(btn_layout)
        self._items_data = []

    def _scan(self):
        self.tree.clear()
        self._items_data = []
        self.progress.setVisible(True)
        self.progress.setValue(0)

        left_files = self._list_files(self._left_path)
        right_files = self._list_files(self._right_path)

        all_names = sorted(set(list(left_files.keys()) + list(right_files.keys())))
        self.progress.setMaximum(len(all_names))

        for i, name in enumerate(all_names):
            left_info = left_files.get(name)
            right_info = right_files.get(name)

            if left_info and not right_info:
                direction = "→ Falta a dreta"
                item = QTreeWidgetItem([name, format_size(left_info[0]), left_info[1], direction])
                item.setForeground(3, Qt.GlobalColor.blue)
            elif right_info and not left_info:
                direction = "← Falta a esquerra"
                item = QTreeWidgetItem([name, format_size(right_info[0]), right_info[1], direction])
                item.setForeground(3, Qt.GlobalColor.red)
            elif left_info and right_info:
                if left_info[0] != right_info[0]:
                    direction = "≠ Mida diferent"
                    item = QTreeWidgetItem(
                        [
                            name,
                            f"L:{format_size(left_info[0])} R:{format_size(right_info[0])}",
                            left_info[1],
                            direction,
                        ]
                    )
                    item.setForeground(3, Qt.GlobalColor.darkYellow)
                else:
                    continue
            else:
                continue

            item.setCheckState(0, Qt.CheckState.Checked)
            self.tree.addTopLevelItem(item)
            self._items_data.append((name, left_info, right_info))
            self.progress.setValue(i + 1)

        self.progress.setVisible(False)
        self.sync_left_btn.setEnabled(True)
        self.sync_right_btn.setEnabled(True)
        count = self.tree.topLevelItemCount()
        QMessageBox.information(self, "Anàlisi completat", f"S'han trobat {count} diferències.")

    def _list_files(self, path):
        files = {}
        try:
            for entry in os.scandir(path):
                if entry.is_file():
                    stat = entry.stat()

                    mtime = datetime.fromtimestamp(stat.st_mtime, tz=UTC).strftime("%Y-%m-%d %H:%M")
                    files[entry.name] = (stat.st_size, mtime, entry.path)
        except Exception as e:
            logger.exception("Error llistant %s: %s", path, e)  # noqa: TRY401
        return files

    def _sync(self, direction):
        dst_base = self._right_path if direction == "right" else self._left_path

        copied = 0
        errors = 0
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item.checkState(0) != Qt.CheckState.Checked:
                continue
            name, left_info, right_info = self._items_data[i]
            if direction == "right" and left_info:
                src = left_info[2]
            elif direction == "left" and right_info:
                src = right_info[2]
            else:
                continue
            dst = os.path.join(dst_base, name)
            try:
                shutil.copy2(src, dst)
                copied += 1
            except Exception as e:
                logger.exception("Error copiant %s → %s: %s", src, dst, e)  # noqa: TRY401
                errors += 1

        msg = f"Copiats {copied} fitxers."
        if errors:
            msg += f" Errors: {errors}"
        QMessageBox.information(self, "Sincronització", msg)
        self.sync_completed.emit()
