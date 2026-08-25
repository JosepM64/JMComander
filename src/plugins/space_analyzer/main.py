import os
import subprocess
from datetime import datetime

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from src.core.utils import format_size


class ScanWorker(QThread):
    progress = Signal(int, int, str)
    finished = Signal(list, int)

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.path = path
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        file_list = []
        total_size = 0
        file_count = 0

        for root, _dirs, files in os.walk(self.path):
            if self._cancelled:
                self.finished.emit([], 0)
                return
            for file in files:
                if self._cancelled:
                    self.finished.emit([], 0)
                    return
                file_count += 1
                path = os.path.join(root, file)
                try:
                    size = os.path.getsize(path)
                    file_list.append((path, size))
                    total_size += size
                except Exception:  # noqa: BLE001
                    pass
                if file_count % 100 == 0:
                    self.progress.emit(file_count, 0, file)

        self.progress.emit(file_count, 0, "Ordenant...")
        file_list.sort(key=lambda x: x[1], reverse=True)
        self.finished.emit(file_list[:50], total_size)


class SpaceAnalyzerDialog(QDialog):
    def __init__(self, current_path, parent=None):
        super().__init__(parent)
        self.current_path = current_path
        self.setWindowTitle("Analizador de Espacio")
        self.resize(800, 600)

        layout = QVBoxLayout(self)

        self.info_label = QLabel(f"Analizando: {current_path}")
        self.info_label.setStyleSheet("font-weight: bold; padding: 5px;")
        layout.addWidget(self.info_label)

        self.bar = QProgressBar()
        self.bar.setRange(0, 0)
        layout.addWidget(self.bar)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Tamaño", "Ruta", "Archivo"])
        self.table.setColumnWidth(0, 100)
        self.table.setColumnWidth(1, 380)
        self.table.setColumnWidth(2, 280)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("QTableWidget { gridline-color: #d0d0d0; }")
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.itemDoubleClicked.connect(self.on_double_click)
        self.table.hide()
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        self.btn_export = QPushButton("Exportar a TXT")
        self.btn_export.clicked.connect(self.export_to_txt)
        self.btn_export.setEnabled(False)
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.clicked.connect(self._cancel_scan)
        self.btn_close = QPushButton("Tancar")
        self.btn_close.clicked.connect(self.accept)
        self.btn_close.hide()
        btn_layout.addWidget(self.btn_export)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)

        self._start_scan()

    def _start_scan(self):
        self._worker = ScanWorker(self.current_path)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _cancel_scan(self):
        if hasattr(self, "_worker") and self._worker.isRunning():
            self._worker.cancel()

    def _on_progress(self, count, _total, filename):
        self.info_label.setText(f"Escanejats: {count} fitxers... {filename}")

    def _on_finished(self, top_files, total_size):
        self.bar.hide()
        self.table.show()
        self.btn_cancel.hide()
        self.btn_close.show()

        self.table.setRowCount(len(top_files))
        for i, (path, size) in enumerate(top_files):
            self.table.setItem(i, 0, QTableWidgetItem(format_size(size)))
            self.table.item(i, 0).setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            folder = os.path.dirname(path)
            self.table.setItem(i, 1, QTableWidgetItem(folder))
            self.table.setItem(i, 2, QTableWidgetItem(os.path.basename(path)))

        info = f"Total: {format_size(total_size)} | Mostrant top {len(top_files)}"
        self.table.setToolTip(info)
        self.info_label.setText(info)
        self.btn_export.setEnabled(True)

    def _walk_files(self, path):
        count = 0
        for _root, _dirs, files in os.walk(path):
            count += len(files)
        return count

    def get_selected_path(self):
        row = self.table.currentRow()
        if row >= 0:
            folder = self.table.item(row, 1).text()
            filename = self.table.item(row, 2).text()
            return os.path.join(folder, filename)
        return None

    def show_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if not item:
            return
        row = item.row()
        folder = self.table.item(row, 1).text()
        filename = self.table.item(row, 2).text()
        full_path = os.path.join(folder, filename)
        if not os.path.exists(full_path):
            return
        menu = QMenu(self)
        act_execute = menu.addAction("Ejecutar")
        act_open_folder = menu.addAction("Abrir carpeta")
        menu.addSeparator()
        act_copy_path = menu.addAction("Copiar ruta")
        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action == act_execute:
            self.execute_file(full_path)
        elif action == act_open_folder:
            self.open_folder(full_path)
        elif action == act_copy_path:
            QApplication.clipboard().setText(full_path)

    def on_double_click(self, _item):
        path = self.get_selected_path()
        if path and os.path.exists(path):
            self.execute_file(path)

    def execute_file(self, path):
        try:
            if os.name == "nt":
                os.startfile(path)
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "Error", f"No se pudo ejecutar:\n{e!s}")

    def open_folder(self, path):
        folder = os.path.dirname(path)
        if os.path.exists(folder):
            subprocess.Popen(f'explorer "{folder}"', shell=True)

    def export_to_txt(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar a TXT",
            os.path.join(self.current_path, "espacio_usado.txt"),
            "Archivos de texto (*.txt)",
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write("Analisis de Espacio en Disco\n")
                f.write("=" * 60 + "\n")
                f.write(f"Directorio: {self.current_path}\n")
                f.write(f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n")
                f.write("=" * 60 + "\n\n")
                f.write(f"{'TAMANO':>12} | {'RUTA':<45} | ARCHIVO\n")
                f.write("-" * 100 + "\n")
                for i in range(self.table.rowCount()):
                    size = self.table.item(i, 0).text()
                    folder = self.table.item(i, 1).text()
                    fname = self.table.item(i, 2).text()
                    folder_disp = folder[:42] + "..." if len(folder) > 45 else folder
                    f.write(f"{size:>12} | {folder_disp:<45} | {fname}\n")
                f.write("\n" + "=" * 60 + "\n")
                f.write("Generado por JMComander\n")
            QMessageBox.information(self, "Exportado", f"Archivo guardado en:\n{path}")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Error", f"No se pudo guardar:\n{e!s}")


def register(api):
    pass


def run_space_analyzer(api):
    dlg = SpaceAnalyzerDialog(api.active_panel.current_path, api.get_parent_window())
    dlg.exec()
