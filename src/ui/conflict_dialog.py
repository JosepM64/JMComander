import os
from datetime import datetime, timezone

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QDialog, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from src.core.utils import format_size as _fmt


class ConflictDialog(QDialog):
    decision_made = Signal(str, bool)  # action, apply_all

    def __init__(self, parent=None, src=None, dst=None, index=0, total=1):
        super().__init__(parent)
        self.setWindowTitle("Conflicto de archivo")
        self.setMinimumWidth(450)

        # NON-MODAL: Don't block the main window
        self.setWindowModality(Qt.WindowModality.NonModal)

        # Stay on top so user can see it while working
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        self.src = src
        self.dst = dst
        self.index = index
        self.total = total

        layout = QVBoxLayout(self)

        filename = os.path.basename(dst) if dst else "archivo"
        layout.addWidget(QLabel(f"<h3 style='margin:0;'>{filename}</h3>"))
        layout.addWidget(QLabel(f"El archivo ya existe en el destino ({index + 1} de {total})"))

        # File Comparison Info
        comp_layout = QHBoxLayout()

        # Source Info
        src_frame = self._create_file_info_frame("Origen", src)
        # Destination Info
        dst_frame = self._create_file_info_frame("Destino", dst)

        comp_layout.addWidget(src_frame)
        comp_layout.addWidget(dst_frame)
        layout.addLayout(comp_layout)

        # Compare dates
        self.comparison_text = ""
        if src and dst and os.path.exists(src) and os.path.exists(dst):
            src_time = os.path.getmtime(src)
            dst_time = os.path.getmtime(dst)

            if src_time > dst_time:
                self.comparison_text = (
                    "<span style='color: #2e7d32; font-weight: bold;'>Origen más NUEVO</span>"
                )
            elif src_time < dst_time:
                self.comparison_text = (
                    "<span style='color: #d32f2f; font-weight: bold;'>Origen más ANTIGUO</span>"
                )
            else:
                self.comparison_text = (
                    "<span style='color: #666; font-weight: bold;'>Misma fecha</span>"
                )

            comp_label = QLabel(self.comparison_text)
            comp_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(comp_label)

        # Buttons: Todos, Solo los más antiguos, Cancelar
        btn_layout = QHBoxLayout()

        self.btn_all = QPushButton("Todos")
        self.btn_all.setStyleSheet(
            "background-color: #2196F3; color: white; padding: 10px 20px; font-weight: bold;"
        )
        self.btn_all.clicked.connect(self.on_all)

        self.btn_older = QPushButton("Solo los más antiguos")
        self.btn_older.setStyleSheet(
            "background-color: #FF9800; color: white; padding: 10px 20px; font-weight: bold;"
        )
        self.btn_older.clicked.connect(self.on_older)

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setStyleSheet(
            "background-color: #9E9E9E; color: white; padding: 10px 20px;"
        )
        self.btn_cancel.clicked.connect(self.on_cancel)

        btn_layout.addWidget(self.btn_all)
        btn_layout.addWidget(self.btn_older)
        btn_layout.addWidget(self.btn_cancel)

        layout.addLayout(btn_layout)

        layout.addStretch()

        self.action = None

    def _create_file_info_frame(self, title, path):
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)
        frame.setStyleSheet(
            "background-color: #f5f5f5; border-radius: 4px; border: 1px solid #ddd;"
        )
        flayout = QVBoxLayout(frame)

        title_label = QLabel(f"<b>{title}</b>")
        flayout.addWidget(title_label)

        if path and os.path.exists(path):
            size = os.path.getsize(path)
            mtime = os.path.getmtime(path)
            date_str = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")  # noqa: UP017
            size_str = self._format_size(size)

            flayout.addWidget(QLabel(f"Fecha: {date_str}"))
            flayout.addWidget(QLabel(f"Tamaño: {size_str}"))
        else:
            flayout.addWidget(QLabel("No disponible"))

        return frame

    def _format_size(self, b):

        return _fmt(b)

    def on_all(self):
        self.action = "overwrite"
        self.decision_made.emit("overwrite", True)
        self.close()

    def on_older(self):
        self.action = "overwrite_if_newer"
        self.decision_made.emit("overwrite_if_newer", True)
        self.close()

    def on_cancel(self):
        self.action = "cancel"
        self.decision_made.emit("cancel", False)
        self.close()

    def closeEvent(self, event):  # noqa: N802
        if self.action is None:
            self.decision_made.emit("cancel", False)
        event.accept()
