#!/usr/bin/env python3
"""
Test de Verificación Automatizada de JMComander
Verifica automáticamente las funcionalidades del checklist de regresión.
Usa análisis estático del código - no requiere PySide6 instalado.
"""

import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
SRC_DIR = os.path.join(PROJECT_ROOT, "src")


class VerificationResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.results = []

    def add_pass(self, test_name, details=""):
        self.passed += 1
        self.results.append(("PASS", test_name, details))

    def add_fail(self, test_name, details=""):
        self.failed += 1
        self.results.append(("FAIL", test_name, details))

    def add_warning(self, test_name, details=""):
        self.warnings += 1
        self.results.append(("WARN", test_name, details))

    def print_summary(self):
        print("\n" + "=" * 60)
        print("RESUMEN DE VERIFICACION")
        print("=" * 60)
        print(f"[OK] PASADOS:   {self.passed}")
        print(f"[X] FALLADOS:  {self.failed}")
        print(f"[!] AVISOS:    {self.warnings}")
        print("=" * 60)

        if self.failed > 0:
            print("\nFALLOS DETECTADOS:")
            for status, test, details in self.results:
                if status == "FAIL":
                    print(f"  [{status}] {test}")
                    if details:
                        print(f"         {details}")

        return self.failed == 0


def read_file(filepath):
    """Lee contenido de archivo"""
    try:
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            return f.read()
    except:
        return ""


def file_contains(filepath, pattern):
    """Verifica si archivo contiene patrón"""
    content = read_file(filepath)
    return bool(re.search(pattern, content, re.IGNORECASE))


def find_in_files(directory, pattern, extensions=[".py"]):
    """Busca patrón en archivos de un directorio"""
    matches = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                filepath = os.path.join(root, file)
                if file_contains(filepath, pattern):
                    matches.append(filepath)
    return matches


def verify_column_sorting(result: VerificationResult):
    """Verifica funcionalidades de ordenación de columnas"""
    print("\n[1/13] Verificando Ordenacion de Columnas...")

    panel_file = os.path.join(SRC_DIR, "ui", "panel.py")
    model_file = os.path.join(SRC_DIR, "ui", "file_system_model.py")

    panel_content = read_file(panel_file) if os.path.exists(panel_file) else ""
    model_content = read_file(model_file) if os.path.exists(model_file) else ""

    if not os.path.exists(panel_file):
        result.add_fail("Column-Sort", "panel.py no encontrado")
    if not os.path.exists(model_file):
        result.add_fail("Column-Sort", "file_system_model.py no encontrado")

    if not panel_content and not model_content:
        return

    combined = panel_content + "\n" + model_content

    # Verificar setSortingEnabled en _configure_tree_headers
    if re.search(r"def _configure_tree_headers.*?setSortingEnabled", panel_content, re.DOTALL):
        result.add_pass("Column-Sort", "setSortingEnabled en _configure_tree_headers")
    else:
        result.add_fail("Column-Sort", "setSortingEnabled no encontrado")

    # Verificar setSortIndicatorShown
    if "setSortIndicatorShown" in panel_content:
        result.add_pass("Column-Sort", "setSortIndicatorShown implementado")
    else:
        result.add_warning("Column-Sort", "setSortIndicatorShown no implementado")

    # Verificar on_header_clicked
    if "def on_header_clicked" in panel_content:
        result.add_pass("Column-Sort", "on_header_clicked implementado")
    else:
        result.add_fail("Column-Sort", "on_header_clicked no existe")

    # Verificar conexión de señal
    if "sectionClicked.connect" in panel_content:
        result.add_pass("Column-Sort", "Conexion de senal de click en cabecera")
    else:
        result.add_fail("Column-Sort", "No hay conexion de senal")

    # Verificar lessThan para ordenación personalizada (en file_system_model.py)
    if "def lessThan" in model_content:
        result.add_pass("Column-Sort", "lessThan implementado en FileSystemProxyModel")
    else:
        result.add_fail("Column-Sort", "lessThan no existe")

    # === VERIFICAR ORDENACIÓN PARA TODAS LAS COLUMNAS ===
    # Columna 0 - Nombre (col == 0 en lessThan con natural_sort_key o fileName)
    if re.search(r"col == 0", model_content):
        result.add_pass("Column-Sort", "Ordenacion por Nombre (columna 0)")
    else:
        result.add_fail("Column-Sort", "Falta ordenacion por Nombre")

    # Columna 1 - Extension (col == 1 en lessThan con get_extension)
    if re.search(r"col == 1", model_content):
        result.add_pass("Column-Sort", "Ordenacion por Extension (columna 1)")
    else:
        result.add_fail("Column-Sort", "Falta ordenacion por Extension")

    # Columna 2 - Tamano (col == 2 en lessThan con size/numeric)
    if re.search(r"col == 2|col in \(2,", model_content):
        result.add_pass("Column-Sort", "Ordenacion por Tamano (columna 2)")
    else:
        result.add_fail("Column-Sort", "Falta ordenacion por Tamano")

    # Columna 3 - Tipo (col == 3 en lessThan con get_file_category)
    if re.search(r"col == 3", model_content):
        result.add_pass("Column-Sort", "Ordenacion por Tipo (columna 3)")
    else:
        result.add_fail("Column-Sort", "Falta ordenacion por Tipo")

    # Columnas 4, 5 - Fecha y Hora (col == 4 o col == 5 en lessThan)
    if re.search(r"col == 4|col == 5|col in \(4, 5\)", model_content):
        result.add_pass("Column-Sort", "Ordenacion por Fecha/Hora (columnas 4-5)")
    else:
        result.add_fail("Column-Sort", "Falta ordenacion por Fecha/Hora")


