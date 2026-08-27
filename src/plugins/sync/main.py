"""
Sincronitzar - Plugin per sincronitzar el contingut de dues carpetes.
"""

import enum
import fnmatch
import hashlib
import os
import shutil

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressDialog,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class SyncState(enum.Enum):
    IDENTICAL = "=="
    COPY_TO_RIGHT = "=>"
    COPY_TO_LEFT = "<="
    CONFLICT = "!?"
    DELETE_FROM_LEFT = "X←"
    DELETE_FROM_RIGHT = "→X"


STATE_COLORS = {
    SyncState.IDENTICAL: (QColor(0, 0, 0), QColor(255, 255, 255)),
    SyncState.COPY_TO_RIGHT: (QColor(0, 128, 0), QColor(220, 255, 220)),
    SyncState.COPY_TO_LEFT: (QColor(0, 128, 0), QColor(220, 255, 220)),
    SyncState.CONFLICT: (QColor(180, 0, 0), QColor(255, 220, 220)),
    SyncState.DELETE_FROM_LEFT: (QColor(180, 0, 0), QColor(255, 220, 220)),
    SyncState.DELETE_FROM_RIGHT: (QColor(180, 0, 0), QColor(255, 220, 220)),
}


def register(api):
    pass


def run_sync(api):
    dialog = SyncDialog(api)
    dialog.exec()


