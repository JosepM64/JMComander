import ctypes
import json
import logging
import os
import time

import pythoncom
import win32api
import win32con
import win32gui
from win32com.shell import shell, shellcon

logger = logging.getLogger(__name__)

# Singleton access
_instance = None
CUSTOM_OPENWITH_ID = 0x7FFF
JM_CREA_BASE_ID = 0x8000
JM_NEW_FOLDER_ID = 0x8001
JM_CREA_EXTENSIONS_START = 0x8002

# Extensions que oferirem al menú de fons
CREA_EXTENSIONS = [".txt", ".docx", ".xlsx", ".pptx", ".rtf", ".bmp", ".zip"]

# Custom IDs for edit operations
JM_EDIT_NOTEPAD_ID = 0x8100
JM_EDIT_NOTEPADPP_ID = 0x8101
JM_SENDTO_ID = 0x8102
JM_TERMINAL_CMD_ID = 0x8103
JM_TERMINAL_PS_ID = 0x8104

# Constantes de Windows
WM_INITMENUPOPUP = 0x0117
WM_DRAWITEM = 0x002B
WM_MEASUREITEM = 0x002C
WM_MENUCHAR = 0x0012
CMIC_MASK_UNICODE = 0x00004000

# Prototipo de WndProc para ctypes (vital en 64-bit)
WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_longlong, ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p
)

# Globales para el WndProc
_current_cm2 = None
_current_cm3 = None


def _get_friendly_name(ext):
    """Busca el nom descriptiu de l'extensió al registre."""
    try:
        import winreg  # noqa: PLC0415

        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, ext) as key:
            file_type, _ = winreg.QueryValueEx(key, "")
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, file_type) as type_key:
                friendly_name, _ = winreg.QueryValueEx(type_key, "")
                return friendly_name
    except Exception as _e:  # noqa: BLE001
        return None


def _low_level_wndproc(hwnd, msg, wparam, lparam):
    """Procedimiento de ventana de bajo nivel para forward de mensajes al Shell."""
    try:
        # Reenviar mensajes de inicialización y dibujo al Shell
        if msg in (WM_INITMENUPOPUP, WM_DRAWITEM, WM_MEASUREITEM):
            if _current_cm3:
                _current_cm3.HandleMenuMsg2(msg, wparam, lparam)
                return 0
            if _current_cm2:
                _current_cm2.HandleMenuMsg(msg, wparam, lparam)
                return 0

        if msg == WM_MENUCHAR:
            if _current_cm3:
                return _current_cm3.HandleMenuMsg2(msg, wparam, lparam)
            if _current_cm2:
                return _current_cm2.HandleMenuMsg(msg, wparam, lparam)

        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)
    except Exception as _e:  # noqa: BLE001
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)


# Referencia persistente del callback para evitar Garbage Collection
_wndproc_callback = WNDPROC(_low_level_wndproc)

# Registrar clase de ventana host
_wnd_class_name = "JMComanderMenuHostV3"


def _register_class():
    try:
        hinst = win32api.GetModuleHandle(None)
        wc = win32gui.WNDCLASS()
        wc.lpfnWndProc = _wndproc_callback
        wc.lpszClassName = _wnd_class_name
        wc.hInstance = hinst
        win32gui.RegisterClass(wc)
    except Exception as _e:  # noqa: BLE001
        pass


_register_class()


