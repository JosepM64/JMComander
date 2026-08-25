import os  # noqa: INP001

from PySide6.QtWidgets import QCheckBox, QDialog, QDialogButtonBox, QLabel, QVBoxLayout


def register(api):
    pass


def compare_dirs(api):
    left_path = api.active_panel.current_path
    right_path = api.passive_panel.current_path

    if left_path == right_path:
        api.show_message("Ambos paneles están en la misma carpeta.", "warning")
        return

    parent = api.get_parent_window()
    dialog = QDialog(parent)
    dialog.setWindowTitle("Comparar directorios")
    dialog.setMinimumWidth(400)
    layout = QVBoxLayout()
    layout.addWidget(QLabel("Opciones de comparación:"))
    recursive_cb = QCheckBox("Comparar subdirectorios recursivamente")
    recursive_cb.setChecked(False)
    layout.addWidget(recursive_cb)
    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)
    dialog.setLayout(layout)

    if not dialog.exec():
        return

    result = api.compare_paths(left_path, right_path, recursive_cb.isChecked())

    if "error" in result:
        api.show_message(result["error"], "error")
        return

    only_left = result["only_in_1"]
    only_right = result["only_in_2"]
    different = result.get("different", [])
    same = result.get("same", [])

    # Count dirs vs files
    left_dirs = sum(1 for f in only_left if f.endswith("/"))
    left_files = len(only_left) - left_dirs
    right_dirs = sum(1 for f in only_right if f.endswith("/"))
    right_files = len(only_right) - right_dirs

    msg = (
        f"Resultados de la comparación:\n\n"
        f"Solo en IZQUIERDO: {len(only_left)} elements"
        f" ({left_files} fitxers, {left_dirs} carpetes)\n"
        f"Solo en DERECHO: {len(only_right)} elements"
        f" ({right_files} fitxers, {right_dirs} carpetes)\n"
        f"Modificats/diferents: {len(different)} fitxers\n"
        f"Idèntics: {len(same)} fitxers\n\n"
        f"Seleccionar els elements únics i diferents a cada panel?"
    )

    if api.confirm(msg):
        left_paths = []
        right_paths = []
        for f in only_left:
            rel = f.replace("/", os.sep).rstrip(os.sep)
            left_paths.append(os.path.normpath(os.path.join(left_path, rel)))
        for f in only_right:
            rel = f.replace("/", os.sep).rstrip(os.sep)
            right_paths.append(os.path.normpath(os.path.join(right_path, rel)))
        for f in different:
            rel = f.replace("/", os.sep).rstrip(os.sep)
            left_paths.append(os.path.normpath(os.path.join(left_path, rel)))
            right_paths.append(os.path.normpath(os.path.join(right_path, rel)))
        if left_paths:
            api.active_panel.select_paths(left_paths)
        if right_paths:
            api.passive_panel.select_paths(right_paths)