class CompareWorker(QThread):
    finished = Signal(dict)
    error = Signal(str)
    progress = Signal(str)

    def __init__(self, left, right, compare_mode, recursive, include, exclude, tolerance=0):
        super().__init__()
        self.left = left
        self.right = right
        self.compare_mode = compare_mode
        self.recursive = recursive
        self.include = include
        self.exclude = exclude
        self.tolerance = tolerance

    def run(self):
        try:
            self.progress.emit("Escanejant...")
            result = compare_dirs(
                self.left,
                self.right,
                self.compare_mode,
                self.recursive,
                self.include,
                self.exclude,
                self.tolerance,
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class SyncWorker(QThread):
    progress = Signal(int, int, str)
    file_action = Signal(str, str, str)
    finished = Signal()
    error = Signal(str)

    def __init__(self, actions, parent=None):
        super().__init__(parent)
        self.actions = actions
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        total = len(self.actions)
        for i, (action, src, dst) in enumerate(self.actions):
            if self._cancelled:
                return
            basename = os.path.basename(src) if src else "(desconegut)"
            if action == "copy":
                self.file_action.emit("copy", src, dst)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                try:
                    st = os.stat(src)
                    _copy_file(src, dst)
                    os.utime(dst, (st.st_atime, st.st_mtime))
                except Exception as e:
                    self.error.emit(f"Error copiant {basename}: {e}")
                    return
            elif action == "delete":
                self.file_action.emit("delete", src, "")
                try:
                    if os.path.isdir(src):
                        shutil.rmtree(src)
                    else:
                        os.remove(src)
                except Exception as e:
                    self.error.emit(f"Error eliminant {basename}: {e}")
                    return
            self.progress.emit(i + 1, total, basename)
        self.finished.emit()


def _copy_file(src, dst):
    bufsize = 1024 * 1024
    with open(src, "rb") as fsrc, open(dst, "wb") as fdst:
        while True:
            buf = fsrc.read(bufsize)
            if not buf:
                break
            fdst.write(buf)


def hash_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            buf = f.read(65536)
            if not buf:
                break
            h.update(buf)
    return h.hexdigest()


def _match_pattern(name, pattern):
    parts = pattern.split(";")
    for part in parts:
        p = part.strip()
        if not p:
            continue
        if fnmatch.fnmatch(name, p):
            return True
        if fnmatch.fnmatch(os.path.basename(name), p):
            return True
    return False


def compare_dirs(left, right, compare_mode, recursive, include, exclude, tolerance=0):
    def walk(path, rel=""):
        results = {}
        try:
            entries = os.scandir(path)
        except PermissionError:
            return results
        for entry in entries:
            rel_name = os.path.join(rel, entry.name).replace("\\", "/")
            if include and not _match_pattern(rel_name, include):
                continue
            if exclude and _match_pattern(rel_name, exclude):
                continue
            if entry.is_dir(follow_symlinks=False):
                results[rel_name + "/"] = {
                    "is_dir": True,
                    "path": entry.path,
                }
                if recursive:
                    results.update(walk(entry.path, rel_name))
            else:
                try:
                    st = entry.stat()
                    results[rel_name] = {
                        "is_dir": False,
                        "path": entry.path,
                        "size": st.st_size,
                        "mtime": st.st_mtime,
                    }
                except OSError:
                    pass
        return results

    left_files = walk(left)
    right_files = walk(right)

    all_names = sorted(set(left_files) | set(right_files), key=_sort_key)

    dir_entries = []
    file_entries = []

    for name in all_names:
        lf = left_files.get(name)
        rf = right_files.get(name)
        is_dir = (lf or rf)["is_dir"] if (lf or rf) else name.endswith("/")

        if is_dir:
            state = SyncState.IDENTICAL
            left_p = lf["path"] if lf else None
            right_p = rf["path"] if rf else None
            info = {"is_dir": True, "left_path": left_p, "right_path": right_p}
            dir_entries.append((name, state, info, lf, rf))
        else:
            if lf and not rf:
                state = SyncState.COPY_TO_RIGHT
            elif rf and not lf:
                state = SyncState.COPY_TO_LEFT
            elif compare_mode == "date":
                if lf["size"] == rf["size"] and abs(lf["mtime"] - rf["mtime"]) <= tolerance:
                    state = SyncState.IDENTICAL
                elif lf["mtime"] > rf["mtime"]:
                    state = SyncState.COPY_TO_RIGHT
                else:
                    state = SyncState.COPY_TO_LEFT
            elif compare_mode == "size":
                state = SyncState.IDENTICAL if lf["size"] == rf["size"] else SyncState.COPY_TO_RIGHT
            elif compare_mode == "content":
                if lf["size"] != rf["size"]:
                    state = SyncState.COPY_TO_RIGHT
                elif hash_file(lf["path"]) == hash_file(rf["path"]):
                    state = SyncState.IDENTICAL
                else:
                    state = SyncState.COPY_TO_RIGHT
            info = {
                "is_dir": False,
                "left_size": lf["size"] if lf else 0,
                "right_size": rf["size"] if rf else 0,
                "left_mtime": lf["mtime"] if lf else 0,
                "right_mtime": rf["mtime"] if rf else 0,
            }
            file_entries.append((name, state, info, lf, rf))

    return {
        "dirs": dir_entries,
        "files": file_entries,
        "left": left,
        "right": right,
    }


def _sort_key(name):
    parts = name.replace("\\", "/").split("/")
    return (len(parts), name.lower())


# Font única de formateig (core.utils) — abans duplicat aquí amb taula pròpia
from src.core.utils import format_size as _format_size  # noqa: E402, PLC0415


def _format_time(timestamp):
    from datetime import datetime

    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime("%d/%m/%Y %H:%M:%S")


class SyncDialog(QDialog):
    def __init__(self, api):
        super().__init__(api.get_parent_window())
        self.api = api
        self.actions = []
        self._result = None
        self._original_states = {}

        self.setWindowTitle("Sincronitzar carpetes")
        self.resize(1100, 750)

        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        layout.setContentsMargins(8, 8, 8, 8)

        self._build_path_bar(layout)
        self._build_toolbar(layout)
        self._build_table(layout)
        self._build_status_bar(layout)
        self._load_profiles()

    def _build_path_bar(self, layout):
        bar = QWidget()
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        bar_layout.setSpacing(4)

        self.left_path_combo = QComboBox()
        self.left_path_combo.setEditable(True)
        self.left_path_combo.setMinimumWidth(300)
        self.left_path_combo.addItem(self.api.left_panel.current_path)
        bar_layout.addWidget(self.left_path_combo)

        self.sync_mode_combo = QComboBox()
        modes = [("=>", "left_to_right"), ("<=", "right_to_left"), ("<=>", "bidirectional")]
        for text, mode in modes:
            self.sync_mode_combo.addItem(text, mode)
        self.sync_mode_combo.setFixedWidth(50)
        self.sync_mode_combo.currentIndexChanged.connect(self._on_option_change)
        bar_layout.addWidget(self.sync_mode_combo)

        self.filter_combo = QComboBox()
        self.filter_combo.setEditable(True)
        self.filter_combo.setMinimumWidth(120)
        filters = ["Tots els fitxers (*)", "(*.txt)", "(*.py)", "(*.jpg;*.png)", "(*.doc;*.pdf)"]
        self.filter_combo.addItems(filters)
        self.filter_combo.setCurrentText("Tots els fitxers (*)")
        bar_layout.addWidget(self.filter_combo)

        self.right_path_combo = QComboBox()
        self.right_path_combo.setEditable(True)
        self.right_path_combo.setMinimumWidth(300)
        self.right_path_combo.addItem(self.api.right_panel.current_path)
        bar_layout.addWidget(self.right_path_combo)

        btn_swap = QPushButton("⇄")
        btn_swap.setFixedWidth(30)
        btn_swap.clicked.connect(self._swap_paths)
        bar_layout.addWidget(btn_swap)

        btn_scan = QPushButton("Comparar")
        btn_scan.clicked.connect(self._run_scan)
        bar_layout.addWidget(btn_scan)

        layout.addWidget(bar)

    def _build_toolbar(self, layout):
        toolbar = QWidget()
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(0, 0, 0, 0)
        tb_layout.setSpacing(4)

        btn_green = "background-color: #4CAF50; color: white; padding: 4px 12px;"
        btn_orange = "background-color: #FF9800; color: white; padding: 4px 12px;"
        btn_red = "background-color: #f44336; color: white; padding: 4px 12px;"
        btn_blue = "background-color: #2196F3; color: white; padding: 4px 16px; font-weight: bold;"

        self.btn_left_to_right = QPushButton("=> Copiar →")
        self.btn_left_to_right.setStyleSheet(btn_green)
        self.btn_left_to_right.clicked.connect(lambda: self._toggle_action("copy_left_to_right"))
        tb_layout.addWidget(self.btn_left_to_right)

        self.btn_right_to_left = QPushButton("← Copiar <=")
        self.btn_right_to_left.setStyleSheet(btn_orange)
        self.btn_right_to_left.clicked.connect(lambda: self._toggle_action("copy_right_to_left"))
        tb_layout.addWidget(self.btn_right_to_left)

        self.btn_delete_left = QPushButton("X← Orfes esq")
        self.btn_delete_left.setStyleSheet(btn_red)
        self.btn_delete_left.clicked.connect(lambda: self._toggle_action("delete_left"))
        tb_layout.addWidget(self.btn_delete_left)

        self.btn_delete_right = QPushButton("Orfes dret →X")
        self.btn_delete_right.setStyleSheet(btn_red)
        self.btn_delete_right.clicked.connect(lambda: self._toggle_action("delete_right"))
        tb_layout.addWidget(self.btn_delete_right)

        tb_layout.addStretch()

        self.btn_sync = QPushButton("▶ Executar")
        self.btn_sync.setStyleSheet(btn_blue)
        self.btn_sync.setEnabled(False)
        self.btn_sync.clicked.connect(self._run_sync)
        tb_layout.addWidget(self.btn_sync)

        self.btn_select_all = QPushButton("Seleccionar tot")
        self.btn_select_all.clicked.connect(self._select_all)
        tb_layout.addWidget(self.btn_select_all)

        self.btn_deselect = QPushButton("Desseleccionar")
        self.btn_deselect.clicked.connect(self._deselect_all)
        tb_layout.addWidget(self.btn_deselect)

        self.compare_mode_combo = QComboBox()
        for text, mode in [("Data/Hora", "date"), ("Mida", "size"), ("Contingut", "content")]:
            self.compare_mode_combo.addItem(text, mode)
        self.compare_mode_combo.currentIndexChanged.connect(self._on_option_change)
        tb_layout.addWidget(QLabel("Comparar:"))
        tb_layout.addWidget(self.compare_mode_combo)

        self.tolerance_spin = QSpinBox()
        self.tolerance_spin.setRange(0, 3600)
        self.tolerance_spin.setValue(60)
        self.tolerance_spin.setSuffix(" s")
        self.tolerance_spin.setFixedWidth(80)
        tb_layout.addWidget(QLabel("Marge:"))
        tb_layout.addWidget(self.tolerance_spin)

        self.recursive_cb = QCheckBox("Subdirs")
        self.recursive_cb.setChecked(True)
        tb_layout.addWidget(self.recursive_cb)

        layout.addWidget(toolbar)

    def _build_table(self, layout):
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            ["", "Nom", "Mida", "Data", "Estat", "Data", "Mida", "Nom"]
        )
        hdr = self.table.horizontalHeader()
        self.table.setColumnWidth(0, 28)
        hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 150)
        self.table.setColumnWidth(4, 50)
        self.table.setColumnWidth(5, 150)
        self.table.setColumnWidth(6, 90)
        hdr.setSectionResizeMode(7, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(False)
        self.table.setShowGrid(False)
        layout.addWidget(self.table)

    def _build_status_bar(self, layout):
        bar = QWidget()
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(0, 0, 0, 0)
        self.status_label = QLabel("Ready.")
        bar_layout.addWidget(self.status_label)
        bar_layout.addStretch()
        self.summary_label = QLabel("0 objects, 0 seleccionats")
        bar_layout.addWidget(self.summary_label)
        layout.addWidget(bar)

    def _swap_paths(self):
        left = self.left_path_combo.currentText()
        right = self.right_path_combo.currentText()
        self.left_path_combo.setCurrentText(right)
        self.right_path_combo.setCurrentText(left)

    def _on_option_change(self):
        self.btn_sync.setEnabled(False)
        self.table.setRowCount(0)
        self.summary_label.setText("0 objects, 0 seleccionats")

    def _toggle_action(self, action_type):
        if not self._result:
            return
        for row in range(self.table.rowCount()):
            orig = self._original_states.get(row)
            if orig is None:
                continue

            should_check = False
            new_state = None
            if action_type == "copy_left_to_right":
                should_check = orig == SyncState.COPY_TO_RIGHT
                if should_check:
                    new_state = SyncState.COPY_TO_RIGHT
            elif action_type == "copy_right_to_left":
                should_check = orig == SyncState.COPY_TO_LEFT
                if should_check:
                    new_state = SyncState.COPY_TO_LEFT
            elif action_type == "delete_left":
                should_check = orig == SyncState.COPY_TO_LEFT
                if should_check:
                    new_state = SyncState.DELETE_FROM_LEFT
            elif action_type == "delete_right":
                should_check = orig == SyncState.COPY_TO_RIGHT
                if should_check:
                    new_state = SyncState.DELETE_FROM_RIGHT

            if should_check and new_state is not None:
                self._check_and_set_state(row, new_state)
            else:
                self._uncheck_row(row)
        self._update_summary()

    def _check_and_set_state(self, row, state):
        chk = self.table.item(row, 0)
        if chk:
            chk.setCheckState(Qt.CheckState.Checked)
        self._set_row_state(row, state)

    def _uncheck_row(self, row):
        chk = self.table.item(row, 0)
        if chk:
            chk.setCheckState(Qt.CheckState.Unchecked)

    def _set_row_state(self, row, state):
        state_item = self.table.item(row, 4)
        if not state_item:
            return
        state_item.setText(state.value)
        state_item.setData(Qt.ItemDataRole.UserRole, state)
        fg, bg = STATE_COLORS.get(state, (QColor(0, 0, 0), QColor(255, 255, 255)))
        for col in range(self.table.columnCount()):
            item = self.table.item(row, col)
            if item and col != 0:
                item.setForeground(fg)
                if state != SyncState.IDENTICAL:
                    item.setBackground(bg)
                else:
                    item.setBackground(QColor(255, 255, 255))

    def _select_all(self):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                item.setCheckState(Qt.CheckState.Checked)
        self._update_summary()

    def _deselect_all(self):
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                item.setCheckState(Qt.CheckState.Unchecked)
        self._update_summary()

    def _load_profiles(self):
        pass

    def _get_include_exclude(self):
        filter_text = self.filter_combo.currentText()
        include = ""
        exclude = ""
        if (
            filter_text
            and filter_text != "Tots els fitxers (*)"
            and filter_text.startswith("(")
            and filter_text.endswith(")")
        ):
            include = filter_text[1:-1]
        return include, exclude

    def _run_scan(self):
        left = self.left_path_combo.currentText()
        right = self.right_path_combo.currentText()

        if not left or not right:
            self.api.show_message("Cal omplir ambdues rutes.", "warning")
            return
        if left == right:
            self.api.show_message("Les dues rutes són iguals.", "warning")
            return

        self.btn_sync.setEnabled(False)
        self.table.setRowCount(0)
        self.status_label.setText("Escanejant...")
        QApplication.processEvents()

        compare_mode = self.compare_mode_combo.currentData()
        recursive = self.recursive_cb.isChecked()
        tolerance = self.tolerance_spin.value()
        include, exclude = self._get_include_exclude()

        self.worker = CompareWorker(
            left, right, compare_mode, recursive, include, exclude, tolerance
        )
        self.worker.finished.connect(self._on_scan_finished)
        self.worker.error.connect(lambda msg: self.api.show_message(f"Error: {msg}", "error"))
        self.worker.progress.connect(self.status_label.setText)
        self.worker.start()

    def _on_scan_finished(self, result):
        self._result = result
        self._original_states.clear()
        self.table.setRowCount(0)

        self.table.setSortingEnabled(False)
        row = 0
        for name, state, info, lf, rf in result["dirs"]:
            self.table.insertRow(row)
            self._add_dir_row(row, name, state, info, lf, rf)
            row += 1

        for name, state, info, lf, rf in result["files"]:
            self.table.insertRow(row)
            self._add_file_row(row, name, state, info, lf, rf)
            row += 1

        self.table.setSortingEnabled(True)
        self.btn_sync.setEnabled(True)
        self.status_label.setText("Ready.")
        self._update_summary()

    def _add_dir_row(self, row, name, state, info, lf, rf):
        chk = QTableWidgetItem()
        chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        chk.setCheckState(Qt.CheckState.Unchecked)
        self.table.setItem(row, 0, chk)

        display_name = name.rstrip("/")
        cols = [(1, display_name), (2, ""), (3, ""), (4, ""), (5, ""), (6, ""), (7, display_name)]
        for col, text in cols:
            item = QTableWidgetItem(text)
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            item.setBackground(QColor(230, 230, 230))
            item.setForeground(QColor(100, 100, 100))
            self.table.setItem(row, col, item)

    def _add_file_row(self, row, name, state, info, lf, rf):
        self._original_states[row] = state
        chk = QTableWidgetItem()
        chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
        checked = Qt.CheckState.Checked if state != SyncState.IDENTICAL else Qt.CheckState.Unchecked
        chk.setCheckState(checked)
        self.table.setItem(row, 0, chk)

        fg, bg = STATE_COLORS.get(state, (QColor(0, 0, 0), QColor(255, 255, 255)))

        left_size = _format_size(info["left_size"]) if lf else ""
        right_size = _format_size(info["right_size"]) if rf else ""
        left_time = _format_time(info["left_mtime"]) if lf else ""
        right_time = _format_time(info["right_mtime"]) if rf else ""

        cells = [
            (1, name, True),
            (2, left_size, False),
            (3, left_time, False),
            (4, state.value, False),
            (5, right_time, False),
            (6, right_size, False),
            (7, name, True),
        ]

        for col, text, align_right in cells:
            item = QTableWidgetItem(text)
            item.setForeground(fg)
            if state != SyncState.IDENTICAL:
                item.setBackground(bg)
            else:
                item.setBackground(QColor(255, 255, 255))
            if align_right:
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if col == 4:
                item.setData(Qt.ItemDataRole.UserRole, state)
                f2 = item.font()
                f2.setBold(True)
                item.setFont(f2)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(row, col, item)

        if row == 0:
            self.table.itemClicked.connect(self._on_item_clicked)

    def _on_item_clicked(self, item):
        if item.column() == 0:
            self._update_summary()

    def _update_summary(self):
        total = self.table.rowCount()
        checked = 0
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                checked += 1
        self.summary_label.setText(f"{total} objects, {checked} seleccionats")

    def _run_sync(self):
        actions = []

        for row in range(self.table.rowCount()):
            chk = self.table.item(row, 0)
            if not chk or chk.checkState() != Qt.CheckState.Checked:
                continue
            state_item = self.table.item(row, 4)
            if not state_item:
                continue
            state = state_item.data(Qt.ItemDataRole.UserRole)
            name = self.table.item(row, 1).text() if self.table.item(row, 1) else ""

            if state == SyncState.COPY_TO_RIGHT:
                src = os.path.join(self._result["left"], name)
                dst = os.path.join(self._result["right"], name)
                actions.append(("copy", src, dst))
            elif state == SyncState.COPY_TO_LEFT:
                src = os.path.join(self._result["right"], name)
                dst = os.path.join(self._result["left"], name)
                actions.append(("copy", src, dst))
            elif state == SyncState.DELETE_FROM_LEFT:
                actions.append(("delete", os.path.join(self._result["left"], name), ""))
            elif state == SyncState.DELETE_FROM_RIGHT:
                actions.append(("delete", os.path.join(self._result["right"], name), ""))

        if not actions:
            self.api.show_message("No hi ha operacions per executar.", "info")
            return

        confirm = self.api.confirm(f"Executar sincronització amb {len(actions)} operacions?")
        if not confirm:
            return

        self.btn_sync.setEnabled(False)
        progress = QProgressDialog("Sincronitzant...", "Cancel·lar", 0, len(actions), self)
        progress.setWindowTitle("Sincronització")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)

        self.sync_worker = SyncWorker(actions)
        self.sync_worker.progress.connect(
            lambda curr, total, name: (
                progress.setValue(curr),
                progress.setLabelText(f"Sincronitzant: {name} ({curr}/{total})"),
            )
        )
        self.sync_worker.finished.connect(
            lambda: (
                progress.close(),
                self.api.show_message("Sincronització completada.", "info"),
                self.api.left_panel.refresh(),
                self.api.right_panel.refresh(),
                self.accept(),
            )
        )
        self.sync_worker.error.connect(
            lambda msg: (
                progress.close(),
                self.api.show_message(msg, "error"),
                self.btn_sync.setEnabled(True),
            )
        )
        progress.canceled.connect(self.sync_worker.cancel)
        self.sync_worker.start()