class WindowsNativeMenu:
    """
    Gestiona la invocació del menú contextual natiu de Windows (Shell).
    Versió 1.9.3: Estabilitat extrema amb reenviaments de missatges a nivell de C.
    """

    def __init__(self):
        self._config = self._load_config()
        self._mode = self._config.get("native_menu", {}).get("mode", "smart")
        try:
            pythoncom.CoInitialize()
        except Exception as _e:  # noqa: BLE001
            pass

    def _load_config(self) -> dict:
        try:
            base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            config_path = os.path.join(base_dir, "config.json")
            if os.path.exists(config_path):
                with open(config_path, encoding="utf-8") as f:
                    return json.load(f)
        except Exception as _e:  # noqa: BLE001
            pass
        return {}

    def show_menu(self, hwnd_parent: int, paths: list[str], x: int, y: int):
        """Menú per a fitxers seleccionats."""
        if not paths:
            return
        pythoncom.CoInitialize()
        try:
            abs_paths = [os.path.abspath(p) for p in paths]
            pidls = [shell.SHParseDisplayName(p, 0)[0] for p in abs_paths]
            desktop = shell.SHGetDesktopFolder()
            ctx_raw = desktop.GetUIObjectOf(hwnd_parent, tuple(pidls), shell.IID_IContextMenu, 0)
            context_menu = self._get_interface(ctx_raw)
            if context_menu:
                self._display_and_execute_menu(hwnd_parent, context_menu, abs_paths, x, y, False)
        except Exception as e:
            logger.exception("Error show_menu: %s", e)  # noqa: TRY401

    def show_background_menu(
        self, hwnd_parent: int, folder_path: str, x: int, y: int, creation_callback=None
    ):
        """Menú per al fons de la carpeta (Nou, Crea, Pegar)."""
        pythoncom.CoInitialize()
        try:
            abs_folder = os.path.abspath(folder_path)
            pidl, _ = shell.SHParseDisplayName(abs_folder, 0)
            desktop = shell.SHGetDesktopFolder()
            folder_object = desktop.BindToObject(pidl, None, shell.IID_IShellFolder)

            context_menu = None
            try:
                # Intent 1: CreateViewObject (Recomanat per a 'Nou')
                context_menu = folder_object.CreateViewObject(hwnd_parent, shell.IID_IContextMenu)
            except Exception as _e:  # noqa: BLE001
                # Intent 2: GetUIObjectOf amb tupla buida
                try:
                    ctx_raw = folder_object.GetUIObjectOf(
                        hwnd_parent, (), shell.IID_IContextMenu, 0
                    )
                    context_menu = self._get_interface(ctx_raw)
                except Exception as _e:  # noqa: BLE001
                    pass

            if context_menu:
                self._display_and_execute_menu(
                    hwnd_parent, context_menu, [abs_folder], x, y, True, creation_callback
                )
        except Exception as e:
            logger.exception("Error show_background_menu: %s", e)  # noqa: TRY401

    def _get_interface(self, ctx_raw):
        if ctx_raw is None:
            return None
        if not isinstance(ctx_raw, tuple):
            return ctx_raw
        for item in ctx_raw:
            if hasattr(item, "QueryContextMenu"):
                return item
        return None

    def _remove_broken_shell_items(self, hmenu):
        """Elimina elementos del menú que puedan causar errores (terminales rotos, etc.)"""
        try:
            import win32con  # noqa: PLC0415

            count = win32gui.GetMenuItemCount(hmenu)
            # Patrones de texto problemáticos (en varios idiomas)
            problematic_patterns = [
                "terminal",
                "cmd",
                "powershell",
                "bash",
                "git",
                "wsl",
                "shell",
                "oberir",
                "obrir",
                "open",
                "abrir",
                "executar",
                "run",
            ]
            # Nuestros submenús personalizados que NO debemos eliminar
            our_submenus = ["&editar", "termi&nal", "crea (jmcomander)"]

            for i in range(count - 1, -1, -1):
                try:
                    # Obtener estado del item
                    state = win32gui.GetMenuState(hmenu, i, win32con.MF_BYPOSITION)
                    # Si es separador, saltar
                    if state & win32con.MF_SEPARATOR:
                        continue

                    # Obtener texto del item
                    text = win32gui.GetMenuString(hmenu, i, win32con.MF_BYPOSITION)
                    if not text:
                        continue

                    text_lower = text.strip().lower()

                    # Si es submenú, verificar si es nuestro o uno problemático
                    if state & win32con.MF_POPUP:
                        # Es un submenú, verificar si es nuestro
                        if text_lower not in our_submenus:
                            # Podría ser un submenú problemático (como "Obrir al terminal")
                            # Verificar si contiene patrones problemáticos
                            if any(pattern in text_lower for pattern in problematic_patterns):
                                logger.debug(
                                    f"Eliminando submenú potencialmente problemático: '{text}'"  # noqa: G004
                                )
                                win32gui.RemoveMenu(hmenu, i, win32con.MF_BYPOSITION)
                                continue
                            # Si no es problemático, limpiar recursivamente su contenido
                            hsubmenu = win32gui.GetSubMenu(hmenu, i)
                            if hsubmenu:
                                self._remove_broken_shell_items(hsubmenu)
                        continue

                    # Para items normales (no submenus)
                    # Verificar si contiene algun patron problemativo
                    if (
                        any(pattern in text_lower for pattern in problematic_patterns)
                        and "termi&nal" not in text_lower
                    ):
                        logger.debug("Eliminando item potencialmente problemativo: '%s'", text)
                        win32gui.RemoveMenu(hmenu, i, win32con.MF_BYPOSITION)
                except Exception as e:  # noqa: BLE001
                    logger.debug("Error al procesar item de menú: %s", e)
                    continue
        except Exception as e:  # noqa: BLE001
            logger.debug("Error en _remove_broken_shell_items: %s", e)

    def _display_and_execute_menu(  # noqa: PLR0912
        self, hwnd_parent, context_menu, targets, _x, _y, is_background, creation_callback=None
    ):
        global _current_cm2, _current_cm3  # noqa: PLW0603

        # 1. Crear finestra invisible Host per rebre missatges del Shell
        hwnd_host = win32gui.CreateWindowEx(
            0,
            _wnd_class_name,
            "JMComander Menu Host",
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            win32api.GetModuleHandle(None),
            None,
        )

        # 2. Obtenir interfícies per a submenús
        try:
            _current_cm2 = context_menu.QueryInterface(shell.IID_IContextMenu2)
        except Exception as _e:  # noqa: BLE001
            _current_cm2 = None
        try:
            _current_cm3 = context_menu.QueryInterface(shell.IID_IContextMenu3)
        except Exception as _e:  # noqa: BLE001
            _current_cm3 = None

        hmenu = win32gui.CreatePopupMenu()

        # Para archivos: 7 items antes de QueryContextMenu
        # (Cut, Copy, Paste, Sep, OpenWith, SendTo, Sep, Edit)
        # Para carpetas (background): 0 items antes
        base_id = 7 if not is_background else 0

        try:
            # Añadir operaciones básicas al inicio del menú (solo para archivos)
            if not is_background:
                win32gui.AppendMenu(hmenu, win32con.MF_STRING, 0x0011, "Cort&ar")
                win32gui.AppendMenu(hmenu, win32con.MF_STRING, 0x0012, "&Copiar")
                win32gui.AppendMenu(hmenu, win32con.MF_STRING, 0x0013, "&Pegar")
                win32gui.AppendMenu(hmenu, win32con.MF_SEPARATOR, 0, "")
                win32gui.AppendMenu(hmenu, win32con.MF_STRING, CUSTOM_OPENWITH_ID, "A&brir con...")
                win32gui.AppendMenu(hmenu, win32con.MF_STRING, JM_SENDTO_ID, "E&nviar a...")

                # Añadir opciones de edición
                hsubmenu_edit = win32gui.CreatePopupMenu()
                win32gui.AppendMenu(
                    hsubmenu_edit,
                    win32con.MF_STRING,
                    JM_EDIT_NOTEPAD_ID,
                    "Editar con &Bloc de notas",
                )

                # Buscar Notepad++
                npp_path = self._find_notepadpp()
                if npp_path:
                    win32gui.AppendMenu(
                        hsubmenu_edit,
                        win32con.MF_STRING,
                        JM_EDIT_NOTEPADPP_ID,
                        "Editar con &Notepad++",
                    )

                win32gui.AppendMenu(
                    hmenu, win32con.MF_BYPOSITION | win32con.MF_POPUP, hsubmenu_edit, "&Editar"
                )

                # Añadir opciones de terminal
                hsubmenu_terminal = win32gui.CreatePopupMenu()
                win32gui.AppendMenu(
                    hsubmenu_terminal, win32con.MF_STRING, JM_TERMINAL_CMD_ID, "Terminal (&CMD)"
                )
                win32gui.AppendMenu(
                    hsubmenu_terminal,
                    win32con.MF_STRING,
                    JM_TERMINAL_PS_ID,
                    "Terminal (&PowerShell)",
                )
                win32gui.AppendMenu(
                    hmenu,
                    win32con.MF_BYPOSITION | win32con.MF_POPUP,
                    hsubmenu_terminal,
                    "Termi&nal",
                )
                win32gui.AppendMenu(hmenu, win32con.MF_SEPARATOR, 0, "")

            # QueryContextMenu: El Shell omple el menú con más opciones
            # idCmdFirst debe empezar después de nuestros items personalizados
            cmd_first = base_id + 1
            context_menu.QueryContextMenu(
                hmenu,
                base_id,
                cmd_first,
                0x7FFF,
                shellcon.CMF_NORMAL
                | shellcon.CMF_EXPLORE
                | shellcon.CMF_CANRENAME
                | shellcon.CMF_NODEFAULT,
            )

            # Eliminar elementos del menú que puedan causar errores (terminales rotos, etc.)
            self._remove_broken_shell_items(hmenu)

            # Afegir el nostre menú "Crea (JM)" al principi si és background
            if is_background:
                hsubmenu = win32gui.CreatePopupMenu()
                win32gui.AppendMenu(hsubmenu, win32con.MF_STRING, JM_NEW_FOLDER_ID, "Nova Carpeta")
                win32gui.AppendMenu(hsubmenu, win32con.MF_SEPARATOR, 0, "")

                for i, ext in enumerate(CREA_EXTENSIONS):
                    friendly = _get_friendly_name(ext)
                    label = f"{friendly} ({ext})" if friendly else f"Fitxer {ext}"
                    win32gui.AppendMenu(
                        hsubmenu, win32con.MF_STRING, JM_CREA_EXTENSIONS_START + i, label
                    )

                # Inserir al principi de tot
                win32gui.InsertMenu(
                    hmenu,
                    0,
                    win32con.MF_BYPOSITION | win32con.MF_POPUP,
                    hsubmenu,
                    "Crea (JMComander)",
                )
                win32gui.InsertMenu(hmenu, 1, win32con.MF_BYPOSITION | win32con.MF_SEPARATOR, 0, "")

                # Añadir submenú Terminal para fondo
                hsubmenu_terminal_bg = win32gui.CreatePopupMenu()
                win32gui.AppendMenu(
                    hsubmenu_terminal_bg, win32con.MF_STRING, JM_TERMINAL_CMD_ID, "Terminal (&CMD)"
                )
                win32gui.AppendMenu(
                    hsubmenu_terminal_bg,
                    win32con.MF_STRING,
                    JM_TERMINAL_PS_ID,
                    "Terminal (&PowerShell)",
                )
                win32gui.InsertMenu(
                    hmenu,
                    2,
                    win32con.MF_BYPOSITION | win32con.MF_POPUP,
                    hsubmenu_terminal_bg,
                    "Termi&nal",
                )
                win32gui.InsertMenu(hmenu, 3, win32con.MF_BYPOSITION | win32con.MF_SEPARATOR, 0, "")

                # ELIMINAR EL MENÚ "NOU/NUEVO/NEW/CREA" NATIVU PER EVITAR DUPLICATS QUE NO FUNCIONEN
                try:
                    count = win32gui.GetMenuItemCount(hmenu)
                    for i in range(count - 1, -1, -1):
                        # Saltar nuestros submenús (posiciones 0 y 2) y separadores
                        if i in (0, 2, 1, 3):  # 0: Crea, 1: separador, 2: Terminal, 3: separador
                            continue
                        state = win32gui.GetMenuState(hmenu, i, win32con.MF_BYPOSITION)
                        if state & win32con.MF_POPUP:
                            # Es un submenú, verificar si es el nativo "Nou/New/Nuevo"
                            try:
                                text = win32gui.GetMenuString(hmenu, i, win32con.MF_BYPOSITION)
                                text_lower = text.strip().lower()
                                # Patrones que indican el menú nativo de "Nuevo"
                                new_patterns = ["nou", "new", "nuevo", "crea", "crear", "create"]
                                if any(pattern in text_lower for pattern in new_patterns) and (
                                    "jmcomander" not in text_lower and "termi&nal" not in text_lower
                                ):
                                    win32gui.RemoveMenu(hmenu, i, win32con.MF_BYPOSITION)
                                    logger.debug("Eliminado menu nativo 'Nuevo': '%s'", text)
                                    break
                            except Exception as _e:  # noqa: BLE001
                                # Si no podemos obtener el texto, eliminarlo solo si no es nuestros
                                win32gui.RemoveMenu(hmenu, i, win32con.MF_BYPOSITION)
                                break
                except Exception as e:  # noqa: BLE001
                    logger.debug("Error eliminando menú 'Nuevo': %s", e)

            win32gui.SetForegroundWindow(hwnd_host)
            time.sleep(0.05)
            real_x, real_y = win32gui.GetCursorPos()

            # 3. TrackPopupMenu redirigit al host invisible
            cmd = win32gui.TrackPopupMenu(
                hmenu,
                win32con.TPM_RETURNCMD | win32con.TPM_RIGHTBUTTON,
                real_x,
                real_y,
                0,
                hwnd_host,
                None,
            )

            if cmd > 0:
                # Manejar Cut, Copy, Paste
                if cmd == 0x0011:  # Cut
                    self._handle_cut_copy(targets, "cut")
                    return
                if cmd == 0x0012:  # Copy
                    self._handle_cut_copy(targets, "copy")
                    return
                if cmd == 0x0013:  # Paste
                    self._handle_paste(targets[0])
                    return
                if not is_background and cmd == CUSTOM_OPENWITH_ID:
                    self._handle_open_with(targets[0])
                    return
                if not is_background and cmd == JM_SENDTO_ID:
                    self._handle_sendto(targets)
                    return
                if not is_background and cmd == JM_EDIT_NOTEPAD_ID:
                    self._handle_edit(targets[0], "notepad.exe")
                    return
                if not is_background and cmd == JM_EDIT_NOTEPADPP_ID:
                    npp_path = self._find_notepadpp()
                    if npp_path:
                        self._handle_edit(targets[0], npp_path)
                    return
                if cmd == JM_TERMINAL_CMD_ID:
                    self._handle_terminal_cmd(targets[0])
                    return
                if cmd == JM_TERMINAL_PS_ID:
                    self._handle_terminal_ps(targets[0])
                    return
                if is_background and cmd >= JM_CREA_BASE_ID and creation_callback:
                    if cmd == JM_NEW_FOLDER_ID:
                        creation_callback(None, "folder")
                    elif cmd >= JM_CREA_EXTENSIONS_START:
                        idx = cmd - JM_CREA_EXTENSIONS_START
                        if 0 <= idx < len(CREA_EXTENSIONS):
                            creation_callback(CREA_EXTENSIONS[idx], "file")
                else:
                    # Restar el offset base para obtener el índice correcto del comando shell
                    cmd_offset = cmd - (base_id + 1)
                    self._execute_shell_command(hwnd_parent, context_menu, cmd_offset, targets[0])

        finally:
            # Neteja de referències i destrucció de finestres
            _current_cm2 = None
            _current_cm3 = None
            win32gui.DestroyMenu(hmenu)
            win32gui.DestroyWindow(hwnd_host)

    def _handle_open_with(self, file_path):
        try:
            shell.ShellExecuteEx(
                lpVerb="openas",
                lpFile=file_path,
                nShow=win32con.SW_SHOWNORMAL,
                fMask=shellcon.SEE_MASK_INVOKEIDLIST,
            )
        except Exception as _e:  # noqa: BLE001
            win32api.ShellExecute(
                0,
                "open",
                "rundll32.exe",
                f'shell32.dll,OpenAs_RunDLL "{file_path}"',
                "",
                win32con.SW_SHOWNORMAL,
            )

    def _handle_sendto(self, paths):
        """Muestra el menú Enviar a... de Windows"""
        try:
            import subprocess  # noqa: PLC0415

            # Método más efectivo: usar PowerShell para invocar el menú SendTo
            if paths and len(paths) > 0:
                # Construir la lista de archivos
                files_arg = ",".join([f'"{os.path.abspath(p)}"' for p in paths])

                # Script de PowerShell para invocar el menú SendTo
                ps_script = f"""
Add-Type -AssemblyName System.Windows.Forms
$files = @({files_arg})
$shell = New-Object -ComObject Shell.Application

# Obtener los archivos seleccionados
foreach ($file in $files) {{
    $item = $shell.NameSpace(0).ParseName($file)
    if ($item) {{
        $item.InvokeVerb("sendto")
    }}
}}
"""
                try:
                    # Ejecutar PowerShell
                    subprocess.Popen(
                        ["powershell", "-WindowStyle", "Hidden", "-Command", ps_script],
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                    logger.info("SendTo menu invoked for %s files", len)
                    return  # noqa: TRY300
                except Exception as e:  # noqa: BLE001
                    logger.warning("PowerShell SendTo failed: %s", e)

            # Fallback: abrir la carpeta SendTo en el explorador
            sendto_path = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "SendTo")
            win32api.ShellExecute(
                0, "open", "explorer.exe", f'"{sendto_path}"', "", win32con.SW_SHOWNORMAL
            )

        except Exception as e:
            logger.exception("Error in SendTo: %s", e)  # noqa: TRY401
            # Último fallback: abrir carpeta SendTo
            try:
                sendto_path = os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "SendTo")
                win32api.ShellExecute(
                    0, "open", "explorer.exe", f'"{sendto_path}"', "", win32con.SW_SHOWNORMAL
                )
            except Exception as e:  # noqa: BLE001
                pass

    def _find_notepadpp(self):
        """Busca Notepad++ via registre o paths estàndard"""
        try:
            import winreg  # noqa: PLC0415
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Notepad++")
            install_dir = winreg.QueryValueEx(key, "Install_Dir")[0]
            winreg.CloseKey(key)
            npp = os.path.join(install_dir, "notepad++.exe")
            if os.path.exists(npp):
                return npp
        except Exception:  # noqa: BLE001
            pass
        for p in [
            os.path.expandvars(r"%ProgramFiles%\Notepad++\notepad++.exe"),
            os.path.expandvars(r"%ProgramFiles(x86)%\Notepad++\notepad++.exe"),
            os.path.expandvars(r"%LOCALAPPDATA%\Notepad++\notepad++.exe"),
        ]:
            if os.path.exists(p):
                return p
        return None

    def _handle_edit(self, file_path, editor_path):
        """Abre un archivo con el editor especificado"""
        try:
            win32api.ShellExecute(
                0, "open", editor_path, f'"{file_path}"', "", win32con.SW_SHOWNORMAL
            )
            logger.info("Opened %s with %s", file_path, editor_path)
        except Exception as e:
            logger.exception("Error opening file with editor: %s", e)  # noqa: TRY401

    def _handle_terminal_cmd(self, path):
        """Abre terminal CMD en la ruta especificada"""
        try:
            import subprocess  # noqa: PLC0415

            directory = os.path.dirname(path) if os.path.isfile(path) else path
            subprocess.Popen(["cmd.exe", "/k", "cd", "/d", directory])
            logger.info("Opened CMD terminal at %s", directory)
        except Exception as e:
            logger.exception("Error opening CMD terminal: %s", e)  # noqa: TRY401

    def _handle_terminal_ps(self, path):
        """Abre terminal PowerShell en la ruta especificada"""
        try:
            import subprocess  # noqa: PLC0415

            directory = os.path.dirname(path) if os.path.isfile(path) else path
            subprocess.Popen(["powershell.exe", "-NoExit", "-Command", f'Set-Location "{directory}"'])
            logger.info("Opened PowerShell terminal at %s", directory)
        except Exception as e:
            logger.exception("Error opening PowerShell terminal: %s", e)  # noqa: TRY401

    def _handle_cut_copy(self, paths, operation):
        """Maneja cortar y copiar usando IDataObject del shell"""
        try:
            import pythoncom  # noqa: PLC0415

            # Crear un IDataObject con los archivos
            pidls = []
            for p in paths:
                abs_path = os.path.abspath(p)
                pidl, _ = shell.SHParseDisplayName(abs_path, 0)
                pidls.append(pidl)

            # Usar el método más simple: usar SHCreateDataObject
            try:
                from win32com.shell import SHCreateDataObject  # noqa: PLC0415

                _desktop = shell.SHGetDesktopFolder()

                # Intentar copiar al portapapeles usando el objeto de datos del shell
                dobj = SHCreateDataObject(pidls)

                # Establecer en el portapapeles
                _oleobj = pythoncom.OleGetClipboard(dobj)
                logger.info("Operation '%s' completed for %s items", operation, len)
            except Exception as _e:  # noqa: BLE001
                # Fallback: copiar rutas al portapapeles como texto
                import win32con  # noqa: PLC0415

                text = "\r\n".join([os.path.abspath(p) for p in paths])
                win32api.OpenClipboard(0)
                win32api.EmptyClipboard()
                win32api.SetClipboardData(win32con.CF_UNICODETEXT, text)
                win32api.CloseClipboard()
                logger.info("Fallback: copied paths to clipboard for %s", operation)
        except Exception as e:
            logger.exception("Error in cut/copy: %s", e)  # noqa: TRY401

    def _handle_paste(self, target_folder):
        """Maneja pegar desde el portapapeles"""
        try:
            import win32api  # noqa: PLC0415
            import win32con  # noqa: PLC0415

            win32api.OpenClipboard(0)
            data = win32api.GetClipboardData(win32con.CF_UNICODETEXT)
            win32api.CloseClipboard()

            if data:
                # Obtener archivos del portapapeles (si es un CF_HDROP)
                try:
                    files = win32api.GetClipboardData(win32con.CF_HDROP)
                    # Copiar cada archivo
                    for src_file in files:
                        if os.path.exists(src_file):
                            dst = os.path.join(target_folder, os.path.basename(src_file))
                            if os.path.isdir(src_file):
                                import shutil  # noqa: PLC0415

                                shutil.copytree(src_file, dst, dirs_exist_ok=True)
                            else:
                                import shutil  # noqa: PLC0415

                                shutil.copy2(src_file, dst)
                    logger.info("Pasted %s items to %s", len, target_folder)
                except Exception as _e:  # noqa: BLE001
                    # Es texto, interpretar como rutas
                    source_paths = data.replace("\r\n", "\n").split("\n")
                    for src_file in source_paths:
                        src_file = src_file.strip()  # noqa: PLW2901
                        if src_file and os.path.exists(src_file):
                            dst = os.path.join(target_folder, os.path.basename(src_file))
                            if os.path.isdir(src_file):
                                import shutil  # noqa: PLC0415

                                shutil.copytree(src_file, dst, dirs_exist_ok=True)
                            else:
                                import shutil  # noqa: PLC0415

                                shutil.copy2(src_file, dst)
                    logger.info("Pasted %s items from text to %s", len, target_folder)
        except Exception as e:
            logger.exception("Error in paste: %s", e)  # noqa: TRY401

    def _execute_shell_command(self, hwnd_parent, context_menu, cmd_offset, file_path):
        # cmd_offset ya viene calculado correctamente desde show_context_menu
        verb = ""
        try:
            verb = str(context_menu.GetCommandString(cmd_offset, shellcon.GCS_VERBW)).lower()
        except Exception as e:  # noqa: BLE001
            logger.warning("GetCommandString failed: %s", e)

        logger.info("Shell command: offset=%s, verb='%s', path='%s'", cmd_offset, verb, file_path)

        core_verbs = {
            "properties": shellcon.SEE_MASK_INVOKEIDLIST,
            "open": 0,
            "openas": shellcon.SEE_MASK_INVOKEIDLIST,
            "runas": 0,
        }
        if verb in core_verbs:
            try:
                shell.ShellExecuteEx(
                    lpVerb=verb,
                    lpFile=file_path,
                    nShow=win32con.SW_SHOWNORMAL,
                    fMask=core_verbs[verb] | shellcon.SEE_MASK_NOCLOSEPROCESS,
                )
                logger.info("Executed core verb '%s' via ShellExecuteEx", verb)
                return  # noqa: TRY300
            except Exception as e:
                logger.exception("Failed core verb '%s': %s", verb, e)  # noqa: TRY401

        # ShellExecuteEx con verbo directamente (gitbash, bash, git_gui)
        if verb and verb not in core_verbs:
            try:
                # Directorio trabajo: archivo→su padre, carpeta→ella misma
                if os.path.isfile(file_path):  # noqa: SIM108
                    lpDirectory = os.path.dirname(file_path)  # noqa: N806
                else:
                    lpDirectory = file_path  # noqa: N806

                shell.ShellExecuteEx(
                    lpVerb=verb,
                    lpFile=file_path,
                    lpDirectory=lpDirectory,
                    nShow=win32con.SW_SHOWNORMAL,
                    fMask=shellcon.SEE_MASK_INVOKEIDLIST | shellcon.SEE_MASK_NOCLOSEPROCESS,
                )
                logger.info(
                    f"Executed verb '{verb}' via ShellExecuteEx with directory '{lpDirectory}'"  # noqa: G004
                )
                return  # noqa: TRY300
            except Exception as e:  # noqa: BLE001
                logger.warning("ShellExecuteEx failed for verb '%s': %s", verb, e)

        try:
            verb_val = win32api.LOWORD(cmd_offset)
            cmi = (
                hwnd_parent,
                verb_val,
                None,
                None,
                win32con.SW_SHOWNORMAL,
                0,
                0,
                CMIC_MASK_UNICODE,
            )
            context_menu.InvokeCommand(cmi)
            logger.info("Executed via InvokeCommand with verb_val=%s", verb_val)
        except Exception as e1:  # noqa: BLE001
            logger.warning("InvokeCommand with verb_val failed: %s", e1)
            if verb:
                try:
                    cmi_v = (
                        hwnd_parent,
                        verb,
                        None,
                        None,
                        win32con.SW_SHOWNORMAL,
                        0,
                        0,
                        CMIC_MASK_UNICODE,
                    )
                    context_menu.InvokeCommand(cmi_v)
                    logger.info("Executed via InvokeCommand with verb='%s'", verb)
                except Exception as e2:
                    logger.exception("InvokeCommand with verb failed: %s", e2)  # noqa: TRY401
                    # Último recurso: abrir con ShellExecute
                    win32api.ShellExecute(0, "open", file_path, "", "", win32con.SW_SHOWNORMAL)
                    logger.warning("Fell back to ShellExecute 'open' on '%s'", file_path)


def get_native_menu():
    global _instance  # noqa: PLW0603
    if _instance is None:
        _instance = WindowsNativeMenu()
    return _instance
