"""
Diàleg de borrat segur.

Permet triar el mètode d'esborrat (sobreescriure el contingut abans de
suprimir) i el nombre de passades, mostrant què s'esborrarà i de quina
mida. La lògica de borrat en si viu a `src/core/secure_delete.py`.
"""

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QListWidget,
    QSpinBox,
    QVBoxLayout,
)

from src.core.secure_delete import SecureDelete

# (id intern, text visible)
METHODS = [
    ("auto", "Automàtic (recomanat)"),
    ("hdd", "Sobrescriure el fitxer (HDD)"),
    ("ssd", "Sobrescriure amb dades aleatòries (SSD)"),
    ("quick", "Ràpid (sense sobrescriure)"),
]

_MAX_LIST = 200


def human_size(num_bytes: float) -> str:
    """Converteix un nombre de bytes en una mida llegible."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def path_size(path: str) -> int:
    """Mida total en bytes d'un fitxer o d'una carpeta (recursiva)."""
    if os.path.isfile(path):
        try:
            return os.path.getsize(path)
        except OSError:
            return 0
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                continue
    return total


class SecureDeleteDialog(QDialog):
    """Configura el mètode de borrat segur abans de suprimir els elements."""

    def __init__(self, parent, paths: list[str]):
        super().__init__(parent)
        self.setWindowTitle("Borrado seguro")
        self.setMinimumWidth(560)
        self._paths = list(paths)
        self._is_ssd = False
        self._setup_ui()
        self._fill_items()
        self._detect_disk()
        self._update_hint()

    # --- UI ---------------------------------------------------------------
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        title = QLabel("<b>Borrat segur</b> — el contingut es sobreescriu abans d'esborrar.")
        layout.addWidget(title)

        self.list_widget = QListWidget()
        self.list_widget.setMinimumHeight(150)
        self.list_widget.setAlternatingRowColors(True)
        layout.addWidget(self.list_widget)

        self.size_label = QLabel()
        self.size_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.size_label)

        options = QGroupBox("Mètode")
        form = QFormLayout(options)

        self.method_combo = QComboBox()
        for method_id, text in METHODS:
            self.method_combo.addItem(text, method_id)
        self.method_combo.currentIndexChanged.connect(self._update_hint)
        form.addRow("Tecnica:", self.method_combo)

        self.passes_spin = QSpinBox()
        self.passes_spin.setRange(1, 10)
        self.passes_spin.setValue(3)
        self.passes_spin.setSuffix(" passades")
        form.addRow("Sobreescriptura:", self.passes_spin)

        layout.addWidget(options)

        self.disk_label = QLabel()
        self.disk_label.setStyleSheet("color: #555;")
        layout.addWidget(self.disk_label)

        self.hint_label = QLabel()
        self.hint_label.setWordWrap(True)
        self.hint_label.setStyleSheet("color: #8a5a00; background: #fff8e1;"
                                      " border: 1px solid #ffe0a0; padding: 6px;")
        layout.addWidget(self.hint_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Borrar")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancel·lar")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # --- contingut --------------------------------------------------------
    def _fill_items(self):
        total = 0
        for path in self._paths[:_MAX_LIST]:
            size = path_size(path)
            total += size
            is_dir = os.path.isdir(path)
            name = os.path.basename(path) or path
            self.list_widget.addItem(
                f"{'[D]' if is_dir else '   '} {name}    ({human_size(size)})"
            )
        if len(self._paths) > _MAX_LIST:
            self.list_widget.addItem(f"... i {len(self._paths) - _MAX_LIST} elements més")
        self.size_label.setText(
            f"{len(self._paths)} element(s) · {human_size(total)} en total"
        )

    def _detect_disk(self):
        try:
            self._is_ssd = SecureDelete.is_ssd(self._paths[0])
        except Exception:  # noqa: BLE001
            self._is_ssd = False
        if self._is_ssd:
            self.disk_label.setText("Unitat detectada: SSD")
        else:
            self.disk_label.setText("Unitat detectada: HDD (o no detectada)")

    def _update_hint(self):
        method = self.method_combo.currentData()
        # Les passades només tenen sentit en la sobrescriptura clàssica
        self.passes_spin.setEnabled(method in ("auto", "hdd"))
        if method == "quick":
            text = (
                "Ràpid: només s'esborra el fitxer, sense sobreescriure. "
                "Ràpid però NOprotegeix el contingut."
            )
        elif method == "hdd":
            text = (
                "Sobreescriure el fitxer tantes passades com indiquis abans d'esborrar. "
                "Molt lent en fitxers grans."
            )
        elif method == "ssd":
            text = (
                "En SSD la sobrescriptura no garanteix la destrucció del contingut "
                "(wear levelling). S'escriu un patró aleatori i s'esborra."
            )
        else:
            text = (
                "Automàtic: s'adapta al tipus de unitat detectat. "
                "En HDD sobreescriu; en SSD escriu dades aleatòries."
            )
        self.hint_label.setText(text)
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

    # --- resultat ---------------------------------------------------------
    def params(self) -> dict:
        """Paràmetres per a `SecureDeleteJob`."""
        return {
            "method": self.method_combo.currentData(),
            "passes": self.passes_spin.value(),
        }
