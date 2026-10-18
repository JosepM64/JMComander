"""Utilitats centralitzades per obrir terminals (CMD, PowerShell, WezTerm).

Aquest mòdul només usa la llibreria estàndard (sense Qt ni win32) perquè
l'importin tant `src/core/actions.py` com `src/ui/native_menu.py`.

WezTerm CLI: `wezterm start --cwd <dir>` obre una finestra nova al directori.
Si l'executable no es troba, `open_wezterm()` retorna False i el cridant
mostra l'avís + fallback (normalment PowerShell).
"""

import logging
import os
import shutil
import subprocess

logger = logging.getLogger(__name__)

_WEZTERM_EXE_NAMES = ("wezterm.exe", "wezterm")

# Rutes típiques d'instal·lació a Windows (més enllà del PATH)
_WEZTERM_PATH_CANDIDATES = (
    r"%ProgramFiles%\WezTerm\wezterm.exe",
    r"%ProgramFiles(x86)%\WezTerm\wezterm.exe",
    r"%LOCALAPPDATA%\Programmes\WezTerm\wezterm.exe",
    r"%USERPROFILE%\scoop\shims\wezterm.exe",
    r"%USERPROFILE%\scoop\apps\wezterm\current\wezterm.exe",
)


def _check_registry_app_path() -> str | None:
    """Mira HKLM/HKCU ...\\App Paths\\wezterm.exe (on escriuen els instal·ladors)."""
    try:
        import winreg  # noqa: PLC0415

        for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for key_path in (
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\wezterm.exe",
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\wezterm-gui.exe",
            ):
                try:
                    with winreg.OpenKey(root, key_path) as key:
                        value, _ = winreg.QueryValueEx(key, "")
                        if value and os.path.isfile(str(value)):
                            return str(value)
                except OSError:
                    continue
    except Exception as e:  # noqa: BLE001
        logger.debug("Registry lookup for wezterm failed: %s", e)
    return None


def find_wezterm_exe() -> str | None:
    """Retorna la ruta de l'executable de WezTerm o None si no està instal·lat."""
    for name in _WEZTERM_EXE_NAMES:
        found = shutil.which(name)
        if found:
            return found
    for candidate in _WEZTERM_PATH_CANDIDATES:
        expanded = os.path.expandvars(candidate)
        if os.path.isfile(expanded):
            return expanded
    return _check_registry_app_path()


def is_wezterm_available() -> bool:
    """True si WezTerm està instal·lat i localitzable."""
    return find_wezterm_exe() is not None


def build_wezterm_command(exe: str, directory: str) -> list:
    """Construeix `wezterm start [--cwd dir]`; sense --cwd si el dir no és vàlid."""
    cmd = [exe, "start"]
    if directory and os.path.isdir(directory):
        cmd += ["--cwd", directory]
    return cmd


def open_wezterm(directory: str) -> bool:
    """Obre WezTerm al directori. Retorna True si s'ha llançat, False si no
    està instal·lat o ha fallat (el cridant fa fallback + avís)."""
    exe = find_wezterm_exe()
    if not exe:
        logger.warning("WezTerm not found, fallback needed (cwd=%s)", directory)
        return False
    try:
        subprocess.Popen(build_wezterm_command(exe, directory))
    except Exception as e:
        logger.exception("Error opening WezTerm: %s", e)  # noqa: TRY401
        return False
    else:
        logger.info("Opened WezTerm at %s", directory)
        return True
