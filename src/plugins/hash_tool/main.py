import hashlib
import os

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QInputDialog,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)


class HashWorker(QThread):
    progress = Signal(int, int)
    finished = Signal(list)

    def __init__(self, paths, algorithm, parent=None):
        super().__init__(parent)
        self.paths = paths
        self.algorithm = algorithm
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        results = []
        total = len(self.paths)
        for i, path in enumerate(self.paths):
            if self._cancelled:
                break
            if os.path.isfile(path):
                try:
                    h = hashlib.new(self.algorithm.lower())
                    with open(path, "rb") as f:
                        while True:
                            if self._cancelled:
                                return
                            block = f.read(65536)
                            if not block:
                                break
                            h.update(block)
                    results.append(f"{os.path.basename(path)}:\n{h.hexdigest()}\n")
                except Exception as e:  # noqa: BLE001
                    results.append(f"{os.path.basename(path)}: Error {e}")
            self.progress.emit(i + 1, total)
        self.finished.emit(results)


def register(api):
    pass


def run_hash_tool(api):
    selected = api.active_panel.get_selected_paths()
    if not selected:
        QMessageBox.warning(api.get_parent_window(), "Hash Tool", "Selecciona al menos un archivo.")
        return

    algorithms = ["MD5", "SHA1", "SHA256", "SHA512"]
    algo, ok = QInputDialog.getItem(
        api.get_parent_window(), "Algoritmo", "Seleccionar:", algorithms, 0, False
    )
    if not ok:
        return

    parent = api.get_parent_window()
    dlg = QDialog(parent)
    dlg.setWindowTitle(f"Calculando {algo}...")
    dlg.resize(350, 80)
    layout = QVBoxLayout(dlg)
    bar = QProgressBar()
    bar.setRange(0, len(selected))
    layout.addWidget(bar)
    btn_cancel = QPushButton("Cancelar")
    layout.addWidget(btn_cancel)
    dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

    worker = HashWorker(selected, algo)
    worker.progress.connect(lambda v, t: (bar.setValue(v), bar.setMaximum(t)))
    worker.finished.connect(lambda r: (_show_hash_results(parent, algo, r), dlg.accept()))
    btn_cancel.clicked.connect(lambda: (worker.cancel(), dlg.reject()))

    worker.start()
    dlg.exec()


def _show_hash_results(parent, algo, results):
    if results:
        QMessageBox.information(parent, f"Resultados {algo}", "\n".join(results))
