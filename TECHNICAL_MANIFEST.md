# JMComander — Manifest Tècnic

## Arquitectura actual (v6.9.9)

### Estructura SoC
```
src/
├── version.py              # Versió actual: 6.9.9
├── ui/
│   ├── main_window.py      # Finestra principal (533 línies + 3 mixins)
│   ├── panel.py            # Panel de fitxers (sorting, filtres, pestanyes)
│   ├── native_menu.py      # Menú contextual Windows (Win32)
│   ├── file_system_model.py # Models Qt (ExtendedFileSystemModel)
│   ├── components/         # DriveCombo, ArchiveBrowser, ShellBrowser, FolderTabBar, BreadcrumbBar
│   └── dialogs/            # DirectoryHotlist, SyncDirs, QuickHelp, etc.
├── core/
│   ├── jobs.py             # BaseJob + ConflictMixin + 4 subclasses
│   ├── fs_utils.py         # copytree_with_progress, should_overwrite_file
│   ├── path_history.py     # Historial back/forward (màx 50 entrades)
│   ├── config.py           # Configuració JSON
│   ├── plugin_manager.py   # Sistema de plugins
│   ├── plugin_api.py       # API per plugins
│   ├── plugin_settings.py  # Helper càrrega/desament config
│   ├── json_store.py       # Base class CRUD
│   ├── directory_watcher.py# Watcher + polling (v6.8.0)
│   ├── actions.py          # ActionContext + registre accions (v6.8.0)
│   └── archive_handler.py  # RAR/7-Zip/ZIP
└── plugins/                # 15 plugins inclosos
```

### Convencions clau

| Àrea | Convenció |
|------|-----------|
| Indentació | 4 espais |
| Imports | `src.*` (no relatius) |
| Senyals Qt | Mètodes `_on_*` |
| Plugins | Reben `api` (PluginAPI), no `main_window` |
| Tests | `verify_automatica.py` (82 tests) abans de cada build |
| Build | `build.bat` → PyInstaller → `dist/JMComander/` (~200 MB) |

### Dependències principals
```
PySide6, PyInstaller, send2trash, psutil, Pillow, pillow-heif,
rarfile, py7zr, paramiko, cryptography, bcrypt, mutagen, numpy, musicbrainzngs
```

### Problemes coneguts
- `conda run` NO funciona (espais al username `JM DJ`)
- PySide6 sempre via pip, mai conda-forge
- `build.bat` usa path directe python.exe

### Últimes versions
- **v6.8.3**: Fix P0 breadcrumb/DriveCombo (captura widget una sola vegada a `_rebuild`)
- **v6.8.0**: Refactor SoC — `path_changed` signal, `DirectoryWatcher` (core), `actions.py` (ActionContext core)
- **v6.7.2**: Fix terminal (CMD/PowerShell via shell=True)
- **v6.7.1**: Fallback directori usuari si USB desconnectat
- **v6.7.0**: Neteja Ruff 0 errors, 80/80 tests
- **v6.6.0**: Neteja codi mort, imports, fitxers orfes
- **v6.5.0**: Plugin sincronitzar carpetes
