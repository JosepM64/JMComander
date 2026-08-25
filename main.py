import logging
import os
import sys
import threading
import traceback
from pathlib import Path

# Configurar QT_PLUGIN_PATH para PyInstaller
if getattr(sys, "frozen", False):
    base_path = sys._MEIPASS

    # Verificar estructura de directorios
    print(f"[DEBUG] base_path: {base_path}")
    print(f"[DEBUG] base_path contents: {os.listdir(base_path)[:30]}")

    # Buscar plugins en diferentes ubicaciones
    possible_plugin_paths = [
        os.path.join(base_path, "plugins"),
        os.path.join(base_path, "plugins", "platforms"),
        os.path.join(base_path, "PySide6", "plugins"),
    ]

    for pp in possible_plugin_paths:
        if os.path.exists(pp):
            print(f"[DEBUG] Found plugin path: {pp}")
            print(f"[DEBUG] Plugin path contents: {os.listdir(pp)}")
            os.environ["QT_PLUGIN_PATH"] = pp
            break

    # Añadir la ruta base i la de PySide6 al PATH per trobar DLLs Qt
    os.environ["PATH"] = (
        base_path
        + os.pathsep
        + os.path.join(base_path, "PySide6")
        + os.pathsep
        + os.environ.get("PATH", "")
    )
    print(f"[DEBUG] Added to PATH: {base_path} and PySide6")

# Configuración básica de logging con force=True para capturar todo desde el inicio
log_dir = (
    Path(os.path.dirname(sys.executable))
    if getattr(sys, "frozen", False)
    else Path(__file__).parent
)
log_dir.mkdir(exist_ok=True)
log_file = log_dir / "jmcomander.log"

# Configurar logging con niveles separados para desarrollo vs producción
# DEBUG para archivo (para troubleshooting), INFO para consola (más limpio)
file_handler = logging.FileHandler(log_file, encoding="utf-8", mode="w")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)  # Mostrar solo INFO y superiores en consola
console_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)
# Filtrar cualquier mensaje DEBUG que pueda colarse
console_handler.addFilter(lambda record: record.levelno >= logging.INFO)

logging.basicConfig(
    level=logging.DEBUG,  # Nivel global DEBUG para capturar todo
    handlers=[file_handler, console_handler],
    force=True,
)
logger = logging.getLogger("JMComander")


# Global exception hook para capturar cualquier excepción no manejada
def global_exception_hook(exctype, value, tb):
    logger.critical("=" * 60)
    logger.critical("GLOBAL EXCEPTION CAUGHT!")
    logger.critical(f"Type: {exctype}")
    logger.critical(f"Value: {value}")
    logger.critical("Traceback:")
    for line in traceback.format_tb(tb):
        logger.critical(line.strip())
    logger.critical("=" * 60)
    # Llamar al handler original también
    sys.__excepthook__(exctype, value, tb)


sys.excepthook = global_exception_hook


# Capturar excepciones en threads también
def thread_except_hook(args):
    logger.critical("=" * 60)
    logger.critical("EXCEPTION IN THREAD!")
    logger.critical(f"Type: {args.exc_type}")
    logger.critical(f"Value: {args.exc_value}")
    logger.critical("Traceback:")
    for line in traceback.format_tb(args.exc_traceback):
        logger.critical(line.strip())
    logger.critical("=" * 60)


threading.excepthook = thread_except_hook

logger.info("=== JMComander Startup ===")
logger.info(f"Python version: {sys.version}")
logger.info(f"Executable: {sys.executable}")
logger.info(f"Frozen: {getattr(sys, 'frozen', False)}")

# Importar PySide6 de manera segura
try:
    import PySide6

    pyside_file = getattr(PySide6, "__file__", None) or getattr(PySide6, "__path__", [None])[0]
    pyside_path = os.path.dirname(pyside_file) if pyside_file else None
    logger.info(f"[DEBUG] PySide6 path: {pyside_file}")
    logger.info(f"[DEBUG] PySide6 dir: {pyside_path}")

    # Verificar que existen los archivos Qt6 DLL
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS
        for dll in ["Qt6Core.dll", "Qt6Gui.dll", "Qt6Widgets.dll"]:
            dll_path = os.path.join(base_path, dll)
            if os.path.exists(dll_path):
                logger.info(f"  Qt6 DLL: {dll} en base_path")
            elif os.path.exists(os.path.join(base_path, "PySide6", dll)):
                logger.info(f"  Qt6 DLL: {dll} en PySide6/")

    import importlib.util as _ilu

    if not _ilu.find_spec("PySide6.QtCore"):
        msg = "PySide6.QtCore not found"
        raise ImportError(msg)
    logger.info("[DEBUG] QtCore available")

    if not _ilu.find_spec("PySide6.QtGui"):
        msg = "PySide6.QtGui not found"
        raise ImportError(msg)
    logger.info("[DEBUG] QtGui available")

    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication

    logger.info("[OK] PySide6 imports successful")
