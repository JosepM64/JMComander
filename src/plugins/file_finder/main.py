import fnmatch  # noqa: INP001
import os
from functools import partial

from PySide6.QtCore import QPoint, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)


class FileFinderWorker(QThread):
    progress = Signal(int, int, str)
    finished = Signal(list)

    def __init__(self, path, pattern, search_type, recursive, max_results, parent=None):
        super().__init__(parent)
        self.path = path
        self.pattern = pattern.lower() if pattern else ""
        self.search_type = search_type
        self.recursive = recursive
        self.max_results = max_results
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True

    def run(self):  # noqa: PLR0912
        results = []
        scanned = 0

        try:
            if self.recursive:
                for root, _dirs, files in os.walk(self.path):
                    if self.is_cancelled:
                        break
                    for f in files:
                        if self.is_cancelled:
                            break
                        if len(results) >= self.max_results:
                            break

                        scanned += 1
                        if scanned % 100 == 0:
                            self.progress.emit(len(results), scanned, root)

                        if self._matches(f):
                            results.append(os.path.join(root, f))
            else:
                try:
                    files = os.listdir(self.path)
                    for f in files:
                        if self.is_cancelled:
                            break
                        if len(results) >= self.max_results:
                            break

                        if os.path.isfile(os.path.join(self.path, f)) and self._matches(f):
                            results.append(os.path.join(self.path, f))
                except PermissionError:
                    pass
        except Exception:  # noqa: BLE001
            pass

        self.finished.emit(results)

    def _matches(self, filename):
        if self.search_type == "extension":
            if not self.pattern.startswith("."):
                self.pattern = "." + self.pattern
            return filename.lower().endswith(self.pattern)
        if self.search_type == "contains":
            return self.pattern in filename.lower()
        if self.search_type == "starts":
            return filename.lower().startswith(self.pattern)
        if self.search_type == "ends":
            return filename.lower().endswith(self.pattern)
        if self.search_type == "exact":
            return filename.lower() == self.pattern
        if self.search_type == "wildcard":
            return fnmatch.fnmatch(filename.lower(), self.pattern.lower())
        return False


