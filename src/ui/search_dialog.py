import fnmatch
import os
from functools import partial

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


class SearchWorker(QThread):
    found_item = Signal(str, str, str)
    finished = Signal()
    error = Signal(str)

    # Extensiones de archivos de texto comunes
    TEXT_EXTENSIONS = {  # noqa: RUF012
        ".txt",
        ".py",
        ".js",
        ".html",
        ".htm",
        ".css",
        ".json",
        ".xml",
        ".yaml",
        ".yml",
        ".md",
        ".markdown",
        ".rst",
        ".log",
        ".csv",
        ".ini",
        ".cfg",
        ".conf",
        ".bat",
        ".sh",
        ".ps1",
        ".sql",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".java",
        ".cs",
        ".go",
        ".rs",
        ".rb",
        ".php",
        ".pl",
        ".bash",
        ".zsh",
        ".fish",
        ".ts",
        ".tsx",
        ".jsx",
        ".vue",
        ".svelte",
        ".swift",
        ".kt",
        ".scala",
        ".r",
        ".lua",
        ".perl",
        ".tcl",
        ".awk",
        ".properties",
        ".env",
        ".gitignore",
        ".dockerignore",
        ".editorconfig",
        ".xls",
        ".xlsx",
        ".doc",
        ".docx",
        ".ppt",
        ".pptx",  # Office (menos común)
    }

    def __init__(self, root_path, pattern, search_subdirs, content_text=None):
        super().__init__()
        self.root_path = root_path
        self.pattern = pattern
        self.search_subdirs = search_subdirs
        self.content_text = content_text
        self.is_running = True

    def stop(self):
        self.is_running = False

    def _is_text_file(self, filename):
        """Determina si un archivo es probable archivo de texto"""
        ext = os.path.splitext(filename.lower())[1]
        # Si tiene extensión de texto, es probable que sea texto
        if ext in self.TEXT_EXTENSIONS:
            return True
        # Si no tiene extensión, asumir texto
        return not ext

    def run(self):
        try:
            if self.search_subdirs:
                iterator = os.walk(self.root_path)
            else:
                iterator = [(self.root_path, [], os.listdir(self.root_path))]

            for root, _dirs, files in iterator:
                if not self.is_running:
                    break
                for filename in fnmatch.filter(files, self.pattern):
                    if not self.is_running:
                        break
                    full_path = os.path.join(root, filename)

                    # Si buscar contenido, verificar que sea archivo de texto
                    if self.content_text:
                        if not self._is_text_file(filename):
                            continue
                        try:
                            with open(full_path, encoding="utf-8", errors="ignore") as f:
                                if self.content_text not in f.read():
                                    continue
                        except Exception as _e:  # noqa: BLE001
                            continue

                    size = f"{os.path.getsize(full_path) / 1024:.1f} KB"
                    self.found_item.emit(filename, root, size)
        except Exception as e:  # noqa: BLE001
            self.error.emit(str(e))
        self.finished.emit()


