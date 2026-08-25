from datetime import UTC, datetime

from PySide6.QtCore import QObject, QRunnable, Signal
from PySide6.QtWidgets import QMessageBox

from src.core.engine import OperationEngine

"""
PluginAPI - API mínima y segura para plugins

Esta clase proporciona acceso controlado a las funcionalidades de JMComander.
Los plugins NO pueden acceder directamente a Qt ni a main_window.
"""

import logging  # noqa: E402
import os  # noqa: E402
from collections.abc import Callable  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Protocol  # noqa: E402

logger = logging.getLogger(__name__)


class PanelProtocol(Protocol):
    @property
    def current_path(self) -> str: ...
    def get_selected_paths(self) -> list[str]: ...
    def refresh(self): ...
    def set_path(self, path: str): ...
    def select_and_focus(self, path: str): ...
    def select_paths(self, paths: list[str]): ...


class PluginAPI:
    def __init__(
        self,
        main_window,
        show_message_cb: Callable | None = None,
        confirm_cb: Callable | None = None,
    ):
        self._mw = main_window
        self._show_message_cb = show_message_cb
        self._confirm_cb = confirm_cb

    @property
    def active_panel(self) -> PanelProtocol:
        return self._mw.active_panel

    @property
    def passive_panel(self) -> PanelProtocol:
        return self._mw.inactive_panel

    @property
    def left_panel(self) -> PanelProtocol:
        return self._mw.left_panel

    @property
    def right_panel(self) -> PanelProtocol:
        return self._mw.right_panel

    @property
    def current_path(self) -> str:
        return self._mw.active_panel.current_path

    def selected_files(self) -> list[Path]:
        paths = self._mw.active_panel.get_selected_paths()
        return [Path(p) for p in paths if p and os.path.exists(p)]

    def run_job(self, fn, *, description: str = "Procesando"):

        class _JobSignals(QObject):
            progress = Signal(int, int)
            finished = Signal()
            error = Signal(str)

        class _JobAdapter(QRunnable):
            def __init__(self, func, desc, signals):
                super().__init__()
                self.func = func
                self.desc = desc
                self.signals = signals
                self._cancelled = False

            def cancel(self):
                self._cancelled = True

            def run(self):
                try:
                    self.func(self.signals.progress.emit)
                    self.signals.finished.emit()
                except Exception as e:  # noqa: BLE001
                    self.signals.error.emit(str(e))

        signals = _JobSignals()
        job = _JobAdapter(fn, description, signals)
        self._mw.run_operation(job, description)

    def show_message(self, text: str, level: str = "info"):
        if self._show_message_cb:
            self._show_message_cb(text, level)
            return

        level_map = {
            "info": QMessageBox.Icon.Information,
            "warning": QMessageBox.Icon.Warning,
            "error": QMessageBox.Icon.Critical,
        }
        icon = level_map.get(level, QMessageBox.Icon.Information)
        QMessageBox(icon, "JMComander", text).exec()

    def confirm(self, text: str) -> bool:
        if self._confirm_cb:
            return self._confirm_cb(text)

        return (
            QMessageBox.question(
                None,
                "JMComander",
                text,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            == QMessageBox.StandardButton.Yes
        )

    def copy(self, src: str, dst: str):

        engine = OperationEngine.instance(self._mw)
        self._mw.run_operation(
            engine.queue_copy([src], dst), f"Copiando {os.path.basename(src)}"
        )

    def move(self, src: str, dst: str):

        engine = OperationEngine.instance(self._mw)
        self._mw.run_operation(
            engine.queue_move([src], dst), f"Moviendo {os.path.basename(src)}"
        )

    def get_parent_window(self):
        return self._mw

    def delete(self, paths: list[str]):

        engine = OperationEngine.instance(self._mw)
        self._mw.run_operation(
            engine.queue_delete(paths), f"Eliminando {len(paths)} elementos"
        )

    def refresh_panel(self):
        self._mw.active_panel.refresh()

    def open_file(self, path: str):
        try:
            os.startfile(path)
        except Exception as e:
            logger.exception("Error abriendo %s: %s", path, e)  # noqa: TRY401
            self.show_message(f"No se pudo abrir: {e}", "error")

    def get_files_info(self, paths: list[str]) -> list[dict]:

        result = []
        for p in paths:
            if os.path.exists(p):
                stat = os.stat(p)
                result.append(
                    {
                        "name": os.path.basename(p),
                        "path": p,
                        "size": stat.st_size,
                        "is_dir": os.path.isdir(p),
                        "modified": datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
                    }
                )
        return result

    def compare_paths(self, path1: str, path2: str, recursive: bool = False) -> dict:
        if not os.path.isdir(path1) or not os.path.isdir(path2):
            return {"error": "Ambas rutas deben ser directorios"}

        def list_files(path, recursive_mode):
            files = set()
            if not recursive_mode:
                for item in os.scandir(path):
                    entry = item.name
                    if item.is_dir():
                        entry += "/"
                    files.add(entry)
            else:
                for root, dirs, filenames in os.walk(path):
                    rel_root = os.path.relpath(root, path)
                    if rel_root == ".":
                        rel_root = ""
                    # Normalize separators to forward slash
                    rel_root = rel_root.replace("\\", "/")
                    for d in dirs:
                        entry = d + "/"
                        if rel_root:
                            entry = rel_root + "/" + entry
                        files.add(entry)
                    for name in filenames:
                        if rel_root:
                            files.add(rel_root + "/" + name)
                        else:
                            files.add(name)
            return files

        files1 = list_files(path1, recursive)
        files2 = list_files(path2, recursive)

        only_in_1 = sorted(files1 - files2)
        only_in_2 = sorted(files2 - files1)

        common = files1 & files2
        different = []
        same = []

        for f in common:
            full1 = os.path.normpath(os.path.join(path1, f.replace("/", os.sep)))
            full2 = os.path.normpath(os.path.join(path2, f.replace("/", os.sep)))
            is_dir1 = os.path.isdir(full1)
            is_dir2 = os.path.isdir(full2)
            if is_dir1 and is_dir2:
                same.append(f)
            elif is_dir1 != is_dir2:
                different.append(f)
            elif os.path.isfile(full1) and os.path.isfile(full2):
                if os.path.getsize(full1) != os.path.getsize(full2):
                    different.append(f)
                else:
                    same.append(f)

        return {
            "only_in_1": only_in_1,
            "only_in_2": only_in_2,
            "different": different,
            "same": same,
        }

