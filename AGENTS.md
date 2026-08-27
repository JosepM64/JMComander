# JMcomander — Projecte

## Descripció
Administrador de fitxers de doble panel. Python 3.13 + PySide6.
- **Versió**: 6.9.13 | **Data**: 2026-08-26

## Estructura
```
JMComander/
├── main.py                    # Entry point
├── build.bat                  # Build ràpid
├── src/
│   ├── version.py             # Versió: 6.9.13
│   ├── core/                  # Lògica
│   │   ├── jobs.py, fs_utils.py, config.py, actions.py
│   │   ├── directory_watcher.py   # [NEW v6.8.0] Watcher + polling extret de panel.py
│   │   └── path_history.py        # Historial de navegació
│   ├── ui/                    # UI
│   │   ├── main_window.py
│   │   ├── panel.py               # 1442 línies (vs 1594 a v6.7.5)
│   │   └── components/
│   │       └── breadcrumb_bar.py  # Breadcrumb amb barra de path
│   └── plugins/               # 15 plugins
└── scripts/                   # verify_automatica.py (82 tests)
```

## Com executar
```bat
run.bat
```

## Com compilar
```bat
build.bat
# Resultat: dist/JMComander/JMComander.exe (~200 MB)
```

## Verificació
```bat
python scripts/verify_automatica.py
```

## Dependències específiques
```
send2trash, rarfile, py7zr, paramiko, cryptography, bcrypt, mutagen, numpy, musicbrainzngs
```

## Últimes versions
- **v6.9.12** (2026-08-25): Fase 3 rendiment còpies+MTP
  - MoveJob mateix volum → os.replace instantani; mida calculada 1 cop
  - MtpCopyJob(QRunnable): còpia iPhone en background amb progrés i cancel·lació (CoInitialize propi al worker)
  - _get_shell() singleton COM (4 Dispatch eliminats)
  - TTL negatiu iPhone 5min (evita escaneig COM a cada navegació sense iPhone)
  - ThreadPoolExecutor únic per còpia (no un per directori)
  - Caché detecció SSD per unitat
- **v6.9.13** (2026-08-26): Fase 4 SoC, consolidació d'utilitats i neteja de codi mort
  - format_size consolidat: única funció a core/utils.py, delegada per sync i shell_browser
  - Noms reservats Windows unificats: RESERVED_NAMES = WINDOWS_RESERVED_NAMES ∪ {".git"}
  - Codi mort esborrat: progress_dialog.py (291 línies), _refresh_views, change_directory_dialog, exit_btn
  - Acció "Acerca de" reparada: _show_about crida show_about_dialog
  - Rendiment filtre: fast-path a filterAcceptsRow (fill directe root sense filtre)
  - Duplicar (F9) en background: nou DuplicateJob, evita congelació UI amb carpetes grans
  - toolbar_manager: fix reconstructió del botó de Plugins (métode inexistent)
- **v6.9.11** (2026-08-25): Fase 2 rendiment navegació
  - config.json només es guarda al closeEvent; menú recents lazy (botó pressed)
  - Fix senyal fantasma: path_input textEdited en lloc de textChanged
  - set_active_panel: CSS només quan canvia el color
  - Unificar _on_directory_loaded/_delayed_directory_refresh → _reapply_root_index; sort redundant a set_path eliminat
  - DriveCombo early-exit mateixa unitat; WM_DEVICECHANGE amb force_refresh=True
  - Model: caché mtimes al DisplayRole (1 stat/fitxer per directori carregat)
- **v6.9.10** (2026-08-25): Fase 1 seguretat de dades + bugs
  - MoveJob només esborra originals dels ítems copiats amb èxit (`CopyJob.copied_ok`)
  - send_to_trash mai escala a borrat permanent si la paperera falla
  - Fix fuita connexions botó cancel·lar in-line (disconnect abans de connect)
  - Fix jobs zombis a engine.active_jobs (cancelled també allibera)
  - plugin_manager: sys.path restaurat amb try/finally
- **v6.9.9** (2026-08-05): Vista iPhone amb columnes ordenables
  - Nou `ShellBrowser(QTreeWidget)` (src/ui/components/shell_browser.py) amb columnes Nom/Mida/Data de modificació
  - `list_shell_folder` obté mida i data reals via `GetDetailsOf` (columnes 2 i 3) — MTP no exposa item.Size
  - `_get_item_size` parseja "2,89 MB"/"978 B" a bytes; `_get_item_date` la data
  - Delegate `_SizeSortDelegate`: mostra mida formatada però ordena pel valor numèric
  - panel.py: mode shell usa `shell_browser` (get_selected_paths, invert, select, filter, double-click)
  - Verificat: navegació 93 carpetes → 93 fotos, ordenació per mida numèrica correcta
