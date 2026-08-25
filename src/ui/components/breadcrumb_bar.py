import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)


class PathInputDialog(QDialog):
    """Diálogo simple para introducir una ruta."""

    def __init__(self, current_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Navegar a...")
        self.setMinimumWidth(450)

        layout = QVBoxLayout(self)

        self.line_edit = QLineEdit(current_path)
        font = QFont("Consolas", 10)
        self.line_edit.setFont(font)
        layout.addWidget(self.line_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.line_edit.setFocus()
        self.line_edit.selectAll()

    def get_path(self):
        return self.line_edit.text().strip()


class BreadcrumbBar(QWidget):
    """
    Barra de path estilo Altap Salamander:
    - Muestra el path completo con carpetas clickeables
    - Doble clic abre diálogo para nueva ruta
    """

    path_changed = Signal(str)
    MAX_VISIBLE_PARTS = 4
    MAX_BUTTON_WIDTH = 120

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_path = ""
        self._full_parts = []
        self._cumulative_paths = []

        self.setContentsMargins(2, 2, 2, 2)
        self.setFixedHeight(28)
        self.setMinimumWidth(200)

        self._layout = QHBoxLayout(self)
        self._layout.setSpacing(0)
        self._layout.setContentsMargins(4, 0, 4, 0)

        # Container para los botones
        self._container = QWidget()
        self._container_layout = QHBoxLayout(self._container)
        self._container_layout.setSpacing(0)
        self._container_layout.setContentsMargins(0, 0, 0, 0)

        self._layout.addWidget(self._container)
        self._layout.addStretch(0)

    def set_path(self, path: str):
        if path == self._current_path:
            return
        self._current_path = path
        self._full_parts = self._split_path(path)
        self._cumulative_paths = self._build_cumulative_paths(self._full_parts)
        self._rebuild()

    def path(self) -> str:
        return self._current_path

    def _build_cumulative_paths(self, parts):
        """Construye los paths acumulativos para cada parte."""
        cumulative = []
        for i, part in enumerate(parts):
            if i == 0:
                cumulative.append(part)
            else:
                cumulative.append(os.path.join(cumulative[-1], part))
        return cumulative

    def _get_visible_parts(self):
        """Devuelve los índices de partes visibles (inicio, ellipsis, final)."""
        n = len(self._full_parts)
        if n <= self.MAX_VISIBLE_PARTS:
            return list(range(n))

        # Siempre mostrar primera parte (unidad), ellipsis, y últimas MAX-1 partes
        last_count = self.MAX_VISIBLE_PARTS - 1
        visible = [0]  # Primera parte (unidad)
        visible.append("ellipsis")  # Marker para ellipsis
        visible.extend(range(n - last_count, n))  # Últimas partes
        return visible

    def _rebuild(self):
        # Limpiar botones anteriores — desvincular visualment abans d'eliminar
        while self._container_layout.count():
            item = self._container_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        if not self._current_path:
            return

        # Obtener índices de partes visibles
        visible_indices = self._get_visible_parts()

        # Crear botones para partes visibles
        prev_idx = None
        for idx in visible_indices:
            # Añadir separador antes de cada parte (excepto primera)
            if prev_idx is not None:
                if prev_idx == 0 and idx == "ellipsis":
                    pass  # No separador antes de ellipsis si es segundo elemento
                elif prev_idx == "ellipsis" or idx != "ellipsis":
                    sep = QLabel("›")
                    sep.setStyleSheet(
                        "color: #666; font-weight: bold;"
                        " font-family: Consolas, monospace; font-size: 10px;"
                    )
                    self._container_layout.addWidget(sep)

            if idx == "ellipsis":
                # Botón ellipsis para mostrar tooltip con path completo
                btn = QToolButton()
                btn.setText("...")
                btn.setAutoRaise(True)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setToolTip(self._current_path)
                btn.setStyleSheet("""
                    QToolButton {
                        background: transparent;
                        border: none;
                        padding: 1px 2px;
                        font-family: Consolas, monospace;
                        font-size: 11px;
                        font-weight: bold;
                        color: #666;
                    }
                    QToolButton:hover {
                        background: rgba(0, 100, 200, 40);
                        border-radius: 2px;
                    }
                """)
                # Click en ... muestra diálogo
                btn.clicked.connect(self._show_path_dialog)
                self._container_layout.addWidget(btn)
            else:
                part = self._full_parts[idx]
                cumulative = self._cumulative_paths[idx]

                btn = QToolButton()
                btn.setText(part)
                btn.setAutoRaise(True)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setMaximumWidth(self.MAX_BUTTON_WIDTH)
                btn.setToolTip(cumulative)
                btn.setStyleSheet("""
                    QToolButton {
                        background: transparent;
                        border: none;
                        padding: 1px 2px;
                        font-family: Consolas, Courier New, monospace;
                        font-size: 11px;
                        color: #1a1a1a;
                    }
                    QToolButton:hover {
                        background: rgba(0, 100, 200, 40);
                        border-radius: 2px;
                    }
                """)
                btn.clicked.connect(lambda _checked, p=cumulative: self.path_changed.emit(p))
                self._container_layout.addWidget(btn)

            prev_idx = idx

    def _split_path(self, path):
        """Divide el path en partes."""
        if not path:
            return []

        # Windows: manejar drive
        drive, tail = os.path.splitdrive(path)
        if drive:
            parts = [drive + os.sep]
            tail = tail.lstrip(os.sep)
            if tail:
                parts.extend([p for p in tail.split(os.sep) if p])
            return parts

        # Unix
        if path == "/":
            return ["/"]

        parts = [p for p in path.split("/") if p]
        if path.startswith("/"):
            parts.insert(0, "/")

        return parts

    def mouseDoubleClickEvent(self, event):  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._show_path_dialog()
        super().mouseDoubleClickEvent(event)

    def _show_path_dialog(self):
        dialog = PathInputDialog(self._current_path, self)
        if dialog.exec():
            new_path = dialog.get_path()
            if new_path and os.path.isdir(new_path):
                self.path_changed.emit(new_path)