except ImportError as e:
    logger.exception(f"[ERROR] Failed to import PySide6: {e}")
    logger.exception("[DEBUG] Checking PySide6 installation...")
    try:
        import PySide6

        pyside_file = getattr(PySide6, "__file__", None) or getattr(PySide6, "__path__", [None])[0]
        logger.exception(f"[DEBUG] PySide6 location: {pyside_file}")
        import os

        pyside_path = os.path.dirname(pyside_file) if pyside_file else None
        logger.exception(f"[DEBUG] PySide6 directory contents: {os.listdir(pyside_path)[:20]}")

        # Check for Qt DLLs
        qt_dirs = [d for d in os.listdir(pyside_path) if d.startswith("Qt")]
        logger.exception(f"[DEBUG] Qt directories found: {qt_dirs}")

        # Check for platforms plugin
        plugins_path = os.path.join(pyside_path, "plugins", "platforms")
        if os.path.exists(plugins_path):
            logger.exception(f"[DEBUG] Platforms found: {os.listdir(plugins_path)}")
        else:
            logger.exception(f"[DEBUG] Platforms NOT found at: {plugins_path}")
    except Exception as debug_e:
        logger.exception(f"[DEBUG] Additional debug info failed: {debug_e}")

    import traceback

    logger.exception(traceback.format_exc())
    sys.exit(1)

try:
    # Forzar inclusión de librerías para plugins dinámicos

    from src.ui.main_window import MainWindow

    logger.info("[OK] MainWindow and Plugin dependencies ready")
except Exception as e:
    logger.exception(f"[ERROR] Unexpected error importing MainWindow: {e}")
    logger.exception(traceback.format_exc())
    sys.exit(1)


