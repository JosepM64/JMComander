import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSizePolicy,
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
    Barra de path compacta estilo Altap Salamander:
    - Muestra el path con carpetas clickeables, sin botones que se estiren
    - Se adapta al ancho disponible (unidades + … + últimas carpetas)
    - Doble clic abre diálogo para escribir una ruta
    """

    path_changed = Signal(str)
    BAR_HEIGHT = 22
    BUTTON_HEIGHT = 18
    BUTTON_PADDING = 10  # px totals (esquerra + dreta)
    MAX_BUTTON_WIDTH = 160
    SEPARATOR = "›"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_path = ""
        self._full_parts = []
        self._cumulative_paths = []
        self._last_width = 0

        self._font = QFont("Segoe UI", 9)
        self.setFont(self._font)
        self._fm = QFontMetrics(self._font)

        self.setContentsMargins(0, 0, 0, 0)
        self.setFixedHeight(self.BAR_HEIGHT)
        self.setMinimumWidth(160)

        self._layout = QHBoxLayout(self)
        self._layout.setSpacing(0)
        self._layout.setContentsMargins(2, 0, 2, 0)

        # Container para los botones (no se estiran: ancho = contenido)
        self._container = QWidget()
        self._container_layout = QHBoxLayout(self._container)
        self._container_layout.setSpacing(0)
        self._container_layout.setContentsMargins(0, 0, 0, 0)
        self._container_layout.addStretch(1)

        self._layout.addWidget(self._container, 1)

    def set_path(self, path: str):
        if path == self._current_path:
            return
        self._current_path = path
        self._full_parts = self._split_path(path)
        self._cumulative_paths = self._build_cumulative_paths(self._full_parts)
        self._rebuild()

    def path(self) -> str:
        return self._current_path

    def resizeEvent(self, event):  # noqa: N802
        super().resizeEvent(event)
        width = event.size().width()
        # Només reconstruïm si l'amplada canvia prou: evita rebuilds en bucle.
        if abs(width - self._last_width) > 16:
            self._last_width = width
            if self._current_path:
                self._rebuild()

    def _build_cumulative_paths(self, parts):
        """Construye los paths acumulativos para cada parte."""
        cumulative = []
        for i, part in enumerate(parts):
            if i == 0:
                cumulative.append(part)
            else:
                cumulative.append(os.path.join(cumulative[-1], part))
        return cumulative

    def _text_width(self, text: str) -> int:
        return min(
            self._fm.horizontalAdvance(text) + self.BUTTON_PADDING,
            self.MAX_BUTTON_WIDTH,
        )

    def _separator_width(self) -> int:
        return self._fm.horizontalAdvance(self.SEPARATOR) + 2

    def _get_visible_parts(self):
        """Devuelve las partes visibles según el ancho disponible."""
        n = len(self._full_parts)
        if n == 0:
            return []

        available = max(self.width() - 8, 120)
        sep = self._separator_width()
        full_width = sum(self._text_width(p) for p in self._full_parts) + sep * (n - 1)
        if full_width <= available:
            return list(range(n))

        # Unidad + "..." + tantes carpetes finals com càpiguen.
        used = self._text_width(self._full_parts[0]) + self._text_width("...") + sep
        suffix = []
        for i in range(n - 1, 0, -1):
            width = self._text_width(self._full_parts[i]) + sep
            if used + width > available:
                break
            used += width
            suffix.insert(0, i)

        if not suffix:
            # Ni una carpeta final hi cap: mostra almenys l'última.
            return [0, "ellipsis", n - 1]
        if suffix[0] == 1:
            # No hi ha res ocult al mig: no calen els punts suspensius.
            return [0, *suffix]
        return [0, "ellipsis", *suffix]

    def _button_style(self):
        return """
            QToolButton {
                background: transparent;
                border: none;
                padding: 0px 4px;
                margin: 0px;
                color: #1a1a1a;
            }
            QToolButton:hover {
                background: rgba(25, 118, 210, 55);
                border-radius: 3px;
            }
            QToolButton:pressed {
                background: rgba(25, 118, 210, 90);
                border-radius: 3px;
            }
        """

    def _make_button(self, text: str) -> QToolButton:
        btn = QToolButton()
        btn.setText(
            self._fm.elidedText(
                text,
                Qt.TextElideMode.ElideMiddle,
                self.MAX_BUTTON_WIDTH - self.BUTTON_PADDING,
            )
        )
        btn.setAutoRaise(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFixedHeight(self.BUTTON_HEIGHT)
        btn.setFixedWidth(self._text_width(text))
        btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        btn.setStyleSheet(self._button_style())
        return btn

    def _make_separator(self) -> QLabel:
        sep = QLabel(self.SEPARATOR)
        sep.setFixedHeight(self.BUTTON_HEIGHT)
        sep.setFixedWidth(self._separator_width())
        sep.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sep.setStyleSheet("color: #78909c; background: transparent;")
        return sep

    def _rebuild(self):
        # Limpiar botones anteriores — desvincular visualment abans d'eliminar
        while self._container_layout.count():
            item = self._container_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        if not self._current_path:
            self._container_layout.addStretch(1)
            return

        visible_indices = self._get_visible_parts()

        prev_idx = None
        for idx in visible_indices:
            # Separador entre parts (excepte la primera)
            if prev_idx is not None:
                self._container_layout.addWidget(self._make_separator())

            if idx == "ellipsis":
                btn = self._make_button("...")
                btn.setToolTip(self._current_path)
                btn.clicked.connect(self._show_path_dialog)
            else:
                part = self._full_parts[idx]
                cumulative = self._cumulative_paths[idx]
                btn = self._make_button(part)
                btn.setToolTip(cumulative)
                btn.clicked.connect(lambda _checked, p=cumulative: self.path_changed.emit(p))

            self._container_layout.addWidget(btn)
            prev_idx = idx

        # L'espai sobrant queda a la dreta (no estira els botons)
        self._container_layout.addStretch(1)

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