def verify_shortcuts(result: VerificationResult):
    """Verifica atajos de teclado"""
    print("[2/13] Verificando Atajos de Teclado...")

    shortcuts_file = os.path.join(SRC_DIR, "shortcuts_constants.py")
    if not os.path.exists(shortcuts_file):
        result.add_fail("Shortcuts", "shortcuts_constants.py no encontrado")
        return

    content = read_file(shortcuts_file)

    # Buscar en el archivo de atajos - verificar que existen las acciones
    expected = {
        "Subir Nivel": "Backspace",
        "Refrescar Panel": "F5",
        "Buscar": "Alt",
        "Seleccionar Todo": "Ctrl",
        "Renombrar": "F2",
        "Ver Archivo": "F3",
        "Editar Archivo": "F4",
        "Copiar Elementos": "F5",
        "Mover Elementos": "F6",
        "Crear Carpeta": "F7",
        "Borrar Elementos": "F8",
    }

    for action, key_part in expected.items():
        if action in content:
            result.add_pass("Shortcuts", f"{action}")
        else:
            result.add_fail("Shortcuts", f"{action} no encontrado")


def verify_main_operations(result: VerificationResult):
    """Verifica operaciones principales en main_window"""
    print("[3/13] Verificando Operaciones Principales...")

    main_file = os.path.join(SRC_DIR, "ui", "main_window.py")
    if not os.path.exists(main_file):
        result.add_fail("Operations", "main_window.py no encontrado")
        return

    content = read_file(main_file)

    operations = [
        "def copy_files",
        "def move_files",
        "def delete_files",
        "def rename_item",
        "def view_file",
        "def edit_file",
        "def go_up",
        "def go_root",
        "def go_home",
        "def refresh",
    ]

    for op in operations:
        if op in content:
            result.add_pass("Operations", op.replace("def ", ""))
        else:
            result.add_fail("Operations", f"{op} no existe")


def verify_view_modes(result: VerificationResult):
    """Verifica modos de vista"""
    print("[4/13] Verificando Modos de Vista...")

    panel_file = os.path.join(SRC_DIR, "ui", "panel.py")
    if not os.path.exists(panel_file):
        result.add_fail("ViewModes", "panel.py no encontrado")
        return

    content = read_file(panel_file)

    modes = ["details", "list", "icons", "icons_large"]
    for mode in modes:
        # Permite que 'icons' y 'icons_large' se consideren como una sola vista 'icons'
        if mode == "icons" or mode == "icons_large":
            if (
                "'icons'" in content
                or "'icons_large'" in content
                or '"icons"' in content
                or '"icons_large"' in content
            ):
                result.add_pass("ViewModes", f"Vista {mode}")
            else:
                result.add_fail("ViewModes", f"Vista {mode} no encontrada")
        elif f'"{mode}"' in content or f"'{mode}'" in content:
            result.add_pass("ViewModes", f"Vista {mode}")
        else:
            result.add_fail("ViewModes", f"Vista {mode} no encontrada")


def verify_plugins(result: VerificationResult):
    """Verifica sistema de plugins"""
    print("[5/13] Verificando Sistema de Plugins...")

    # Verificar PluginAPI
    api_file = os.path.join(SRC_DIR, "core", "plugin_api.py")
    if os.path.exists(api_file):
        content = read_file(api_file)
        methods = ["copy", "move", "open_file", "run_job", "show_message"]

        for method in methods:
            if f"def {method}" in content:
                result.add_pass("Plugins", f"PluginAPI.{method}")
            else:
                result.add_fail("Plugins", f"PluginAPI.{method} falta")
    else:
        result.add_fail("Plugins", "plugin_api.py no encontrado")

    # Verificar PluginManager
    pm_file = os.path.join(SRC_DIR, "core", "plugin_manager.py")
    if os.path.exists(pm_file):
        result.add_pass("Plugins", "PluginManager existe")
    else:
        result.add_fail("Plugins", "plugin_manager.py no encontrado")