def check_single_instance():
    """Implementa única instancia. Retorna True si es la primera instancia, False si ya hay otra."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        # Nombre del mutex
        mutex_name = "Global\\JMComander_SingleInstance_Mutex"

        # Crear mutex con seguridad para permitir que otras sesiones lo vean
        class SECURITY_ATTRIBUTES(ctypes.Structure):
            _fields_ = [
                ("nLength", wintypes.DWORD),
                ("lpSecurityDescriptor", wintypes.LPVOID),
                ("bInheritHandle", wintypes.BOOL),
            ]

        sa = SECURITY_ATTRIBUTES()
        sa.nLength = ctypes.sizeof(SECURITY_ATTRIBUTES)
        sa.lpSecurityDescriptor = None
        sa.bInheritHandle = True

        # Intentar crear el mutex
        mutex = ctypes.windll.kernel32.CreateMutexW(ctypes.byref(sa), False, mutex_name)

        if not mutex:
            logger.warning("No se pudo crear el mutex de instancia única")
            return True

        # Verificar si ya existía (otra instancia corriendo)
        ERROR_ALREADY_EXISTS = 183
        last_error = ctypes.windll.kernel32.GetLastError()

        if last_error == ERROR_ALREADY_EXISTS:
            logger.warning("Ya hay otra instancia de JMComander ejecutándose")

            # Intentar traer la ventana existente al frente
            try:
                import win32con
                import win32gui

                # Buscar la ventana principal
                def find_jmcomander_window(hwnd, lParam):
                    if win32gui.IsWindowVisible(hwnd):
                        title = win32gui.GetWindowText(hwnd)
                        if "JMComander" in title:
                            # Restaurar si está minimizada
                            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                            # Traer al frente
                            win32gui.SetForegroundWindow(hwnd)
                            return False  # Stop enumeration
                    return True

                win32gui.EnumWindows(find_jmcomander_window, None)
                logger.info("Ventana anterior traída al frente")
            except Exception as e:
                logger.warning(f"No se pudo traer ventana anterior: {e}")

            # Cerrar el mutex y salir
            ctypes.windll.kernel32.CloseHandle(mutex)
            return False

        logger.info("Mutex de instancia única creado correctamente")
        return True
    # En otras plataformas, usar un archivo de lock
    lock_file = Path.home() / ".jmcomander.lock"
    if lock_file.exists():
        logger.warning("Ya hay otra instancia de JMComander ejecutándose (archivo de lock)")
        return False
    try:
        lock_file.write_text(str(os.getpid()))
        return True
    except Exception as e:
        logger.warning(f"No se pudo crear archivo de lock: {e}")
        return True


def main():
    try:
        # Verificar instancia única antes de continuar
        if not check_single_instance():
            logger.info("Saliendo porque ya hay otra instancia ejecutándose")
            sys.exit(0)

        # CRITICAL: Set AppUserModelID BEFORE QApplication on Windows 11
        if sys.platform == "win32":
            try:
                import ctypes

                myappid = "josepmaria.jmcomander.app"
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
                logger.info(f"[OK] AppUserModelID set: {myappid}")
            except Exception as e:
                logger.warning(f"Failed to set AppUserModelID: {e}")

        app = QApplication(sys.argv)
        app.setApplicationName("JMComander")
        app.setOrganizationName("JMSoftware")

        # Set Global App Icon (Critical for taskbar)
        base_path = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).parent

        # Intentar varias rutas para el icono
        ico_locations = [
            base_path / "assets" / "jmcomander.ico",
            base_path / "src" / "assets" / "jmcomander.ico",
            base_path / "_internal" / "assets" / "jmcomander.ico",
        ]

        icon_found = False
        for ico_path in ico_locations:
            if ico_path.exists():
                app.setWindowIcon(QIcon(str(ico_path)))
                logger.info(f"[OK] Global icon set from: {ico_path}")
                icon_found = True
                break

        if not icon_found:
            logger.warning("Application icon not found in any standard location")

        logger.info("[OK] QApplication created")

        window = MainWindow()
        logger.info("[OK] MainWindow created")

        # Instalar eventFilter global para capturar teclas de filtro rápido
        from PySide6.QtCore import QEvent, QObject

        class GlobalKeyFilter(QObject):
            def __init__(self, main_window, parent=None):
                super().__init__(parent)
                self.main_window = main_window

            def eventFilter(self, obj, event):
                if event.type() == QEvent.Type.KeyPress:
                    logger.debug(
                        f"GlobalKeyFilter: key press text='{event.text()}',"
                        f" key={event.key()}, obj={obj}"
                    )
                    # Verificar si hay un diálogo modal abierto
                    active_window = app.activeWindow()
                    if active_window and active_window != self.main_window:
                        # Hay un diálogo o ventana diferente abierta, no interceptar
                        logger.debug(
                            f"Active window is different window"
                            f" ({type(active_window).__name__}), skipping"
                        )
                        return False

                    # Obtener el panel activo
                    active_panel = self.main_window.active_panel
                    if not active_panel:
                        logger.debug("No active panel")
                        return False

                    # Si el foco está en path_input del panel activo, no interceptar
                    if active_panel.path_input.hasFocus():
                        logger.debug("Focus in path_input, skipping")
                        return False

                    # Si el foco está en filter_input, solo manejar ESC
                    if active_panel.filter_input.hasFocus():
                        logger.debug(f"Focus in filter_input, key={event.key()}")
                        if event.key() == 16777216:  # Qt.Key.Key_Escape
                            logger.debug("ESC pressed in filter_input")
                            active_panel.filter_input.clear()
                            active_panel.filter_input.hide()
                            active_panel.current_view_widget.setFocus()
                            return True
                        return False

                    # Capturar '+' para selección por patrón
                    if event.text() == "+":
                        logger.info("+ pressed, triggering pattern selection")
                        active_panel._trigger_pattern_selection(True)
                        logger.info("Pattern selection completed")
                        return True

                    # Capturar '-' para deselección por patrón
                    if event.text() == "-":
                        logger.info("- pressed, triggering pattern deselection")
                        active_panel._trigger_pattern_selection(False)
                        logger.info("Pattern deselection completed")
                        return True

                    # Capturar teclas alfanuméricas para filtro rápido
                    if len(event.text()) == 1 and event.text().isalnum():
                        # Si el filter_input no está visible, mostrarlo y establecer el texto
                        if not active_panel.filter_input.isVisible():
                            logger.debug(
                                f"Alpha key '{event.text()}', filter_input not visible, showing"
                            )
                            active_panel.filter_input.show()
                            active_panel.filter_input.setText(event.text())
                            active_panel.filter_input.setFocus()
                            return True
                        # Si filter_input visible pero sin foco, poner foco y añadir
                        if not active_panel.filter_input.hasFocus():
                            logger.debug(
                                f"Alpha key '{event.text()}',"
                                " filter_input visible but not focused, appending"
                            )
                            active_panel.filter_input.setFocus()
                            current_text = active_panel.filter_input.text()
                            active_panel.filter_input.setText(current_text + event.text())
                            return True
                        # Si filter_input visible y con foco, Qt maneja la tecla
                        logger.debug(
                            f"Alpha key '{event.text()}', filter_input focused, passing through"
                        )
                        return False

                return False

        global_filter = GlobalKeyFilter(window)
        app.installEventFilter(global_filter)
        logger.info("[OK] Global key filter installed")

        window.show()
        logger.info("[OK] MainWindow shown")

        try:
            exit_code = app.exec()
            logger.info(f"App.exec() returned with exit code: {exit_code}")
        except Exception as e:
            logger.critical(f"Exception in app.exec(): {e}")
            logger.critical(traceback.format_exc())
            exit_code = 1

        sys.exit(exit_code)
    except Exception as e:
        logger.critical(f"CRITICAL ERROR in main(): {e}")
        logger.critical(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
