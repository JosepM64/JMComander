import hashlib  # noqa: INP001
import os
import subprocess

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from src.core.plugin_settings import load_settings, save_settings


class DuplicateFinderWorker(QThread):
    progress = Signal(str, int)
    finished = Signal(dict)

    def __init__(self, path, min_size_kb=0):
        super().__init__()
        self.path = path
        self.min_size = min_size_kb * 1024
        self.is_cancelled = False

    def cancel(self):
        self.is_cancelled = True

    def run(self):
        files_by_size = {}
        for root, _dirs, files in os.walk(self.path):
            if self.is_cancelled:
                self.finished.emit({})
                return
            for f in files:
                full_path = os.path.join(root, f)
                try:
                    size = os.path.getsize(full_path)
                    if size >= self.min_size:
                        files_by_size.setdefault(size, []).append(full_path)
                except Exception:  # noqa: BLE001
                    continue

        potential_dupes = {s: paths for s, paths in files_by_size.items() if len(paths) > 1}
        total_potential = sum(len(p) for p in potential_dupes.values())

        dupes = {}
        processed = 0
        for paths in potential_dupes.values():
            hashes = {}
            for p in paths:
                if self.is_cancelled:
                    self.finished.emit({})
                    return
                h = self._calculate_hash(p)
                if h:
                    hashes.setdefault(h, []).append(p)
                processed += 1
                self.progress.emit(
                    f"Analizando: {os.path.basename(p)}", int((processed / total_potential) * 100)
                )

            for h, dupe_list in hashes.items():
                if len(dupe_list) > 1:
                    dupes[h] = dupe_list  # noqa: PERF403

        self.finished.emit(dupes)

    def _calculate_hash(self, path):
        h = hashlib.md5()
        try:
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    if self.is_cancelled:
                        return None
                    h.update(chunk)
            return h.hexdigest()
        except Exception:  # noqa: BLE001
            return None


class DuplicateFinderConfigDialog(QDialog):
    def __init__(self, current_config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configurar Buscador de Duplicados")
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Ignorar archivos más pequeños que:"))
        self.spin_size = QSpinBox()
        self.spin_size.setRange(0, 1048576)  # Hasta 1GB
        self.spin_size.setSuffix(" KB")
        self.spin_size.setValue(current_config.get("min_size_kb", 0))
        layout.addWidget(self.spin_size)

        btn_save = QPushButton("Guardar Configuración")
        btn_save.clicked.connect(self.accept)
        layout.addWidget(btn_save)

    def get_settings(self):
        return {"min_size_kb": self.spin_size.value()}

    def get_config(self):
        """Alias para compatibilidad con el sistema de configuración de plugins"""
        return self.get_settings()


class DuplicateFinderDialog(QDialog):
    def __init__(self, path, config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Buscador de Duplicados")
        self.resize(700, 500)
        self.path = path
        self.config = config

        layout = QVBoxLayout(self)
        self.lbl_status = QLabel(f"Preparado (Mín: {config.get('min_size_kb', 0)} KB)")
        layout.addWidget(self.lbl_status)

        self.progress = QProgressBar()
        layout.addWidget(self.progress)
        self.list_results = QListWidget()
        layout.addWidget(self.list_results)

        btn_layout = QHBoxLayout()
        self.btn_start = QPushButton("Empezar Escaneo")
        self.btn_start.clicked.connect(self.start_scan)
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.clicked.connect(self.cancel_scan)
        self.btn_cancel.setEnabled(False)
        self.btn_delete = QPushButton("Eliminar Seleccionados")
        self.btn_delete.setEnabled(False)
        self.btn_delete.clicked.connect(self.delete_selected)
        self.btn_open_folder = QPushButton("Abrir Carpeta")
        self.btn_open_folder.setEnabled(False)
        self.btn_open_folder.clicked.connect(self.open_folder)
        self.btn_open_file = QPushButton("Abrir Archivo")
        self.btn_open_file.setEnabled(False)
        self.btn_open_file.clicked.connect(self.open_file)
        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_open_folder)
        btn_layout.addWidget(self.btn_open_file)
        layout.addLayout(btn_layout)

        self.list_results.itemSelectionChanged.connect(self.on_selection_changed)
        self.list_results.itemDoubleClicked.connect(self.on_double_click)

    def on_double_click(self, item):
        path = item.text()
        if os.path.exists(path):
            folder = os.path.dirname(path)
            subprocess.Popen(f'explorer "{folder}"', shell=True)

    def start_scan(self):
        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.btn_delete.setEnabled(False)
        self.list_results.clear()
        self.worker = DuplicateFinderWorker(self.path, self.config.get("min_size_kb", 0))
        self.worker.progress.connect(
            lambda t, v: (self.lbl_status.setText(t), self.progress.setValue(v))
        )
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def cancel_scan(self):
        if hasattr(self, "worker") and self.worker.isRunning():
            self.worker.cancel()
            self.lbl_status.setText("Escaneo cancelado por el usuario.")
            self.btn_start.setEnabled(True)
            self.btn_cancel.setEnabled(False)
            self.progress.setValue(0)

    def _on_finished(self, dupes):
        self.lbl_status.setText(f"Escaneo finalizado. {len(dupes)} grupos encontrados.")
        for h, paths in dupes.items():
            item = QListWidgetItem(f"Grupo Hash: {h[:8]} ({len(paths)} archivos)")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            item.setBackground(Qt.GlobalColor.lightGray)
            self.list_results.addItem(item)
            for p in paths:
                child = QListWidgetItem(p)
                child.setFlags(child.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                child.setCheckState(Qt.CheckState.Unchecked)
                self.list_results.addItem(child)
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.btn_delete.setEnabled(True)
        self.btn_open_folder.setEnabled(True)
        self.btn_open_file.setEnabled(True)

    def on_selection_changed(self):
        selected = self.list_results.selectedItems()
        if selected:
            text = selected[0].text()
            if os.path.exists(text):
                self.btn_open_folder.setEnabled(True)
                self.btn_open_file.setEnabled(True)
            else:
                self.btn_open_folder.setEnabled(False)
                self.btn_open_file.setEnabled(False)
        else:
            self.btn_open_folder.setEnabled(False)
            self.btn_open_file.setEnabled(False)

    def open_folder(self):
        selected = self.list_results.selectedItems()
        if selected:
            path = selected[0].text()
            if os.path.exists(path):
                folder = os.path.dirname(path)
                subprocess.Popen(f'explorer "{folder}"', shell=True)

    def open_file(self):
        selected = self.list_results.selectedItems()
        if selected:
            path = selected[0].text()
            if os.path.exists(path):
                os.startfile(path) if os.name == "nt" else subprocess.Popen(["xdg-open", path])

    def delete_selected(self):
        to_delete = [
            self.list_results.item(i).text()
            for i in range(self.list_results.count())
            if self.list_results.item(i).checkState() == Qt.CheckState.Checked
        ]
        if (
            to_delete
            and QMessageBox.question(self, "Eliminar", f"¿Eliminar {len(to_delete)} archivos?")
            == QMessageBox.StandardButton.Yes
        ):
            for p in to_delete:
                try:
                    os.remove(p)
                except Exception:  # noqa: BLE001
                    pass
            self.accept()


def _load_settings():
    return load_settings("duplicate_finder", {"min_size_kb": 0})


def _save_settings(settings):
    save_settings("duplicate_finder", settings)


def register(api):
    pass


def run_duplicate_finder(api):
    settings = _load_settings()
    dlg = DuplicateFinderDialog(api.active_panel.current_path, settings, api.get_parent_window())
    dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
    dlg.show()