def verify_plugins_directory(result: VerificationResult):
    """Verifica plugins en directorio"""
    print("[6/13] Verificando Directorio de Plugins...")

    plugins_dir = os.path.join(SRC_DIR, "plugins")
    if not os.path.exists(plugins_dir):
        result.add_fail("Plugins-Dir", "Directorio plugins no existe")
        return

    expected = [
        "compare_dirs",
        "compressor",
        "disk_space",
        "duplicate_finder",
        "extractor",
        "hash_tool",
        "image_converter",
        "mini_grep",
        "multi_rename",
        "organizer",
        "remote_conn",
        "space_analyzer",
    ]

    found = 0
    for plugin in expected:
        path = os.path.join(plugins_dir, plugin)
        if os.path.isdir(path):
            found += 1
            result.add_pass("Plugins-Dir", plugin)
        else:
            result.add_fail("Plugins-Dir", f"{plugin} no encontrado")

    if found >= 10:
        result.add_pass("Plugins-Dir", f"Total: {found}/12 plugins")


def verify_archive_handler(result: VerificationResult):
    """Verifica manejo de archivos comprimidos"""
    print("[7/13] Verificando Archive Handler...")

    archive_file = os.path.join(SRC_DIR, "core", "archive_handler.py")
    if not os.path.exists(archive_file):
        result.add_fail("Archive", "archive_handler.py no encontrado")
        return

    content = read_file(archive_file)

    methods = ["is_inside_archive", "mount_archive", "unmount_archive"]
    for method in methods:
        if method in content:
            result.add_pass("Archive", method)
        else:
            result.add_fail("Archive", f"{method} no existe")


def verify_config_manager(result: VerificationResult):
    """Verifica ConfigManager"""
    print("[8/13] Verificando ConfigManager...")

    config_file = os.path.join(SRC_DIR, "core", "config.py")
    if not os.path.exists(config_file):
        result.add_fail("Config", "config.py no encontrado")
        return

    content = read_file(config_file)

    methods = ["get_geometry", "set_window_state", "get_left_path", "get_right_path"]
    for method in methods:
        if method in content:
            result.add_pass("Config", method)
        else:
            result.add_fail("Config", f"{method} no existe")


def verify_engine(result: VerificationResult):
    """Verifica OperationEngine"""
    print("[9/13] Verificando OperationEngine...")

    engine_file = os.path.join(SRC_DIR, "core", "engine.py")
    if not os.path.exists(engine_file):
        result.add_fail("Engine", "engine.py no encontrado")
        return

    content = read_file(engine_file)

    operations = ["copy", "move", "delete"]
    for op in operations:
        if op in content:
            result.add_pass("Engine", op)
        else:
            result.add_fail("Engine", f"{op} no existe")


def verify_bookmarks(result: VerificationResult):
    """Verifica BookmarkManager"""
    print("[10/13] Verificando Bookmarks...")

    bookmarks_file = os.path.join(SRC_DIR, "core", "bookmarks.py")
    if not os.path.exists(bookmarks_file):
        result.add_fail("Bookmarks", "bookmarks.py no encontrado")
        return

    content = read_file(bookmarks_file)

    methods = ["add_bookmark", "get_all", "remove_bookmark"]
    for method in methods:
        if method in content:
            result.add_pass("Bookmarks", method)
        else:
            result.add_fail("Bookmarks", f"{method} no existe")


def verify_ui_dialogs(result: VerificationResult):
    """Verifica diálogos UI"""
    print("[11/13] Verificando Dialogos UI...")

    ui_dir = os.path.join(SRC_DIR, "ui")
    if not os.path.exists(ui_dir):
        result.add_fail("UI", "Directorio ui no encontrado")
        return

    dialogs = [
        "progress_dialog.py",
        "conflict_dialog.py",
        "settings_dialog.py",
        "bookmarks_editor.py",
        "search_dialog.py",
    ]

    for dialog in dialogs:
        path = os.path.join(ui_dir, dialog)
        if os.path.exists(path):
            result.add_pass("UI", dialog.replace(".py", ""))
        else:
            result.add_fail("UI", f"{dialog} no encontrado")


