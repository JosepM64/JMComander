import ctypes
import os
import time

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

TEST_SIZE = 200 * 1024 * 1024  # 200 MB
BLOCK_SIZE = 1024 * 1024  # 1 MB blocks

FILE_FLAG_WRITE_THROUGH = 0x80000000
GENERIC_WRITE = 0x40000000
CREATE_ALWAYS = 2

USB_LABELS = {
    "USB 2.0": (0, 40),
    "USB 3.0": (40, 500),
    "USB 3.1": (500, 1100),
    "USB 3.2": (1100, 2500),
    "USB4": (2500, 10000),
}


def _estimate_usb_version(speed_mbs):
    for label, (lo, hi) in USB_LABELS.items():
        if lo <= speed_mbs < hi:
            return label
    return "Desconegut / SSD intern"


class SpeedWorker(QThread):
    progress = Signal(int, int, str)
    finished = Signal(float, float)

    def __init__(self, path, parent=None):
        super().__init__(parent)
        self.path = path
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        test_file = os.path.join(self.path, ".jmcomander_usb_test.tmp")
        try:
            data = os.urandom(BLOCK_SIZE)
            total_written = 0

            handle = ctypes.windll.kernel32.CreateFileW(
                test_file,
                GENERIC_WRITE,
                0,
                None,
                CREATE_ALWAYS,
                FILE_FLAG_WRITE_THROUGH,
                None,
            )
            if handle == -1 or handle is None:
                self.finished.emit(-1, 0)
                return

            try:
                start = time.perf_counter()
                blocks = TEST_SIZE // BLOCK_SIZE
                for i in range(blocks):
                    if self._cancelled:
                        return
                    written = ctypes.c_ulong(0)
                    ctypes.windll.kernel32.WriteFile(
                        handle, data, BLOCK_SIZE, ctypes.byref(written), None
                    )
                    total_written += written.value
                    pct = int((i + 1) / blocks * 100)
                    self.progress.emit(pct, 100, f"Escrivint {i + 1}/{blocks} MB")
                elapsed = time.perf_counter() - start
            finally:
                ctypes.windll.kernel32.CloseHandle(handle)

            speed_mbs = total_written / (1000 * 1000) / elapsed if elapsed > 0 else 0
            self.finished.emit(speed_mbs, elapsed)
        except Exception:  # noqa: BLE001
            self.finished.emit(-1, 0)
        finally:
            try:
                if os.path.exists(test_file):
                    os.remove(test_file)
            except Exception:  # noqa: BLE001
                pass


def register(api):
    pass


def run_usb_speed(api):
    path = api.active_panel.current_path
    parent = api.get_parent_window()

    dlg = QDialog(parent)
    dlg.setWindowTitle("Test de Velocitat USB")
    dlg.resize(450, 160)
    layout = QVBoxLayout(dlg)

    title = QLabel(f"Provant velocitat d'escriptura a:\n{path}")
    title.setStyleSheet("font-weight: bold; padding: 5px;")
    layout.addWidget(title)

    bar = QProgressBar()
    bar.setRange(0, 100)
    layout.addWidget(bar)

    status = QLabel("Preparant...")
    layout.addWidget(status)

    btn_layout = QHBoxLayout()
    btn_cancel = QPushButton("Cancel·lar")
    btn_close = QPushButton("Tancar")
    btn_close.hide()
    btn_layout.addStretch()
    btn_layout.addWidget(btn_cancel)
    btn_layout.addWidget(btn_close)
    layout.addLayout(btn_layout)

    dlg.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

    worker = SpeedWorker(path)

    def on_progress(pct, total, text):
        bar.setValue(pct)
        status.setText(text)

    def on_finished(speed_mbs, elapsed):
        btn_cancel.hide()
        btn_close.show()
        bar.hide()

        if speed_mbs < 0:
            status.setText("Error durant el test.")
            dlg.layout().addWidget(QLabel("No s'ha pogut completar el test."))
            return

        usb_version = _estimate_usb_version(speed_mbs)

        result_text = (
            f"<h2>Resultat</h2>"
            f"<p><b>Velocitat d'escriptura:</b> {speed_mbs:.1f} MB/s</p>"
            f"<p><b>Temps:</b> {elapsed:.2f} s</p>"
            f"<p><b>Estimació:</b>"
            f" <span style='font-size:14pt;"
            f" color:#1565C0;'>{usb_version}</span></p>"
            f"<hr><p style='font-size:10px; color:#999;'>"
            f"USB 2.0: &lt;40 MB/s | USB 3.0: 40-500 MB/s<br>"
            f"USB 3.1: 500-1100 MB/s | USB 3.2: 1100-2500 MB/s<br>"
            f"USB4: &gt;2500 MB/s</p>"
        )
        result = QLabel(result_text)
        result.setTextFormat(Qt.TextFormat.RichText)
        result.setWordWrap(True)
        dlg.layout().addWidget(result)

    worker.progress.connect(on_progress)
    worker.finished.connect(on_finished)
    btn_cancel.clicked.connect(lambda: (worker.cancel(), dlg.reject()))
    btn_close.clicked.connect(dlg.accept)

    worker.start()
    dlg.exec()
