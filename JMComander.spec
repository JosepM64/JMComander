# -*- mode: python ; coding: utf-8 -*-

import sys
import os
import PySide6

# Obtener la ruta de PySide6 (suporta tant pip com conda)
_PS6_FILE = getattr(PySide6, "__file__", None)
if _PS6_FILE:
    _PS6_ROOT = os.path.dirname(_PS6_FILE)
else:
    _PS6_PATH = PySide6.__path__[0] if PySide6.__path__ else None
    _PS6_ROOT = os.path.dirname(_PS6_PATH) if _PS6_PATH else None

# Localitzar plugins Qt (pip vs conda layout)
def _find_qt6_plugins():
    """Troba els plugins Qt6: pip els posa a PySide6/qt6/plugins, conda a Library/lib/qt6/plugins"""
    candidates = []
    if _PS6_ROOT:
        candidates.append(os.path.join(_PS6_ROOT, 'PySide6', 'plugins'))
        candidates.append(os.path.join(_PS6_ROOT, 'qt6', 'plugins'))
        candidates.append(os.path.join(_PS6_ROOT, 'plugins'))
    # Layout típic de conda
    candidates.append(os.path.join(sys.base_prefix, 'Library', 'lib', 'qt6', 'plugins'))
    # Layout per si el prefix de conda és un entorn
    _conda_env = os.environ.get('CONDA_PREFIX', '')
    if _conda_env:
        candidates.append(os.path.join(_conda_env, 'Library', 'lib', 'qt6', 'plugins'))
    for c in candidates:
        if c and os.path.isdir(os.path.join(c, 'platforms')):
            return c
    return None

_plugin_dir = _find_qt6_plugins()

# Incluir archivos JSON, plugins e iconos si existen
datas = [
    ('src\\plugins', 'src\\plugins'),
    ('src\\assets\\icon_theme.py', 'src\\assets'),
    ('src\\assets\\icons', 'src\\assets\\icons'),
    ('src\\assets\\jmcomander.ico', 'assets'),
    ('src\\assets\\jmcomander.png', 'assets'),
    ('src\\toolbar_constants.py', 'src'),
    ('src\\core\\__init__.py', 'src\\core'),
    ('src\\core\\jobs.py', 'src\\core'),
    ('src\\core\\file_constants.py', 'src\\core'),
    ('src\\core\\mtp_handler.py', 'src\\core'),
    ('src\\core\\utils.py', 'src\\core'),
    ('src\\core\\json_store.py', 'src\\core'),
    ('src\\assets\\icon_utils.py', 'src\\assets'),
    ('src\\ui', 'src\\ui'),
    ('src\\__init__.py', 'src'),
]

# Añadir plugins de Qt necesarios para cargar SVG
_plugin_dir = os.path.join(_PS6_ROOT, 'plugins')
if os.path.exists(_plugin_dir):
    datas.append((os.path.join(_plugin_dir, 'imageformats'), 'plugins\\imageformats'))
    if os.path.exists(os.path.join(_plugin_dir, 'iconengines')):
        datas.append((os.path.join(_plugin_dir, 'iconengines'), 'plugins\\iconengines'))
    if os.path.exists(os.path.join(_plugin_dir, 'platforms')):
        datas.append((os.path.join(_plugin_dir, 'platforms'), 'plugins\\platforms'))
        print(f"Incluyendo platforms desde: {os.path.join(_plugin_dir, 'platforms')}")

binaries = []

# Añadir DLLs de Windows necesarias para papelera y operaciones de sistema
if sys.platform == 'win32':
    binaries.append(('C:\\Windows\\System32\\shell32.dll', '.'))
    
    # UnRAR DLL para soporte de archivos RAR
    unrar_dll = 'src\\assets\\UnRAR64.dll'
    if os.path.exists(unrar_dll):
        binaries.append((unrar_dll, 'assets'))
        print(f"Incluyendo UnRAR64.dll en assets/: {unrar_dll}")
    
    unrar_exe = 'src\\assets\\UnRAR.exe'
    if os.path.exists(unrar_exe):
        binaries.append((unrar_exe, 'assets'))
        print(f"Incluyendo UnRAR.exe CLI en assets/: {unrar_exe}")
    else:
        print("ADVERTENCIA: UnRAR.exe no encontrado.")

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=[
        # PySide6 core
        'PySide6',
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'PySide6.QtSvg',
        'PySide6.QtNetwork',
        'PySide6.QtXml',
        'PySide6.QtSvgWidgets',
        'PySide6.QtPrintSupport',
        'shiboken6',
        'shiboken6.Shiboken',
        'shiboken6.loader',
        # PIL/Pillow
        'PIL',
        'PIL.Image',
        'PIL.PngImagePlugin',
        'PIL.JpegImagePlugin',
        'PIL.GifImagePlugin',
        'PIL.TiffImagePlugin',
        'PIL.WebPImagePlugin',
        'PIL.BmpImagePlugin',
        'PIL.TgaImagePlugin',
        # pillow-heif for HEIC/HEIF (iPhone)
        'pillow_heif',
        'pillow_heif.HeifFile',
        # Windows
        'win32com',
        'win32com.client',
        'win32com.shell',
        'win32com.shell.shell',
        'win32gui',
        'win32con',
        'pythoncom',
        'send2trash',
        'send2trash.plat_win',
        # Remote
        'paramiko',
        'cryptography',
        'bcrypt',
        'nacl',
# Archives
    'rarfile',
    'py7zr',
    'py7zr.callbacks',
    # UI modules (necessaris per PyInstaller)
    'src.ui.panel',
    'src.ui.main_window',
    'src.ui.progress_dialog',
    'src.ui.conflict_dialog',
    'src.ui.search_dialog',
    'src.ui.settings_dialog',
    'src.ui.bookmarks_editor',
    'src.ui.app_launcher_editor',
    # Eliminado: src.ui.secure_delete_dialog (eliminado en v6.6.0)
    'src.ui.quick_look',
    'src.ui.components.breadcrumb_bar',
    # Core modules
    'src.core.file_constants',
    'src.core.mtp_handler',
    'src.core.utils',
    'src.core.json_store',
    'src.core.taskbar_progress',
    'src.core.directory_watcher',
    'src.ui.file_system_model',
    # Email needed by importlib.metadata (py7zr -> bcj)
    'email',
    'email.mime',
    'email.mime.text',
    'email.mime.multipart',
    'email.mime.base',
    'email.charset',
    'importlib_metadata',
    'src.assets.icon_utils',
    # Plugins que carreguen dinàmicament (PyInstaller no els detecta)
    'src.core.plugin_settings',
    # Remote plugin
    'ftplib',
],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'test',
        'pydoc',
        'pdb',
        'unittest',
        'pip',
        'setuptools',
        'numpy',
        'scipy',
        'html',
        'http',
        'xml',
        'xmlrpc',
        'ensurepip',
        'venv',
        'lib2to3',
        'msilib',
        'msvcrt',
        'curses',
        'idlelib',
        'tcl',
        'ttk',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='JMComander',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="src/assets/jmcomander.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='JMComander',
)