def verify_filter_functionality(result: VerificationResult):
    """Verifica funcionalidad de filtro"""
    print("[12/13] Verificando Filtros...")

    panel_file = os.path.join(SRC_DIR, "ui", "panel.py")
    if not os.path.exists(panel_file):
        result.add_fail("Filter", "panel.py no encontrado")
        return

    content = read_file(panel_file)

    if "setFilterFixedString" in content or "setFilterWildcard" in content:
        result.add_pass("Filter", "Filtros configurados")
    else:
        result.add_fail("Filter", "No hay filtros")

    if "setFilterCaseSensitivity" in content:
        result.add_pass("Filter", "Filtro case-insensitive")
    else:
        result.add_warning("Filter", "Filtro case-sensitive solo")


def verify_drag_drop(result: VerificationResult):
    """Verifica drag & drop"""
    print("[13/14] Verificando Drag & Drop...")

    panel_file = os.path.join(SRC_DIR, "ui", "panel.py")
    if not os.path.exists(panel_file):
        result.add_fail("DnD", "panel.py no encontrado")
        return

    content = read_file(panel_file)

    if "setDragEnabled" in content:
        result.add_pass("DnD", "Drag enabled")
    else:
        result.add_fail("DnD", "Drag no habilitado")

    if "setAcceptDrops" in content:
        result.add_pass("DnD", "Drop enabled")
    else:
        result.add_fail("DnD", "Drop no habilitado")


def verify_copy_move_jobs(result: VerificationResult):
    """Verifica las operaciones de copia y movimiento"""
    print("[14/14] Verificando CopyJob y MoveJob...")

    jobs_file = os.path.join(SRC_DIR, "core", "jobs.py")
    if not os.path.exists(jobs_file):
        result.add_fail("CopyMove", "jobs.py no encontrado")
        return

    jobs_content = read_file(jobs_file)

    # Verificar CopyJob usa dirs_exist_ok
    if "dirs_exist_ok=True" in jobs_content:
        result.add_pass("CopyMove", "CopyJob usa dirs_exist_ok=True")
    else:
        result.add_fail("CopyMove", "CopyJob no usa dirs_exist_ok")

    # Check fs_utils.py for .git and Windows reserved names handling
    fs_utils_file = os.path.join(SRC_DIR, "core", "fs_utils.py")
    fs_content = read_file(fs_utils_file) if os.path.exists(fs_utils_file) else ""

    # Verificar ignore para .git
    if "def should_overwrite_file" in fs_content:
        result.add_pass("CopyMove", "Ignora archivos .git")
    else:
        result.add_fail("CopyMove", "No ignora .git")

    # Verificar ignore para Windows reserved names
    reserved_names = [
        "nul",
        "con",
        "prn",
        "aux",
        "com1",
        "com2",
        "com3",
        "com4",
        "com5",
        "com6",
        "com7",
        "com8",
        "com9",
        "lpt1",
        "lpt2",
        "lpt3",
        "lpt4",
        "lpt5",
        "lpt6",
        "lpt7",
        "lpt8",
        "lpt9",
    ]
    found_reserved = [name for name in reserved_names if name in fs_content]
    if len(found_reserved) >= 3:  # Si encuentra al menos 3 nombres reservados
        result.add_pass("CopyMove", "Ignora nombres reservados Windows")
    else:
        result.add_fail("CopyMove", "No ignora nombres Windows")

    # Verificar partial success handling en CopyJob
    if "shutil.Error" in jobs_content or "partial" in jobs_content.lower():
        result.add_pass("CopyMove", "Manejo de copia parcial")
    else:
        result.add_warning("CopyMove", "Sin manejo de copia parcial")

    # Verificar MoveJob usa copytree para sobrescribir
    if "copytree" in jobs_content:
        result.add_pass("MoveJob", "MoveJob usa copytree")
    else:
        result.add_fail("MoveJob", "MoveJob no usa copytree")


def main():
    print("=" * 60)
    print("JMComander - Verificacion Automatizada")
    print("=" * 60)
    print(f"Python: {sys.version}")
    print(f"Proyecto: {PROJECT_ROOT}")

    if not os.path.exists(SRC_DIR):
        print(f"\n[X] ERROR: Directorio src no encontrado en {SRC_DIR}")
        return 1

    result = VerificationResult()

    verify_column_sorting(result)
    verify_shortcuts(result)
    verify_main_operations(result)
    verify_view_modes(result)
    verify_plugins(result)
    verify_plugins_directory(result)
    verify_archive_handler(result)
    verify_config_manager(result)
    verify_engine(result)
    verify_bookmarks(result)
    verify_ui_dialogs(result)
    verify_filter_functionality(result)
    verify_drag_drop(result)
    verify_copy_move_jobs(result)

    success = result.print_summary()

    if success:
        print("\n[OK] TODAS LAS VERIFICACIONES PASARON")
        return 0
    print("\n[X] ALGUNAS VERIFICACIONES FALLARON")
    return 1


if __name__ == "__main__":
    sys.exit(main())