- **v6.9.8** (2026-08-05): Fix MTP/iPhone — navegació i còpia
  - Bug: a l'iPhone es veien les subcarpetes però no es podia obrir ni copiar res
  - Causa 1: el fallback de navegació shell només descomponia `\SID-{...}` i no els GUIDs `\{xxxx-...}` dels subnivells → mostrava el contingut del pare en lloc del fill
  - Fix 1: `_split_shell_path` + `_descend_shell` — navegació pas a pas per tots els segments (SID o GUID)
  - Fix 2: `copy_shell_items` — còpia MTP amb `Shell.CopyHere` (0x14 silent); `_copy_files`/`_move_files` a actions.py detecten paths shell i usen CopyHere en lloc de shutil
  - Verificat: navegació 3 nivells (Internal Storage → 201906_a → fotos) + còpia de 2 fotos real
- **v6.9.7** (2026-07-13): Fix P0 — crash amb fitxers >2GB (overflow int 32-bit)
  - Causa real del "0% i no es pot cancel·lar": `JobSignals.total_size = Signal(int)` a PySide6 és un int de C++ de 32 bits (màx 2.147.483.647). Amb fitxers >2GB, `total_size.emit()` llençava OverflowError → el job moria a la 1a línia → 0% permanent i sense cancel·lació
  - Fix: `total_size = Signal("qint64")` (64 bits) a jobs.py:27
  - Verificat: move real de 5.91GB C:→E: amb 109 updates de progrés, 6.1s, sense error
- **v6.9.6** (2026-07-13): Fix crític — move es penjava per conflicte no resolt
  - Causa real: el CopyJob intern del MoveJob emetia `conflict` sense cap receptor — si el destí ja té el fitxer, esperava una decisió que mai arribava → 0% infinit
  - Fix: `copy_job.signals.conflict.connect(self.signals.conflict.emit)` perquè l'engine resolgui el conflicte via diàleg
  - Fix: cancel·lació propagada al CopyJob intern (`MoveJob._copy_job.cancel()`)
  - Test: move amb conflicte (overwrite) resolt en 0.1s; 2 fitxers de 600MB amb 160 updates de progrés
- **v6.9.5** (2026-07-13): Fix crític — move entre unitats es penjava
  - Causa: `shutil.move` entre unitats diferents fa copy+delete a cegues, sense progrés ni cancel·lació (models 8GB+ → 0% durant minuts)
  - Fix: MoveJob reutilitza CopyJob (progrés + cancel·lació + paral·lelisme) i elimina originals al final
  - Test: move 300MB amb 88 updates de progrés; cancel·lació preserva l'original
- **v6.9.4** (2026-07-13): Fix crític — còpia de fitxers grans bloquejada
  - Causa: `fdst.truncate(size)` pre-allocava l'espai escrivint zeros; amb 8GB bloquejava la còpia durant minuts (0% i sense cancel·lació)
  - Fix: pre-allocació NOMÉS per fitxers ≤64MB (jobs.py:295 + fs_utils.py:215)
  - Buffer de còpia a jobs.py unificat a 4MB (consistent amb fs_utils)
  - Test: còpia de 200MB amb 59 updates de progrés, sense bloqueig