class FileFinderDialog(QDialog):
    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.path = path
        self.worker = None
        self.results = []
        self.setWindowTitle("Buscador de Archivos")
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(f"Carpeta: {path}"))

        search_group = QGroupBox("Búsqueda")
        search_layout = QVBoxLayout()

        pattern_layout = QHBoxLayout()
        pattern_layout.addWidget(QLabel("Patrón:"))
        self.txt_pattern = QLineEdit()
        self.txt_pattern.setPlaceholderText("Ej: .txt, *.log, archivo_")
        self.txt_pattern.textChanged.connect(self._on_pattern_changed)
        pattern_layout.addWidget(self.txt_pattern)

        self.cmb_type = QComboBox()
        for label, data in [
            ("Extensión", "extension"),
            ("Contiene", "contains"),
            ("Empieza por", "starts"),
            ("Acaba por", "ends"),
            ("Coincidencia exacta", "exact"),
            ("Comodines (* ?)", "wildcard"),
        ]:
            self.cmb_type.addItem(label, data)
        self.cmb_type.currentIndexChanged.connect(self._on_type_changed)
        pattern_layout.addWidget(self.cmb_type)
        search_layout.addLayout(pattern_layout)

        options_layout = QHBoxLayout()
        self.chk_recursive = QCheckBox("Buscar en subcarpetas")
        self.chk_recursive.setChecked(True)
        options_layout.addWidget(self.chk_recursive)

        options_layout.addWidget(QLabel("Máx. resultados:"))
        self.spin_max = QSpinBox()
        self.spin_max.setRange(100, 10000)
        self.spin_max.setValue(1000)
        self.spin_max.setSuffix(" archivos")
        options_layout.addWidget(self.spin_max)
        options_layout.addStretch()
        search_layout.addLayout(options_layout)
        search_group.setLayout(search_layout)
        layout.addWidget(search_group)

        self.list_results = QListWidget()
        self.list_results.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.list_results.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_results.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self.list_results)

        self.lbl_status = QLabel("Escribe un patrón y pulsa Buscar")
        layout.addWidget(self.lbl_status)

        btn_layout = QHBoxLayout()
        self.btn_search = QPushButton("Buscar")
        self.btn_search.clicked.connect(self.start_search)
        self.btn_select_all = QPushButton("Seleccionar todo")
        self.btn_select_all.clicked.connect(self.select_all)
        self.btn_select_none = QPushButton("Deseleccionar")
        self.btn_select_none.clicked.connect(self.select_none)
        self.btn_delete = QPushButton("Eliminar seleccionados")
        self.btn_delete.clicked.connect(self.delete_selected)
        self.btn_delete.setStyleSheet("background-color: #f44336; color: white;")
        self.btn_delete.setEnabled(False)
        self.btn_close = QPushButton("Cerrar")
        self.btn_close.clicked.connect(self.close)

        btn_layout.addWidget(self.btn_search)
        btn_layout.addWidget(self.btn_select_all)
        btn_layout.addWidget(self.btn_select_none)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)

        self.list_results.itemSelectionChanged.connect(self._update_delete_button)

    def _on_pattern_changed(self, text):
        pass

    def _on_type_changed(self, _index):
        placeholder_map = {
            "extension": "Ej: .txt, .jpg, .log",
            "contains": "Ej: archivo, foto",
            "starts": "Ej: IMG_, foto",
            "ends": "Ej: _backup, 2024",
            "exact": "Ej: archivo.txt",
            "wildcard": "Ej: *.jpg, archivo_*.log",
        }
        search_type = self.cmb_type.currentData()
        self.txt_pattern.setPlaceholderText(placeholder_map.get(search_type, ""))

    def _update_delete_button(self):
        selected = len(self.list_results.selectedItems())
        self.btn_delete.setEnabled(selected > 0)
        if selected > 0:
            self.btn_delete.setText(f"Eliminar seleccionados ({selected})")
        else:
            self.btn_delete.setText("Eliminar seleccionados")

    def _on_context_menu(self, position):
        self.show_context_menu(position)

    def show_context_menu(self, position):
        menu = QMenu(self)

        selected = self.list_results.selectedItems()

        action_select_all = menu.addAction("Seleccionar todo")
        action_select_all.triggered.connect(partial(self.select_all))

        action_deselect = menu.addAction("Deseleccionar todo")
        action_deselect.triggered.connect(partial(self.select_none))

        if selected:
            menu.addSeparator()
            action_delete = menu.addAction(f"Eliminar {len(selected)} archivos")
            action_delete.triggered.connect(partial(self.delete_selected))

        if isinstance(position, QPoint):
            global_pos = position
        else:
            global_pos = self.list_results.viewport().mapToGlobal(position)

        menu.exec(global_pos)

    def start_search(self):
        pattern = self.txt_pattern.text().strip()
        if not pattern:
            QMessageBox.warning(self, "Aviso", "Introduce un patrón de búsqueda.")
            return

        self.list_results.clear()
        self.btn_search.setEnabled(False)
        self.lbl_status.setText("Buscando...")

        self.worker = FileFinderWorker(
            path=self.path,
            pattern=pattern,
            search_type=self.cmb_type.currentData(),
            recursive=self.chk_recursive.isChecked(),
            max_results=self.spin_max.value(),
        )

        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_progress(self, found, scanned, _current_folder):
        self.lbl_status.setText(f"Encontrados: {found} | Escaneados: {scanned}")

    def on_finished(self, results):
        self.btn_search.setEnabled(True)
        self.results = results

        for path in results:
            item = QListWidgetItem(path)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsSelectable)
            self.list_results.addItem(item)

        self.lbl_status.setText(f"{len(results)} archivos encontrados")

    def select_all(self):
        for i in range(self.list_results.count()):
            self.list_results.item(i).setSelected(True)

    def select_none(self):
        for i in range(self.list_results.count()):
            self.list_results.item(i).setSelected(False)

    def delete_selected(self):
        selected = self.list_results.selectedItems()
        if not selected:
            return

        count = len(selected)
        [item.text() for item in selected]

        msg = f"¿Eliminar {count} archivos?\n\n"
        msg += "Esta acción no se puede deshacer."

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

            rows_to_remove = sorted(
                [self.list_results.row(item) for item in selected], reverse=True
            )
            for row in rows_to_remove:
                path = self.list_results.item(row).text()
                try:
                    os.remove(path)
                    deleted += 1
                except Exception as e:  # noqa: BLE001
                    errors.append(f"{os.path.basename(path)}: {e!s}")
                self.list_results.takeItem(row)

            self._update_delete_button()

            msg = f"Archivos eliminados: {deleted}"
            if errors:
                msg += f"\n\nErrores: {len(errors)}"
                msg += "\n".join(errors[:3])
            QMessageBox.information(self, "Resultado", msg)

    def closeEvent(self, event):  # noqa: N802
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait()
        super().closeEvent(event)


def register(api):
    pass


def run_file_finder(api):
    path = api.active_panel.current_path
    if not os.path.isdir(path):
        QMessageBox.warning(api.get_parent_window(), "Error", "Selecciona una carpeta válida.")
        return
    dlg = FileFinderDialog(path, api.get_parent_window())
    dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    dlg.show()
