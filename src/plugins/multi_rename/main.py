import os  # noqa: INP001
import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)


class MultiRenameDialog(QDialog):
    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Renombrado Masivo")
        self.resize(800, 600)
        self.items = items
        layout = QVBoxLayout(self)
        grp_opts = QGroupBox("Reglas de Renombrado")
        opts_layout = QVBoxLayout(grp_opts)
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Buscar:"))
        self.input_find = QLineEdit()
        self.input_find.textChanged.connect(self.preview)
        row1.addWidget(self.input_find)
        row1.addWidget(QLabel("Reemplazar:"))
        self.input_replace = QLineEdit()
        self.input_replace.textChanged.connect(self.preview)
        row1.addWidget(self.input_replace)
        opts_layout.addLayout(row1)
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Prefijo:"))
        self.input_prefix = QLineEdit()
        self.input_prefix.textChanged.connect(self.preview)
        row2.addWidget(self.input_prefix)
        row2.addWidget(QLabel("Sufijo:"))
        self.input_suffix = QLineEdit()
        self.input_suffix.textChanged.connect(self.preview)
        row2.addWidget(self.input_suffix)
        opts_layout.addLayout(row2)
        row3 = QHBoxLayout()
        self.chk_counter = QCheckBox("Añadir contador")
        self.chk_counter.toggled.connect(self.preview)
        row3.addWidget(self.chk_counter)
        self.spin_start = QSpinBox()
        self.spin_start.setValue(1)
        self.spin_start.valueChanged.connect(self.preview)
        row3.addWidget(QLabel("Inicio:"))
        row3.addWidget(self.spin_start)
        row3.addWidget(QLabel("Formato:"))
        self.combo_counter_format = QComboBox()
        self.combo_counter_format.addItems(["001", "01", "1"])
        self.combo_counter_format.currentTextChanged.connect(self.preview)
        row3.addWidget(self.combo_counter_format)
        opts_layout.addLayout(row3)
        row4 = QHBoxLayout()
        self.chk_regex = QCheckBox("Usar expresiones regulares")
        self.chk_regex.toggled.connect(self.preview)
        row4.addWidget(self.chk_regex)
        self.chk_case = QCheckBox("Diferenciar mayúsculas/minúsculas")
        self.chk_case.setChecked(True)
        self.chk_case.toggled.connect(self.preview)
        row4.addWidget(self.chk_case)
        opts_layout.addLayout(row4)
        layout.addWidget(grp_opts)
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Nombre Original", "Nuevo Nombre"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table)
        btn_layout = QHBoxLayout()
        btn_apply = QPushButton("Aplicar")
        btn_apply.clicked.connect(self.apply_rename)
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_apply)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)
        self.preview()

    def generate_new_name(self, original_name, index):
        name, ext = os.path.splitext(original_name)
        find_txt = self.input_find.text()
        replace_txt = self.input_replace.text()
        if find_txt:
            if self.chk_regex.isChecked():
                flags = 0 if self.chk_case.isChecked() else re.IGNORECASE
                try:
                    name = re.sub(find_txt, replace_txt, name, flags=flags)
                except re.error:
                    # Si la regex es inválida, usar texto plano
                    name = name.replace(find_txt, replace_txt)
            elif self.chk_case.isChecked():
                name = name.replace(find_txt, replace_txt)
            else:
                # replace case-insensitive
                name = re.sub(re.escape(find_txt), replace_txt, name, flags=re.IGNORECASE)
        name = f"{self.input_prefix.text()}{name}{self.input_suffix.text()}"
        if self.chk_counter.isChecked():
            num = self.spin_start.value() + index
            fmt = self.combo_counter_format.currentText()
            if fmt == "001":
                num_str = f"{num:03d}"
            elif fmt == "01":
                num_str = f"{num:02d}"
            else:
                num_str = str(num)
            name = f"{name}_{num_str}"
        return f"{name}{ext}"

    def preview(self):
        self.table.setRowCount(len(self.items))
        for i, path in enumerate(self.items):
            original = os.path.basename(path)
            new_name = self.generate_new_name(original, i)
            self.table.setItem(i, 0, QTableWidgetItem(original))
            item_new = QTableWidgetItem(new_name)
            if original != new_name and os.path.exists(
                os.path.join(os.path.dirname(path), new_name)
            ):
                item_new.setBackground(Qt.GlobalColor.red)
            self.table.setItem(i, 1, item_new)

    def apply_rename(self):
        conflicts = []
        renames = []
        for i, path in enumerate(self.items):
            new_name = self.generate_new_name(os.path.basename(path), i)
            dst = os.path.join(os.path.dirname(path), new_name)
            if os.path.exists(dst):
                conflicts.append(new_name)
            else:
                renames.append((path, dst))

        if conflicts:
            msg = "Els següents fitxers ja existeixen i NO es renombraran:\n\n"
            msg += "\n".join(f"  • {c}" for c in conflicts[:20])
            if len(conflicts) > 20:
                msg += f"\n  ... i {len(conflicts) - 20} més"
            QMessageBox.warning(self, "Conflictes", msg)

        if not renames:
            return

        summary = f"Es renombraran {len(renames)} fitxer(s)."
        if QMessageBox.question(self, "Confirmar", summary) == QMessageBox.StandardButton.Yes:
            renamed_ok = 0
            errors = []
            for path, dst in renames:
                try:
                    os.rename(path, dst)
                    renamed_ok += 1
                except Exception as e:  # noqa: BLE001
                    errors.append(f"{os.path.basename(path)}: {e}")
            if errors:
                err_msg = f"Renombrats {renamed_ok} fitxers.\n\nErrors:\n"
                err_msg += "\n".join(errors[:10])
                if len(errors) > 10:
                    err_msg += f"\n... i {len(errors) - 10} més"
                QMessageBox.warning(self, "Errors", err_msg)
            if renamed_ok:
                self.accept()


def register(api):
    pass


def run_multi_rename(api):
    items = api.active_panel.get_selected_paths()
    if not items:
        QMessageBox.warning(api.get_parent_window(), "Aviso", "Selecciona archivos.")
        return
    MultiRenameDialog(items, api.get_parent_window()).exec()
    api.active_panel.refresh()
