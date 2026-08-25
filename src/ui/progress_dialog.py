import logging
import sys

from PySide6.QtCore import QCoreApplication, Qt, QTimer
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout

from src.core.utils import format_size as _fmt

logger = logging.getLogger(__name__)


class ProgressDialog(QDialog):
    def __init__(self, title="Operación en progreso", _total_files=0, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setFixedSize(400, 150)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowModality(Qt.WindowModality.NonModal)

        self._taskbar_button = None
        self._taskbar_progress = None
        self._init_taskbar()

        self.setStyleSheet("""
            QDialog { background-color: #ffffff; }
            QLabel { font-size: 12px; }
            QProgressBar {
                border: 2px solid #1976D2;
                border-radius: 4px;
                text-align: center;
                min-height: 24px;
                background-color: #e3f2fd;
            }
            QProgressBar::chunk { background-color: #1976D2; }
            QPushButton {
                padding: 6px 16px;
                border-radius: 4px;
                font-size: 12px;
                min-width: 110px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #1565C0;")
        layout.addWidget(self.title_label)

        self.file_label = QLabel("Preparando...")
        self.file_label.setStyleSheet("color: #333;")
        layout.addWidget(self.file_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        layout.addWidget(self.progress_bar)

        self.info_label = QLabel("")
        self.info_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self.info_label)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.minimize_btn = QPushButton("Minimizar")
        self.minimize_btn.setStyleSheet("""
            QPushButton {
                background-color: #e3f2fd;
                color: #1565C0;
                border: 1px solid #90caf9;
                min-width: 110px;
                min-height: 32px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #bbdefb; }
        """)
        self.minimize_btn.clicked.connect(self.showMinimized)
        btn_layout.addWidget(self.minimize_btn)

        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Cancelar")
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                min-width: 110px;
                min-height: 32px;
                padding: 8px 16px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #d32f2f; }
        """)
        self.cancel_btn.clicked.connect(self.on_cancel)
        btn_layout.addWidget(self.cancel_btn)

        layout.addLayout(btn_layout)

        self.job = None
        self.is_cancelled = False
        self.is_finished = False
        self._parent = parent

        # Cola de actualizaciones pendientes
        self._pending_text = None
        self._pending_percent = None
        self._last_displayed_percent = -1

        # Timer para actualizar la UI periódicamente (cada 100ms para reducir overhead)
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._flush_progress)
        self._update_timer.setInterval(100)

    def _init_taskbar(self):
        """Inicializar progreso en la barra de tareas de Windows (ctypes)"""
        self._taskbar = None
        if sys.platform != "win32":
            return
        try:
            from ctypes import windll

            self._taskbar = windll.shell32.ITaskbarList3()
            self._taskbar.HrInit()
        except Exception:
            self._taskbar = None

    def _flush_progress(self):
        """Update UI amb la ultima actualitzacio acumulada."""
        if (
            self._pending_percent is not None
            and self._pending_percent != self._last_displayed_percent
        ):
            self.progress_bar.setValue(self._pending_percent)
            self._last_displayed_percent = self._pending_percent
            self._update_taskbar(self._pending_percent)
        if self._pending_text is not None:
            self.file_label.setText(self._pending_text)

    def _update_taskbar(self, percent):
        """Actualizar progreso en la barra de tareas"""
        if not self._taskbar:
            return
        try:
            hwnd = int(self.winId())
            # TBPF_NORMAL = 0x2
            self._taskbar.SetProgressState(hwnd, 0x2)
            self._taskbar.SetProgressValue(hwnd, percent, 100)
        except Exception:
            pass

    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        self._update_timer.start()

    def set_job(self, job):
        self.job = job
        self.total_bytes = 0
        self.copied_bytes = 0
        job.signals.progress.connect(self._on_progress)
        job.signals.total_size.connect(self._on_total_size)
        job.signals.file_started.connect(self._on_file_started)
        job.signals.finished.connect(self._on_finished)
        job.signals.error.connect(self._on_error)
        job.signals.cancelled.connect(self._on_cancelled)

    def _on_progress(self, text, percent):
        """Recibir actualización de progreso del worker"""
        logger.info("[ProgressDialog] _on_progress: %s, %s", text, percent)
        self._pending_text = text
        self._pending_percent = min(100, max(0, int(percent)))

    def _on_total_size(self, total_bytes):
        """Rebre mida total i mostrar en l'etiqueta d'info"""
        self.total_bytes = total_bytes
        size_str = self._format_size(total_bytes)
        self.info_label.setText(f"Total: {size_str}")

    def _format_size(self, size):

        return _fmt(size)

    def _on_file_started(self, _filename, current, total):
        self.info_label.setText(f"Archivo {current} de {total}")

    def _clear_taskbar(self):
        """Limpiar progreso de la barra de tareas"""
        if not self._taskbar:
            return
        try:
            hwnd = int(self.winId())
            # TBPF_NOPROGRESS = 0
            self._taskbar.SetProgressState(hwnd, 0)
        except Exception:
            pass

    def _on_finished(self):
        logger.info("[ProgressDialog] _on_finished called")
        if self._update_timer:
            self._update_timer.stop()
            self._update_timer.deleteLater()
            self._update_timer = None

        self.is_finished = True
        self._pending_percent = 100
        self._flush_progress()
        self.file_label.setText("Operación completada")
        self.file_label.setStyleSheet("color: #4caf50; font-weight: bold;")
        self.minimize_btn.setVisible(False)
        self.cancel_btn.setVisible(False)

        if self._parent:
            try:
                if hasattr(self._parent, "left_panel"):
                    self._parent.left_panel.refresh()
                if hasattr(self._parent, "right_panel"):
                    self._parent.right_panel.refresh()
            except Exception as _e:  # noqa: BLE001
                pass

        QTimer.singleShot(1000, self.close)

    def _on_error(self, msg):
        if self._update_timer:
            self._update_timer.stop()
            self._update_timer.deleteLater()
            self._update_timer = None
        self.file_label.setText(f"Error: {msg}")
        self.file_label.setStyleSheet("color: red; font-weight: bold;")
        self._clear_taskbar()

    def _on_cancelled(self):
        if self._update_timer:
            self._update_timer.stop()
            self._update_timer.deleteLater()
            self._update_timer = None
        self.is_cancelled = True
        self.file_label.setText("Operación cancelada")
        self.file_label.setStyleSheet("color: orange;")
        self.progress_bar.setEnabled(False)
        self._clear_taskbar()
        self.minimize_btn.setVisible(False)
        self.cancel_btn.setVisible(False)
        QTimer.singleShot(1500, self.close)

    def on_cancel(self):
        self.is_cancelled = True
        if self.job:
            self.job.cancel()
        self.file_label.setText("Cancelando...")
        self.cancel_btn.setEnabled(False)

    def changeEvent(self, event):  # noqa: N802
        super().changeEvent(event)
        if event.type() == event.Type.WindowStateChange:
            if self.windowState() & Qt.WindowState.WindowMinimized:
                # Window minimized - taskbar progress still visible
                pass
            # Window restored - ensure taskbar progress is visible
            elif self._pending_percent is not None:
                self._update_taskbar(self._pending_percent)

    def closeEvent(self, event):  # noqa: N802
        try:
            if hasattr(self, "_update_timer") and self._update_timer:
                self._update_timer.stop()
        except RuntimeError:
            pass
        self._clear_taskbar()
        if not self.is_finished and not self.is_cancelled and self.job:
            event.ignore()
            self.showMinimized()
        else:
            event.accept()

    def reject(self):
        try:
            if hasattr(self, "_update_timer") and self._update_timer:
                self._update_timer.stop()
        except RuntimeError:
            pass
        if not self.is_finished and not self.is_cancelled and self.job:
            self.showMinimized()
        else:
            super().reject()
