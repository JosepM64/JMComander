import logging

from src.core.json_store import JsonStore

logger = logging.getLogger(__name__)

_DEFAULT_APPS = [
    {"name": "Notepad", "path": "notepad.exe", "args": ""},
    {"name": "Calculadora", "path": "calc.exe", "args": ""},
    {"name": "Paint", "path": "mspaint.exe", "args": ""},
]


class AppLauncher:
    def __init__(self, filepath="apps.json"):
        self._store = JsonStore(filepath)
        if not self._store.get_all():
            self._store.set_items(_DEFAULT_APPS)

    def load(self):
        return self._store.load()

    def save(self):
        self._store.save()

    def add_app(self, name, path, args=""):
        return self._store.add({"name": name, "path": path, "args": args}, unique_key="path")

    def remove_app(self, index):
        return self._store.remove(index)

    def update_app(self, index, name, path, args=""):
        return self._store.update(index, {"name": name, "path": path, "args": args})

    def move_up(self, index):
        return self._store.move_up(index)

    def move_down(self, index):
        return self._store.move_down(index)

    def get_all(self):
        return self._store.get_all()


app_launcher = AppLauncher()
