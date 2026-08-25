import ctypes
import logging
import sys

logger = logging.getLogger(__name__)


class TaskbarProgress:
    TBPF_NOPROGRESS = 0
    TBPF_INDETERMINATE = 0x1
    TBPF_NORMAL = 0x2
    TBPF_ERROR = 0x4
    TBPF_PAUSED = 0x8

    def __init__(self, hwnd):
        self.hwnd = hwnd
        self._taskbar = None
        self._init_taskbar()

    def _init_taskbar(self):
        if sys.platform != "win32":
            return
        try:
            _shell32 = ctypes.windll.shell32
            _clsid = ctypes.CLSIDFromString
            _iid = ctypes.WinDLL("ole32.dll").CoCreateInstance
            _i_taskbar_list3 = ctypes.windll.shell32.ITaskbarList3
            _iid_taskbar = ctypes.UUID("{56FDF344-FD6D-11d0-958A-006097C9A090}")
            self._taskbar = ctypes.windll.shell32.ITaskbarList3()
            self._taskbar.HrInit()
        except Exception:  # noqa: BLE001
            self._taskbar = None

    def set_progress(self, current, total):
        if not self._taskbar or not self.hwnd:
            return
        try:
            self._taskbar.SetProgressState(self.hwnd, self.TBPF_NORMAL)
            self._taskbar.SetProgressValue(self.hwnd, current, total)
        except Exception:  # noqa: BLE001
            pass

    def set_state(self, state):
        if not self._taskbar or not self.hwnd:
            return
        try:
            self._taskbar.SetProgressState(self.hwnd, state)
        except Exception:  # noqa: BLE001
            pass

    def clear(self):
        self.set_state(self.TBPF_NOPROGRESS)
