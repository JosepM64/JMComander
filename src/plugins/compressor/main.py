import os  # noqa: INP001
import shutil
import zipfile

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QVBoxLayout,
)


class CompressorDialog(QDialog):
    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Comprimir Archivos")
        self.resize(400, 200)
        self.items = items

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Comprimiendo {len(items)} elementos."))
        layout.addWidget(QLabel("Nombre del archivo:"))
        self.input_name = QLineEdit("archivo_comprimido")
        layout.addWidget(self.input_name)
        layout.addWidget(QLabel("Formato:"))
        self.combo_format = QComboBox()
        self.combo_format.addItems(["zip", "tar", "gztar"])
        layout.addWidget(self.combo_format)
        btn = QPushButton("Comprimir")
        btn.clicked.connect(self.compress)
        layout.addWidget(btn)

    def _count_files(self, items):
        total = 0
        for item in items:
            if os.path.isdir(item):
                for _root, _dirs, files in os.walk(item):
                    total += len(files)
            else:
                total += 1
        return total

    def compress(self):
        name = self.input_name.text()
        fmt = self.combo_format.currentText()
        if not name:
            return
        base_dir = os.path.dirname(self.items[0])
        output_filename = os.path.join(base_dir, name)
        try:
            full_output = f"{output_filename}.{fmt}"
            if fmt == "zip":
                total_files = self._count_files(self.items)
                # Crear diálogo de progreso
                progress = QProgressDialog(
                    "Comprimiendo archivos...", "Cancelar", 0, total_files, self
                )
                progress.setWindowTitle("Compresión ZIP")
                progress.setWindowModality(Qt.WindowModality.WindowModal)
                progress.setMinimumDuration(500)
                processed = 0
                with zipfile.ZipFile(full_output, "w", zipfile.ZIP_DEFLATED) as zf:
                    for item in self.items:
                        if os.path.isdir(item):
                            for root, _dirs, files in os.walk(item):
                                for file in files:
                                    if progress.wasCanceled():
                                        progress.close()
                                        QMessageBox.information(
                                            self, "Cancelado", "Compresión cancelada."
                                        )
                                        return
                                    zf.write(
                                        os.path.join(root, file),
                                        os.path.relpath(
                                            os.path.join(root, file), os.path.dirname(item)
                                        ),
                                    )
                                    processed += 1
                                    progress.setValue(processed)
                                    progress.setLabelText(f"Comprimiendo: {file}")
                        else:
                            if progress.wasCanceled():
                                progress.close()
                                QMessageBox.information(self, "Cancelado", "Compresión cancelada.")
                                return
                            zf.write(item, os.path.basename(item))
                            processed += 1
                            progress.setValue(processed)
                progress.setValue(total_files)
                progress.close()
            elif len(self.items) == 1 and os.path.isdir(self.items[0]):
                # Para TAR, progreso indeterminado
                progress = QProgressDialog("Comprimiendo carpeta...", "Cancelar", 0, 0, self)
                progress.setWindowTitle(f"Compresión {fmt}")
                progress.setWindowModality(Qt.WindowModality.WindowModal)
                progress.setMinimumDuration(500)
                progress.setValue(0)
                # shutil.make_archive sin cancelación fácil; ejecutar y cerrar
                shutil.make_archive(output_filename, fmt, self.items[0])
                progress.close()
            else:
                QMessageBox.warning(self, "Aviso", "Para TAR selecciona una sola carpeta.")
                return
            QMessageBox.information(self, "Éxito", f"Creado: {full_output}")
            self.accept()
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(e))


def register(api):
    pass


def run_compressor(api):
    items = api.active_panel.get_selected_paths()
    if not items:
        QMessageBox.warning(api.get_parent_window(), "Aviso", "Selecciona archivos.")
        return
    dlg = CompressorDialog(items, api.get_parent_window())
    dlg.exec()
    api.active_panel.refresh()
