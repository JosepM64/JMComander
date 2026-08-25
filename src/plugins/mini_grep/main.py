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

TEXT_EXTS = {
    ".txt",
    ".py",
    ".log",
    ".ini",
    ".md",
    ".xml",
    ".json",
    ".html",
    ".htm",
    ".csv",
    ".yaml",
    ".yml",
    ".cfg",
    ".conf",
    ".rst",
    ".tex",
    ".bat",
    ".cmd",
    ".ps1",
    ".sh",
    ".js",
    ".ts",
    ".css",
    ".scss",
    ".php",
    ".rb",
    ".pl",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".sql",
    ".r",
    ".lua",
    ".go",
    ".rs",
}


class GrepWorker(QThread):
    progress = Signal(int, int, str)
    finished = Signal(list)

    def __init__(self, path, search_term, parent=None):
        super().__init__(parent)
        self.path = path
        self.search_term = search_term
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        matches = []
        total = 0
        scanned = 0
        # Count files first for progress
        for _root, _dirs, files in os.walk(self.path):
            total += sum(1 for f in files if f.lower().endswith(tuple(TEXT_EXTS)))

        for root, _dirs, files in os.walk(self.path):
            for file in files:
                if self._cancelled:
                    return
                if file.lower().endswith(tuple(TEXT_EXTS)):
                    full_path = os.path.join(root, file)
                    try:
                        with open(full_path, encoding="utf-8", errors="ignore") as f:
                            if self.search_term in f.read():
                                matches.append(os.path.relpath(full_path, self.path))
                    except Exception:  # noqa: BLE001
                        pass
                    scanned += 1
                    self.progress.emit(scanned, total, file)
        self.finished.emit(matches)


def register(api):
    pass


def run_mini_grep(api):
    search_term, ok = QInputDialog.getText(api.get_parent_window(), "Mini-Grep", "Texto a buscar:")
    if not ok or not search_term:
        return

    parent = api.get_parent_window()
    dlg = QDialog(parent)
    dlg.setWindowTitle("Buscando...")
    dlg.resize(400, 80)
    layout = QVBoxLayout(dlg)
    bar = QProgressBar()
    layout.addWidget(bar)
    btn_cancel = QPushButton("Cancelar")
    layout.addWidget(btn_cancel)
    dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

    worker = GrepWorker(api.active_panel.current_path, search_term)
    worker.progress.connect(lambda v, t, f: (bar.setValue(v), bar.setMaximum(t)))
    worker.finished.connect(lambda m: (_show_grep_results(parent, search_term, m), dlg.accept()))
    btn_cancel.clicked.connect(lambda: (worker.cancel(), dlg.reject()))

    worker.start()
    dlg.exec()


def _show_grep_results(parent, search_term, matches):
    if matches:
        msg = f"Trobats {len(matches)} resultats:\n\n"
        msg += "\n".join(matches[:50])
        if len(matches) > 50:
            msg += f"\n... i {len(matches) - 50} més."
        QMessageBox.information(parent, "Resultats", msg)
    else:
        QMessageBox.information(parent, "Sense resultats", f"No es va trobar '{search_term}'.")