- **v6.9.3** (2026-07-13): Simplificació progrés — una sola barra
  - Eliminat diàleg modal (ProgressDialog) de les operacions
  - `run_operation_with_dialog` → `run_operation`: només barra in-line al panell ACTIU (no als 2 panells ni barra d'estat)
  - Neteja imports ProgressDialog, botons cancel_btn de la barra d'estat, i referències `_operation_dialog`
- **v6.9.2** (2026-07-13): Còpia paral·lel per directori
  - T7: `ThreadPoolExecutor` (2 workers) copia fitxers en paral·lel dins de cada directori de `copytree_with_progress`
  - `_copy_single_file` extraïda com a funció auxiliar thread-safe; comptadors amb `stats_lock`
  - Callback de progrés protegit amb lock a jobs.py (thread-safe)
- **v6.9.1** (2026-07-13): Cancel·lació in-line + pre-allocació + progrés USB lent
  - T4: Botó X a la barra de progrés in-line (QFrame amb QProgressBar + cancel) — panel.py + main_window.py
  - T5: Pre-allocar fitxer destí amb `fdst.truncate(size)` per reduir fragmentació USB (fs_utils.py + jobs.py)
  - T6: `progress_callback` sempre actiu; mode USB lent avança per temps (0.5s/1%) — cap de congelació visual
- **v6.9.0** (2026-07-13): Optimizacions rendiment + UX
  - T1: Barra de progrés in-line sota el nav_frame (panel.py + main_window.py) — no modal
  - T2: `get_tree_size` amb timeout 1.5s — si USB lent, salta estimació i mostra progrés per fitxers
  - T3: Confirmació abans d'obrir arxius >100MB a unitats lentes (QMessageBox)
  - `fs_utils.py`: buffer 1MB→4MB, eliminat rmtree(dst) previ, throttle callback 1MB
  - `progress_dialog.py`: timer 50ms→100ms, eliminats repaint()/processEvents() redundants
  - Breadcrumb: colors explícits (#1a1a1a/#666) per visibilitat als dos panells
- **v6.8.3** (2026-07-13): Optimització operacions fitxer + breadcrumb
  - P1: `breadcrumb_bar.py` — colors explícits `#1a1a1a`/`#666` en lloc de `palette(text)` per visibilitat al panell inactiu
  - P1: `main_window.py` — estils `#navFrame`/`BreadcrumbBar` al `set_active_panel`
  - P2: `fs_utils.py` — buffer 1MB→4MB, eliminat `rmtree(dst)` previ (bloquejava a USB), throttle callback cada ~1MB
  - P2: `progress_dialog.py` — timer 50ms→100ms, eliminat `repaint()`/`processEvents()` redundants
  - Fix: `breadcrumb_bar.py` — capturar el widget una sola vegada abans de `setParent(None)`/`deleteLater()` a `_rebuild()` (evita `AttributeError` a `item.widget()` al segon `set_path()`)
- **v6.8.0** (2026-07-07): Refactor profund SoC
  - P0: `breadcrumb_bar.py` — `setParent(None)` abans de `deleteLater()` per evitar widgets penjats visualment
  - P1: `panel.py` — `path_changed` signal com a única font de veritat; nav widgets (breadcrumb, path_input, drive_combo, tabs) s'actualitzen via signal handler `_on_path_changed_update_nav`
  - P2a: `src/core/directory_watcher.py` — nou; watcher + polling extret de panel.py
  - P2b: `set_path` descompost en `_apply_to_model`, `_apply_to_archive`, `_push_history`, `_on_path_changed_update_nav`
  - `panel.py` −152 línies (1594 → 1442)
  - P3: `core/actions.py` — `ActionContext` + handlers per copy/move/delete/terminal/create_folder/view/edit; `main_window.py` delega via `_run_action()`, −10 imports inlines
  - Build verificat: `PyInstaller` v6.22.2 (rebuild 18/08/2026)
- **v6.7.1**: Fallback directori usuari si USB desconnectat
- **v6.7.0**: Neteja Ruff 0 errors, 80/80 tests
- **v6.6.0**: Neteja codi mort, imports, fitxers orfes

 Versions anteriors: veure `CHANGELOG.md`

## Fixos recents
- **2026-07-29**: Breadcrumb / DriveCombo bug deixa el DriveCombo en "Local"
  - Causa: a `_rebuild()` el widget es capturava dues vegades; al segon `set_path()` el widget ja estava garbage-collectejar i `item.widget()` llançava `AttributeError`, tallant `_on_path_changed_update_nav`
  - Fix: capturar el widget una sola vegada a la variable local abans de `setParent(None)`/`deleteLater()` a `breadcrumb_bar.py`
- **2026-07-07**: Breadcrumb no s'actualitzava en navegar per bookmarks
  - Causa: `deleteLater()` sense `setParent(None)` a `_rebuild` — widgets vells seguien renderitzant-se
  - Fix: `item.widget().setParent(None)` abans de `deleteLater()` a `breadcrumb_bar.py:118`
  - Addicional: refactor P1+P2 per prevenir bugs similars
- **2026-06-30**: Botons Terminal/PowerShell no funcionaven
  - Causa: `shell=True` en `subprocess.Popen` doblava wrapping amb `cmd.exe /c`, i PowerShell usava cometes simples
  - Fix: eliminar `shell=True` de `main_window.py:533` i `native_menu.py:613,624`; PowerShell amb `f'Set-Location "{path}"'`

## Arquitectura d'accions (P3)

```
main_window.py                core/actions.py
─────────────────             ──────────────
setup_actions()               ActionRegistry + ActionContext
setup_function_bar()          handlers: _copy_files, _delete_files, etc.
  ↓ via _run_action("id")     ↓ ctx.active_panel, ctx.engine, ctx.parent
```

- `ActionContext` conté: `active_panel`, `inactive_panel`, `engine`, `bookmarks`, `parent`, `run_operation`, `refresh_bookmarks_bar`, `update_bookmarks_menu`
- Per afegir una acció nova: (1) crear handler `_fn(ctx)` a `actions.py`, (2) registrar amb `action_registry.register(Action(id="...", handler=_fn))`, (3) cridar des de main_window amb `self._run_action("id")`
- Les accions sense handler (pures UI: rename, select_all, etc.) es queden a main_window
- Els handlers d'accions NO importen MainWindow — només `ActionContext`

## Regles
- Pre-run: `verify_automatica.py` abans de cada build
- No tocar git sense permís
- Build: `build.bat` des de l'arrel del projecte (paths relatius al `.spec`)
- Si es crea un fitxer .py nou al core, afegir-lo a `hiddenimports` del `.spec`
- `DirectoryWatcher` es crea a `panel.py` i es connecta via `directory_changed → _on_watcher_refresh`
- El breadcrumb `_rebuild` ha de fer `setParent(None)` + `deleteLater()` per evitar artefactes visuals
- `ActionContext` es construeix via property `_action_context` a MainWindow — no cal crear-lo manualment