class SearchDialog(QDialog):
    def __init__(self, start_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Buscar Archivos")
        self.resize(700, 500)
        self.main_window = parent

        layout = QVBoxLayout(self)

        options_layout = QVBoxLayout()
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Nombre (ej: *.txt, *.py):"))
        self.input_pattern = QComboBox()
        self.input_pattern.setEditable(True)
        self.input_pattern.addItems(["*.txt", "*.py", "*.js", "*.html", "*.md", "*.*"])
        row1.addWidget(self.input_pattern, 1)

        self.btn_search = QPushButton("Buscar")
        self.btn_search.clicked.connect(self.start_search)
        row1.addWidget(self.btn_search)
        options_layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Buscar en:"))
        self.input_path = QLineEdit(start_path)
        row2.addWidget(self.input_path, 1)
        options_layout.addLayout(row2)

        row3 = QHBoxLayout()
        self.chk_subdirs = QCheckBox("Buscar en subdirectorios")
        self.chk_subdirs.setChecked(True)
        row3.addWidget(self.chk_subdirs)

        self.chk_content = QCheckBox("Contiene texto:")
        self.chk_content.setChecked(False)
        self.chk_content.setToolTip(
            "Busca dentro del contenido de archivos de texto (txt, py, js, html, etc.)"
        )
        self.input_content = QLineEdit()
        self.input_content.setEnabled(False)
        self.input_content.setPlaceholderText("Palabra a buscar dentro...")
        self.chk_content.toggled.connect(self.input_content.setEnabled)
        row3.addWidget(self.chk_content)
        row3.addWidget(self.input_content)
        row3.addStretch()
        options_layout.addLayout(row3)
        layout.addLayout(options_layout)

        line = QLabel()
        line.setFrameStyle(QLabel.Shape.HLine | QLabel.Shadow.Sunken)
        layout.addWidget(line)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_focus = QPushButton("🎯 Ir al archivo")
        self.btn_focus.setToolTip("Navega al archivo seleccionado y lo activa")
        self.btn_focus.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.btn_focus.clicked.connect(self.focus_item)
        self.btn_focus.setEnabled(False)
        btn_layout.addWidget(self.btn_focus)

        layout.addLayout(btn_layout)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Nombre", "Ubicación", "Tamaño"])
        self.table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.cellDoubleClicked.connect(self.on_item_double_clicked)
        self.table.selectionModel().selectionChanged.connect(self.on_selection_changed)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.table)

        status_layout = QHBoxLayout()
        self.lbl_status = QLabel("Listo.")
        status_layout.addWidget(self.lbl_status)
        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        status_layout.addWidget(self.progress)

        self.btn_stop = QPushButton("Detener")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self.stop_search)
        status_layout.addWidget(self.btn_stop)
        layout.addLayout(status_layout)

        self.worker = None

        self.input_pattern.lineEdit().selectAll()
        self.input_content.selectAll()

    def on_selection_changed(self, selected, _deselected):
        self.btn_focus.setEnabled(len(selected.indexes()) > 0)

    def start_search(self):
        path = self.input_path.text()
        if not path or not os.path.exists(path):
            return

        self.table.setRowCount(0)
        self.lbl_status.setText("Buscando...")
        self.btn_search.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress.setVisible(True)

        content = self.input_content.text() if self.chk_content.isChecked() else None
        self.worker = SearchWorker(
            path, self.input_pattern.currentText(), self.chk_subdirs.isChecked(), content
        )
        self.worker.found_item.connect(self.add_result)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(lambda e: QMessageBox.critical(self, "Error", e))
        self.worker.start()

    def stop_search(self):
        if self.worker:
            self.worker.stop()

    def add_result(self, name, path, size):
        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setItem(row, 0, QTableWidgetItem(name))
        self.table.setItem(row, 1, QTableWidgetItem(path))
        self.table.setItem(row, 2, QTableWidgetItem(size))
        self.lbl_status.setText(f"Encontrados: {row + 1}")
        self.btn_focus.setEnabled(True)

    def on_finished(self):
        self.btn_search.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.progress.setVisible(False)
        self.lbl_status.setText(f"Búsqueda finalizada. {self.table.rowCount()} items.")

    def on_item_double_clicked(self, _row, _col):
        self.focus_item()

    def focus_item(self):
        row = self.table.currentRow()
        if row < 0:
            return

        name = self.table.item(row, 0).text()
        path = self.table.item(row, 1).text()
        full_path = os.path.join(path, name)

        if self.main_window:
            self.main_window.active_panel.navigate_and_select(full_path)
            self.main_window.activateWindow()
            self.close()

    def show_context_menu(self, position):
        selected_rows = {index.row() for index in self.table.selectionModel().selectedIndexes()}

        if not selected_rows:
            return

        menu = QMenu(self)

        action_select_all = menu.addAction("Seleccionar todo")
        action_select_all.triggered.connect(partial(self.select_all))

        action_deselect = menu.addAction("Deseleccionar todo")
        action_deselect.triggered.connect(partial(self.select_none))

        menu.addSeparator()

        action_delete = menu.addAction(f"Eliminar {len(selected_rows)} archivos")
        action_delete.triggered.connect(partial(self.delete_selected))

        global_pos = self.table.viewport().mapToGlobal(position)
        menu.exec(global_pos)

    def select_all(self):
        self.table.selectAll()

    def select_none(self):
        self.table.clearSelection()

    def delete_selected(self):
        selected_rows = sorted(
            {index.row() for index in self.table.selectionModel().selectedIndexes()},
            reverse=True,
        )

        if not selected_rows:
            return

        paths = []
        for row in selected_rows:
            name = self.table.item(row, 0).text()
            path = self.table.item(row, 1).text()
            full_path = os.path.join(path, name)
            paths.append(full_path)

        count = len(paths)
        msg = f"¿Eliminar {count} archivos?\n\nEsta acción no se puede deshacer."

        reply = QMessageBox.warning(
            self,
            "Confirmar eliminación",
            msg,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            deleted = 0
            errors = []

            for path in paths:
                try:
                    os.remove(path)
                    deleted += 1
                except Exception as e:  # noqa: BLE001
                    errors.append(f"{os.path.basename(path)}: {e!s}")

            for row in selected_rows:
                self.table.removeRow(row)

            msg = f"Archivos eliminados: {deleted}"
            if errors:
                msg += f"\n\nErrores: {len(errors)}"
                msg += "\n".join(errors[:3])
            QMessageBox.information(self, "Resultado", msg)
