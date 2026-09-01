# Changelog JMComander

## Versió 6.9.22 - Agost 2026

### UI — Barra de progrés de còpia/moviment mostra nom del fitxer
- `src/ui/panel.py`: etiqueta `inline_progress_label` a la barra de progrés in-line; `show_inline_progress` accepta text.
- `src/ui/main_window.py`: `_on_dialog_progress` passa text del senyal; `_on_inline_file_started` actualitza l'etiqueta quan comença un fitxer nou.
- L'usuari veu ara "filename (current/total)" mentre es copia/mou, en lloc de només la barra.

## Versió 6.9.21 - Agost 2026

### Fix — F:\ protegit contra escritura + error visible
- **F:\ Kingston `IsReadOnly=True` (WinError 19)**: `F:\` està en només lectura a nivell de disc (`Get-Disk 3 IsReadOnly True`) malgrat `diskpart clear readonly` — per això no apareixia barra (fallava `os.makedirs` i es confonia amb cancel). Ara `CopyJob:278` distingeix `is_cancelled` vs error real i emet `error` amb missatge "medio protegido contra escritura" + `main_window.py:929` mostra `QMessageBox.critical`
- **Verificat**: `F:\` NO escrivible (root i `F:\Varis` fallen), `D:\` SÍ escrivible (15 fitxers PASS) — si vas copiar avui a F:\, el disc ha passat a només lectura després (fallada típica Kingston per desgast)

## Versió 6.9.20 - Agost 2026

### Fix crític — còpia buida + 8x més ràpid estable
- **Bug carpetes buides 6.9.19**: `global futures` sense barrera fallava en certs casos (només `makedirs` sense fitxers) → revertit a per-directori robust amb `futures` correcte (`fs_utils.py:286` indent fix) + `CopyFileW` per tots + 8 workers → bench 0.17s, test recursiu 9/9 PASS
- **Conserva parcial**: `CopyJob:278` NO esborra al cancel·lar (15ms) — abans esborrava feina feta

## Versió 6.9.19 - Agost 2026

### Fase 5.1 — Rendiment còpies grans 9x + cancel conserva parcial
- **Cancel conserva**: `CopyJob:278` ja NO esborra `dst` parcial al cancel·lar — abans `rmtree` síncron (6.9.17) i async (6.9.18) eliminava feina feta i l'usuari havia de recomençar; ara `cancelled` en 15ms i destí intacte amb el copiat fins al moment
- **9x més ràpid**: `CopyFileW` per TOTS els fitxers (abans loop Python 4MB només >64MB) + `PARALLEL_COPY_WORKERS` 4→8 (`min(8, cpu*2)`) + global futures sense barrera per directori (`fs_utils.py:19,157,252`) → bench 502 fitxers/47MB 1.34s→0.15s
- **Estructura instantània**: `os.makedirs` sense esperar futures; l'usuari veu carpetes immediatament mentre fitxers copien en paral·lel
- **Parcial per fitxer**: cancel a mitges conserva fitxer parcial sense `os.remove` (`fs_utils.py:244`)

## Versió 6.9.18 - Agost 2026

### Fase 5 — Rendiment còpies grans + cancel·lació instantània
- **Cancel·lació instantània**: `CopyJob` `shutil.rmtree` del destí parcial ara en `Thread` daemon (`jobs.py:273`) — abans bloquejava la UI segons/minuts amb carpetes grans; senyal `cancelled` en ~30ms (verificat bench 15-30ms), neteja async després
- **Paral·lelisme 2→4 workers**: `PARALLEL_COPY_WORKERS = min(4, cpu_count())` (`fs_utils.py:19`) guanya ~30-50% en SSD amb molts fitxers petits; HDD penal mínima
- **`get_tree_size` 1.5s→0.8s**: carpetes grans comencen a copiar abans; `total_size=0` usa fallback time-based de `jobs.py:233` ja existent
- **Fast-path `CopyFileW`**: fitxers >64MB usen `kernel32.CopyFileW` natiu (~20-40% més ràpid) amb fallback a loop Python si falla (`fs_utils.py:173`)
- **Cancel futures**: `as_completed` cancel·la futures pendents immediatament i propaga `None` de workers (`fs_utils.py:289`)

## Versió 6.9.17 - Agost 2026

### Millores d'Estabilitat
- **`disk_space` drill-down**: es cancel·la l'escanys previ avant d'iniciar un nou escaneig per a evitar condicions de carreira que podien produir el tancament improvès del programa al navegar rapidament per carpetes.

## Versió 6.9.16 - Agost 2026

### Nova funcionalitat
- **`disk_space` esborrat de carpetes des del drill-down**: el panell de vista d'arbre (Carpeta/Mida/%) ara permet esborrar les carpetes seleccionades. Dos modes:
  - **Eliminar (Paperera)**: mou a la paperera via `core.fs_utils.safe_delete(use_trash=True)` amb una sola confirmació.
  - **Eliminar Permanent**: esborra amb `shutil.rmtree` amb **doble confirmació** (avís + confirmació final).
  - El borrat s'executa en segon pla (`DeleteFoldersWorker`) per no congelar la UI amb carpetes grans, i en acabar es re-escaneja el directori actual per refrescar l'arbre. Els errors es reporten en un sol diàleg.

## Versió 6.9.14 - Agost 2026

### Correccions
- **`disk_space` arrencava al directori actiu**: el plugin començava a escanejar allà on estaves navegant (ex. `C:\Users\JM` o `D:\Documents\BBF\2025`). Ara puja a l'arrel del disc (`os.path.splitdrive`) i mostra una vista global de la unitat. Des del tree, doble-clic a una carpeta per drill-down.
- **`disk_space` no apareixia al menú**: la funció `register()` cridava `api.register_action()` però ja ho feia el `plugin.json`. Doble registre provocava que el plugin quedés ocult. Ara `register()` és `pass` (com la resta de plugins) i el registre ve només de `plugin.json`.
- **`image_converter` ignorava el checkbox de proporcions**: el resize només s'aplicava si ambdues dimensions estaven plenes. Ara, si "Mantener proporción" està marcat, calcular la dimensió que falta a partir de la mida original. Si ambdues estan plenes, s'apliquen tal qual (voluntat explícita).
- **`disk_space` drill-down recursiu (nou)**: vista d'arbre (Carpeta/Mida/%) amb escaneig en background (`FolderSizeWorker` + `os.scandir`), percentatges calculats al final, botó "← Subir" per navegar cap amunt i "Obrir al Explorador" per obrir la carpeta seleccionada.

## Versió 6.9.13 - Agost 2026

### Fase 4 — SoC, consolidació d'utilitats i neteja de codi mort
- **`format_size` consolidat**: era duplicada en 6 llocs (core/utils, sync, panel, shell_browser, progress_dialog, conflict_dialog). Ara és una sola funció a `core/utils.py`; shell_browser i sync hi deleguen.
- **Noms reservats Windows unificats**: `RESERVED_NAMES` (fs_utils) i `_WINDOWS_SPECIAL_FILES` (utils) eren gairebé idèntics — ara `RESERVED_NAMES = set(WINDOWS_RESERVED_NAMES) | {".git"}`.
- **Codi mort esborrat**: `progress_dialog.py` sencer (291 línies, cap importador), `_refresh_views`, `change_directory_dialog`, `_on_shell_item_clicked` (slot buit) i el botó `exit_btn` (mai mostrat).
- **Acció "Acerca de" reparada**: estava registrada sense handler (el menú Ajuda→About no feia res). Ara `_show_about` crida `show_about_dialog`.
- **Rendiment filtre de fitxers**: `filterAcceptsRow` retorna directament pel cas comú (fill directe del root sense filtre) — abans recorria la cadena de pares 2 cops per fila; eliminat el spam de `logger.debug` per cada fitxer de C:\ a l'arrencada.
- **Duplicar (F9) en background**: nou `DuplicateJob(QRunnable)` — abans `shutil.copytree` síncron congelava la UI amb carpetes grans.
- **toolbar_manager**: arreglada la reconstrucció del botó de Plugins (referia un mètode inexistent).

## Versió 6.9.12 - Agost 2026

### Fase 3 — Rendiment còpies i MTP/iPhone
- **Moure dins del mateix disc ara és instantani**: `os.replace` directe en lloc de copiar+esborrar (~×1000 més ràpid); la ruta lenta queda només per a moviments entre unitats. La mida ja no es calcula dues vegades (MoveJob delegava el càlcul al CopyJob intern que el repetia).
- **Còpia des de l'iPhone sense congelar la UI**: nou `MtpCopyJob(QRunnable)` amb barra de progrés in-line i cancel·lació; abans la navegació COM + CopyHere era síncrona al thread principal (minuts de congelació amb moltes fotos). El job usa el seu propi apartament COM (`CoInitialize`) per seguretat de threads.
- **Singleton COM Shell.Application**: es creava un `Dispatch` a cada crida (~100ms cada una, 4 punts). Ara `_get_shell()` reutilitza la instància.
- **Escaneig d'iPhone només quan cal**: TTL negatiu de 5 minuts (abans 30s) — en màquines sense iPhone, cada navegació disparava una enumeració COM completa d'"Aquest PC".
- **Un sol ThreadPoolExecutor per còpia** (abans es creava/destruïa un per directori visitat).
- **Caché de detecció SSD** per unitat: cada esborrat segur pagava 0.5-10s arrencant PowerShell; ara 0ms a partir del primer.
- Tests verificats: rename instantani mateix volum, skip preserva original, caché SSD 2a crida 0ms, MtpCopyJob destí invàlid no bloqueja.

## Versió 6.9.11 - Agost 2026

### Fase 2 — Optimització del camí calent de navegació
Ara mateix cada clic de navegació feia: escriptura de config.json a disc + reconstrucció del menú de recents + 6 setStyleSheet nous + triple ordenació O(n log n) + reconstrucció completa del combo d'unitats amb crides Win32 que podien blocar.

- **config.json**: `add_recent_path` només muta en memòria (el save fa el closeEvent). El menú de recents es reconstrueix lazy al prémer el botó, no a cada navegació.
- **Senyal fantasma eliminada**: el QLineEdit ocult del path emetia `focused` a cada `set_path` (textChanged s'activa amb setText) → canviava el panell actiu sense interacció. Fix: `textEdited`.
- **Estils**: set_active_panel només reaplica CSS quan el color realment canvia.
- **Ordenació**: eliminat el sort redundant a set_path; `_on_directory_loaded` i `_delayed_directory_refresh` unificades en `_reapply_root_index()` (eren còpies línia per línia).
- **Combo d'unitats**: early-exit si la unitat no canvia i la llista ja està construïda; WM_DEVICECHANGE ara passa `force_refresh=True` perquè les unitats noves apareguin igualment.
- **Model**: columnes data/hora serveixen mtimes de la caché (`_get_mtime_cached`) — un stat() per fitxer i directori carregat, no un per cada repintat. `import datetime` pujat a nivell de mòdul.
- Tests funcionals verificats: navegació múltiple, data/hora correctes, caché activa (1 stat per fitxer).

## Versió 6.9.10 - Agost 2026

### Fase 1 — Seguretat de dades + correcció de bugs
- **PÈRDUA DE DADES corregida**: MoveJob esborrava els originals encara que la còpia hagués fallat o l'usuari triés "Ometre" al conflicte. Ara CopyJob registra els ítems copiats amb èxit (`copied_ok`) i MoveJob només esborra els originals verificats.
- **Papelera**: si `send2trash` falla, JA NO s'escala a borrat permanent (`os.remove`). Retorna False i informa de l'error — el fitxer es preserva.
- **Fuita de connexions** al botó cancel·lar in-line: després de N operacions, un clic executava N slots sobre jobs antics. Ara es desconnecta abans de connectar.
- **Jobs zombis**: `engine.active_jobs` mai netejava els jobs cancel·lats (molts emeten només `cancelled`, no `finished`). Ara ambdós senyals alliberen el job.
- **plugin_manager**: restauració de `sys.path` en bloc `try/finally` (2 punts de càrrega) — un plugin que falli ja no contamina els imports globals.
- Tests funcionals verificats: move amb skip preserva l'original; paperera trencada preserva el fitxer; cancel·lació neteja active_jobs.

## Versió 6.9.9 - Agost 2026

### Millora — Vista iPhone amb columnes ordenables
- **Nou `ShellBrowser(QTreeWidget)`**: `src/ui/components/shell_browser.py` amb columnes Nom / Mida / Data de modificació, ordenables clicant a la capçalera.
- **Dades reals MTP**: `list_shell_folder` obté mida i data via `GetDetailsOf` (columnes 2 i 3). L'iPhone no exposa `item.Size`/`ModifyDate` (retornen 0/1899).
- **Ordenació numèrica**: `_SizeSortDelegate` mostra la mida formatada ("3.5 MB") però ordena pel valor numèric real.
- **panel.py**: el mode shell usa `shell_browser` per a get_selected_paths, invert_selection, select_and_focus, filter_items i doble clic.

## Versió 6.9.8 - Agost 2026

### Correcció P0 — MTP/iPhone: no es podia navegar ni copiar
- **Navegació**: el fallback només descomponia `\SID-{NUM,Nom,Mida}` i ignorava els GUIDs `\{xxxx-...}` dels subnivells → mostrava el contingut del pare. Fix: `_split_shell_path` + `_descend_shell` naveguen pas a pas per tots els segments.
- **Còpia**: `CopyJob` usava `shutil`/`os.path` amb paths shell inexistents. Fix: `copy_shell_items` usa `Shell.CopyHere(item, 0x14)`; `_copy_files`/`_move_files` detecten paths shell amb `_is_shell_path`.

## Versió 6.9.7 - Agost 2026

### Correcció P0 — Crash amb fitxers >2GB (overflow int 32-bit)
- `JobSignals.total_size = Signal(int)` a PySide6 és un int C++ de 32 bits (màx 2.147.483.647). Amb fitxers >2GB, `total_size.emit()` llençava OverflowError → el job moria → 0% permanent i sense cancel·lació.
- Fix: `total_size = Signal("qint64")` (64 bits) a `jobs.py:27`.
- Verificat: move real de 5.91GB C:→E: amb 109 updates de progrés.

## Versió 6.9.6 - Agost 2026

### Correcció — Move es penjava per conflicte no resolt
- El CopyJob intern del MoveJob emetia `conflict` sense cap receptor → si el destí ja tenia el fitxer, esperava una decisió que mai arribava.
- Fix: `copy_job.signals.conflict.connect(self.signals.conflict.emit)` + cancel·lació propagada al CopyJob intern.

## Versió 6.9.5 - Agost 2026

### Correcció — Move entre unitats es penjava
- `shutil.move` entre unitats diferents fa copy+delete a cegues, sense progrés ni cancel·lació.
- Fix: MoveJob reutilitza CopyJob (progrés + cancel·lació) i elimina originals al final només si la còpia ha completat.

## Versió 6.9.4 - Agost 2026

### Correcció — Còpia de fitxers grans bloquejada
- `fdst.truncate(size)` de la pre-allocació escrivia 8GB de zeros a Windows abans de copiar.
- Fix: pre-allocació només per fitxers ≤64MB; buffer de còpia unificat a 4MB.

## Versió 6.9.3 - Agost 2026

### Simplificació — Una sola barra de progrés
- Eliminat el diàleg modal (ProgressDialog) de les operacions.
- `run_operation_with_dialog` → `run_operation`: només barra in-line al panell actiu (no als 2 panells ni barra d'estat).

## Versió 6.9.2 - Agost 2026

### Millora — Còpia paral·lel per directori
- `ThreadPoolExecutor` (2 workers) copia fitxers en paral·lel dins de cada directori de `copytree_with_progress`.
- `_copy_single_file` extraïda com a funció auxiliar thread-safe; comptadors amb lock.

## Versió 6.9.1 - Agost 2026

### Millores — Cancel·lació in-line, pre-allocació, progrés USB lent
- Botó X a la barra de progrés in-line del panell.
- Pre-allocació `fdst.truncate(size)` per reduir fragmentació USB.
- Progrés estable per temps (0.5s/1%) quan la mida total és desconeguda (USB lent).

## Versió 6.9.0 - Juliol 2026

### Millores — Optimitzacions rendiment + UX
- Barra de progrés in-line sota el nav_frame (no modal).
- `get_tree_size` amb timeout 1.5s — si USB lent, salta estimació i mostra progrés per fitxers.
- Confirmació abans d'obrir arxius >100MB.
- Breadcrumb amb colors explícits per visibilitat als dos panells.

## Versió 6.8.3 - Juliol 2026

### Correccions
- **P0 - Breadcrumb / DriveCombo bug**: a `_rebuild()` es captura el widget una sola vegada abans de `setParent(None)`/`deleteLater()`. Abans el segon `set_path()` llançava `AttributeError` a `item.widget()` (el widget quedava sense referència Python i PySide6 el garbage-collectejava), fet que tallava `_on_path_changed_update_nav` i impedia actualitzar el `DriveCombo` (es quedava en "Local") i deixava el breadcrumb inconsistent.

## Versió 6.8.0 - Juliol 2026

### Refactor SoC (Separation of Concerns)
- **P0 — Breadcrumb bug**: `_rebuild()` afegeix `setParent(None)` abans de `deleteLater()` per evitar que widgets vells segueixin renderitzant-se.
- **P1 — Single source of truth**: `path_changed` signal actualitza breadcrumb, path_input, drive_combo i tabs via `_on_path_changed_update_nav`.
- **P2a — `DirectoryWatcher`**: Nou mòdul `src/core/directory_watcher.py` amb QFileSystemWatcher + polling. Extret de `panel.py` per SoC.
- **P2b — `set_path` descompost**: Dividit en `_apply_to_model`, `_apply_to_archive`, `_push_history`, `_on_path_changed_update_nav`.
- **`panel.py`**: −152 línies (1594 → 1442).
- **`.spec`**: Afegit `src.core.directory_watcher` a `hiddenimports`.

- **P3 — Core actions**: `ActionContext` + handlers a `core/actions.py` per copy, move, delete, create_folder, terminal, view/edit file. `main_window.py` delega via `_run_action("id")`. Eliminats ~90 línies de lògica inline i 4 imports no usats.

### Build
- PyInstaller v6.21.0, `BUILD SUCCESSFUL` verificat.

## Versió 6.7.5 - Juny 2026

### Seguretat
- **remote_conn**: Contrasenyes SSH/FTP emmagatzemades al Windows Credential Manager (abans en clar a JSON)
- **credential_store.py**: Nou mòdul per gestionar credencials via ctypes + advapi32.dll

### Correccions
- **native_menu.py**: Eliminats paths hardcoded de Notepad++ → usa registre Windows + variables d'entorn
- **native_menu.py**: Fix terminal CMD/PowerShell amb `shell=True`

### Neteja
- Eliminat `PROJECT_GUIDE.md` (redundant amb AGENTS.md)
- Eliminat `.opencode/instructions.md` (redundant amb AGENTS.md)
- Retallat `TECHNICAL_MANIFEST.md` (1095 → 60 línies)
- Retallat `DEVELOPMENT_PLAN.md` (124 → 35 línies)

---

## Versió 6.7.4 - Juny 2026

### Millora
- **main_window.py**: Finestra per defecte canviada de 1200×800 a 1200×500 (més compacta)

---

## Versió 6.7.3 - Juny 2026

### Correccions
- **native_menu.py**: Eliminats paths hardcoded de Notepad++ → usa registre Windows + variables d'entorn
- **native_menu.py**: Fix terminal CMD/PowerShell amb `shell=True` per compatibilitat amb executables compilats

### Millora
- **TECHNICAL_MANIFEST.md**: Retallat a decisions vigents (1095 → 60 línies)
- **DEVELOPMENT_PLAN.md**: Retallat a fases completades (124 → 35 línies)

### Neteja
- Eliminat `PROJECT_GUIDE.md` (redundant amb AGENTS.md)
- Eliminat `.opencode/instructions.md` (redundant amb AGENTS.md)

---

## Versió 6.2.6 - Abril 2026

### Correccions

- **compare_dirs**: `select_and_focus` usava `setCurrentIndex` que reemplaçava la selecció anterior → només 1 fitxer seleccionat dels N. Ara usa `select_paths` (nou mètode a `FilePanel`) que acumula seleccions amb `QItemSelectionModel.Select | Rows`.
- **panel.py**: Nou mètode `select_paths(paths)` per seleccionar múltiples fitxers alhora.

## Versió 6.2.5 - Abril 2026

### Correccions

- **compare_dirs**: `list_files` ara usa `item.is_dir()` per marcar directoris amb `/` també en mode no-recursiu (abans només en recursiu). Paths normalitzats amb `os.path.normpath` per evitar separadors mixtos (`/` vs `\\`) a Windows que impedien `select_and_focus`.

## Versió 6.2.4 - Abril 2026

### Correccions

- **compare_dirs**: Mode recursiu ara detecta també carpetes (no només fitxers). Selecciona fitxers modificats/diferents (mida canviada). `os.path.join` en lloc de `f"{path}/{f}"`.
- **plugin_api.compare_paths**: `os.walk` ara inclou `dirs` en el set de fitxers (marcats amb `/` final).
- **space_analyzer plugin.json**: Descripció actualitzada (10 → 50 fitxers). Nom canviat a "Fitxers més grans" per claredat.

## Versió 6.2.3 - Abril 2026

### Nou Plugin

- **Test de Velocitat USB**: Nou plugin `usb_speed` que mesura la velocitat d'escriptura real mitjançant un fitxer temporal de 200 MB i estima el tipus d'USB (2.0, 3.0, 3.1, 3.2). S'executa en `QThread`, no bloqueja la UI.

### Altres Correccions

- **Progrés en còpia**: Corregit bug on `update_taskbar` no tenia `self` + `.connect()` mal ubicades (quedava "Iniciando 0%" permanent).
- **Ajuda ràpida**: Corregits shortcuts incorrectes (`Ctrl+R`: "Sincronitzar" → "Refrescar"; eliminat `Ctrl+Shift+A` inexistent; afegits `F1`, `Ctrl+N`, `Alt+F4`, `Ctrl+Shift+C`).

### Fitxers modificats

- `src/plugins/usb_speed/`: **Nou** plugin (plugin.json + main.py).
- `src/ui/main_window.py`: Fix `update_taskbar` → `_on_dialog_progress` amb `self`.
- `src/ui/dialogs/quick_help.py`: Shortcuts corregits i ampliats.
- `src/version.py`: Versió 6.2.2 → 6.2.3

## Versió 6.2.2 - Abril 2026

### Millores de Plugins

- **hash_tool**: Ara s'executa en `QThread` amb barra de progrés, botó de cancel·lar, i buffer de 64KB (×16 més ràpid).
- **mini_grep**: Ara s'executa en `QThread` amb barra de progrés, cancel·lació, i suport per +30 formats de text (xml, json, html, csv, yaml, css, js, ts, c, java, sql...).
- **space_analyzer**: Escaneig en `QThread` (no bloqueja la UI), `QProgressBar` real, cancel·lació, `datetime` en lloc de `os.popen('date /t')`.

### Fitxers modificats

- `src/plugins/hash_tool/main.py`: Reesccrit amb `HashWorker(QThread)`, barra de progrés, buffer 64KB.
- `src/plugins/mini_grep/main.py`: Reesccrit amb `GrepWorker(QThread)`, barra de progrés, +30 extensions.
- `src/plugins/space_analyzer/main.py`: `ScanWorker(QThread)`, `QProgressBar` real, cancel·lació, `datetime` natiu.
- `src/version.py`: Versió 6.2.0 → 6.2.1

## Versió 6.2.0 - Abril 2026

### Millores de Plugins

- **multi_rename**: Ara comprova si el fitxer destí existeix abans de renombrar (evita pèrdua de dades). Mostra resum d'errors per fitxer.
- **remote_conn**: Corregides vulnerabilitats de seguretat: `AutoAddPolicy()` → `WarningPolicy()` (MITM), timeout de 10s en connexions FTP/SFTP.
- **organizer**: Corregit import ordering (docstring al principi). `_open_destination` ja no usa `self.parent()` directament.

### Noves Dependències Compartides

- **`src/core/plugin_settings.py`**: **Nou** mòdul compartit per `load_settings`/`save_settings`. Eliminada duplicació de codi a `duplicate_finder`, `image_converter` i `remote_conn`.

### Fitxers modificats

- `src/core/plugin_settings.py`: **Nou** - helper de càrrega/desament de config de plugins.
- `src/plugins/multi_rename/main.py`: Comprovació de fitxers existents + errors granulars.
- `src/plugins/remote_conn/main.py`: `WarningPolicy` + timeout 10s.
- `src/plugins/organizer/main.py`: Imports fixes + `_last_path` per `_open_destination`.
- `src/plugins/duplicate_finder/main.py`: Usa `plugin_settings` en lloc de codi duplicat.
- `src/plugins/image_converter/main.py`: Usa `plugin_settings` en lloc de codi duplicat.
- `src/version.py`: Versió 6.1.2 → 6.2.0

## Versió 6.1.2 - Abril 2026

### Millores de Rendiment

- **Caché de metadades**: `ExtendedFileSystemModel` ara cacheja `os.path.getmtime()` i `os.path.getsize()` per evitar crides repetides al sistema de fitxers durant l'ordenació. La caché es neteja automàticament en canviar de directori.
- **`os.scandir()` a `fs_utils.py`**: Substituït `os.listdir()` per `os.scandir()` (més eficient, no crea llistes intermèdies).

### Correccions de Build

- **Fix `JMComander.spec`**: `'email'` tret de `excludes` i afegit a `hiddenimports` (necessari per `importlib.metadata` → `py7zr` → `bcj`).
- **Nous hidden imports**: `src.ui.file_system_model`, `src.core.taskbar_progress`, `email.*`, `importlib_metadata`.

### Dependències Actualitzades

| Paquet | Abans | Després |
|--------|-------|---------|
| PyInstaller | 6.19.0 | **6.20.0** |
| cryptography | 46.0.7 | **47.0.0** |
| pyinstaller-hooks-contrib | 2026.0 | 2026.4 |

### Fitxers modificats

- `src/ui/file_system_model.py`: Afegides `_size_cache` i `_mtime_cache` a `ExtendedFileSystemModel`.
- `src/core/fs_utils.py`: `os.listdir()` → `os.scandir()`.
- `JMComander.spec`: Fix hidden imports i excludes.
- `src/version.py`: Versió 6.1.1 → 6.1.2 + dependències actualitzades.

## Versió 6.1.1 - Abril 2026

## Versió 6.1.1 - Abril 2026

### Millores d'Arquitectura (SoC)

- **TaskbarProgress extret**: Classe `TaskbarProgress` extreta de `main_window.py` (1305 línies) a `src/core/taskbar_progress.py` (98 línies).
- **`main_window.py` reduït**: -45 línies gràcies a l'extracció.
- **Optimització rendiment**: Canviat `os.listdir()` per `os.scandir()` a `src/core/plugin_api.py` (més ràpid, no crea llistes intermèdies).

### Fitxers modificats

- `src/core/taskbar_progress.py`: **Nou** - classe TaskbarProgress extreta.
- `src/ui/main_window.py`: Eliminada classe TaskbarProgress; importada des de `src.core.taskbar_progress`.
- `src/core/plugin_api.py`: `os.listdir()` → `os.scandir()` a `list_files`.
- `src/version.py`: Versió 6.1.0 → 6.1.1

## Versió 6.1.0 - Abril 2026

### Millores d'Arquitectura (SoC)

- **Refactor SoC**: Extrets `ExtendedFileSystemModel`, `FileSystemProxyModel` i `natural_sort_key` de `panel.py` (2106 línies) a `src/ui/file_system_model.py` (468 línies).
- **panel.py reduït**: De ~2106 a ~1370 línies, millorant la separació de responsabilitats.
- **Imports optimitzats**: Eliminats imports no utilitzats (`QFileSystemModel`, `QSortFilterProxyModel`, `QModelIndex`).

### Fitxers modificats

- `src/ui/panel.py`: Eliminades classes de model (~730 línies); importades des de `file_system_model.py`.
- `src/ui/file_system_model.py`: **Nou** - conté `ExtendedFileSystemModel`, `FileSystemProxyModel`, `natural_sort_key`.
- `src/version.py`: Versió 6.0.11 → 6.1.0

## Versió 6.0.11 - Abril 2026

### Correccions

- **Fix DLL script**: Corregit `scripts/3_copy_qt_dlls.bat` per usar entorn `jm_pyside_313` en lloc de `jm_pyside_312`.
- **Imports**: Corregit `ImportError` a `src/core/actions.py` — `run_organize` → `run_organizer`.
- **Neteja**: Eliminats ~88 fitxers temporaris de debug, fix, check, i directoris backup antics.
- **Backup**: Creat `backup_preclean_20260427.zip` amb estat net del projecte.

## Versió 6.0.10 - Abril 2026

### Millores

- **Ordenació prioritària**: Les arxius apareixen sempre abans que les carpetes en qualsevol columna. Per defecte s'ordena per data de modificació (més nous primer).
- **Correcció crítica**: Resolt error d'indentació i estructura a `CopyJob.run()` que impedia l'execució de l'aplicació.

### Fitxers modificats

- `src/ui/panel.py`: Modificat `FileSystemProxyModel.lessThan()` per prioritzar arxius; afegida ordenació per data per defecte.
- `src/core/jobs.py`: Reestructurat mètode `CopyJob.run()` amb sagnia correcta i flux de control try/except/finally vàlid.
- `src/version.py`: Versió 6.0.9 → 6.0.10

---
## Versió 6.0.9 - Abril 2026

### Millores d'Usabilitat

- **Barra de progrés visible en còpia de directoris**:
  - **Millora**: La barra de transferència ara mostra el progrés en temps real durant la còpia de directoris entre panells
  - **Càlcul precís**: El percentatge es calcula correctament respecte al total de bytes a copiar
  - **Informació detallada**: Es mostra el fitxer actual que s'està copiant i el percentatge global
  - **Exemple**: "Copiant Documents\\subdir\\fitxer.txt (45%)"
  - **Abans**: La còpia es feia però no es veia cap progrés (sensació de bloqueig)
  - **Ara**: L'usuari veu clarament l'estat de la transferència en tot moment

### Correccions de Bugs

- **Correcció d'indentació a jobs.py**: Solucionat error d'indentació a la línia 248 que impedia l'inici de l'aplicació

### Fitxers modificats

- `src/core/jobs.py`: Refactoritzat `progress_callback` per mostrar progrés en temps real amb càlcul correcte del percentatge global i corregit error d'indentació
- `src/ui/panel.py`: Temporitzador de doble clic 100ms → 300ms
- `src/version.py`: Versió 6.0.8 → 6.0.9

---

## Versió 6.0.8 - Abril 2026

### Correccions Crítiques

- **Còpia recursiva de directoris**: Solucionats bugs crítics a `CopyJob.run()` que impedeixen la còpia correcta de directoris entre panells:
  - **Bug 1**: `progress_wrapper()` sense paràmetres causava `TypeError` en rebre crides de `copytree_with_progress()`
  - **Bug 2**: `ProgressHandler` accedia a variables fora del seu scope (`total_size`, `completed_size`, `filename`)
  - **Bug 3**: Import de `QThreadPool` dins del mètode `run()` en lloc de la capçalera
  - **Solució**: Refactoritzat `ProgressHandler` per rebre referències correctes, `progress_wrapper` ara accepta `total_copied`, import mogut a la capçalera
  - **Resultat**: La còpia recursiva amb F5 funciona perfectament amb progrés i cancel·lació

### Fitxers modificats

- `src/core/jobs.py`: Refactoritzat `ProgressHandler`, corregit `progress_wrapper`, mogut import de `QThreadPool`
- `src/ui/panel.py`: Temporitzador de doble clic 100ms → 300ms
- `src/version.py`: Versió 6.0.7 → 6.0.8

### Fitxers modificats

- `src/core/jobs.py`: Refactoritzat `ProgressHandler`, corregit `progress_wrapper`, mogut import de `QThreadPool`
- `src/ui/panel.py`: Temporitzador de doble clic 100ms → 300ms
- `src/version.py`: Versió 6.0.7 → 6.0.8

---

## Versió 6.0.5 - Abril 2026

### Millores

- **Tecla Suprimir**: Afegida gestió de la tecla Suprimir (Delete) per mostrar el diàleg de supressió. Ara els usuaris poden suprimir fitxers i carpetes tant amb F8 com amb la tecla Suprimir, millorant la usabilitat i la consistència amb altres gestors d'arxius.
- **Verificació de funcionalitats**: Verificat que la còpia de directoris amb F5 funciona correctament, copiant recursivament tots els subdirectoris i arxius. El sistema usa `CopyJob` i `copytree_with_progress()` per a una còpia eficient amb progrés.

### Fitxers modificats

- `src/ui/main_window.py`: Afegida gestió de la tecla Suprimir al mètode `keyPressEvent()`
- `src/version.py`: Actualitzada versió de 6.0.4 a 6.0.5

---

## Versió 6.0.4 - Abril 2026

### Correccions

- **Tecles de funció F2/F5/F6/F7/F8/F9**: Corregit bug crític on les tecles de funció no funcionaven. Les QAction amb shortcuts F-key no s'afegien al MainWindow amb `addAction()`, per tant els shortcuts no s'activaven quan un widget fill (QTreeView) tenia el focus. Ara `add_act()` afegeix automàticament cada acció al MainWindow.
- **F9 Duplicar**: Afegit shortcut F9 per a l'acció "Duplicar" (abans només tenia Ctrl+D).
- **Navegació des de bookmarks/favorits**: Millorada la fiabilitat de la càrrega de fitxers quan es navega des d'un bookmark o carpeta favorita. Afegit `_delayed_directory_refresh()` com a fallback de 100ms per garantir que la vista es refresqui encara que el signal `directoryLoaded` no arribi a temps.
- **`_on_directory_loaded()`**: Comparació de paths ara és case-insensitive (`lower()`) per evitar falsos negatius en Windows. També actualitza `set_current_root_source_index` i re-ordena el proxy model.

## Versió 6.0.3 - Abril 2026

### Correccions

- **Favorits/Marcadors**: En clicar un favorit ara es mostren els fitxers correctament. Abans la vista quedava buida fins que es clicava la carpeta al breadcrumb (bug de `QFileSystemModel.directoryLoaded` asíncron)
- **Shift+F7**: Nova drecera per obrir el diàleg "Ir a..." (canviar directori), equivalent a Ctrl+G (estil Total Commander)
- **`_on_directory_loaded()`**: Nou mètode que actualitza els índexs de la vista quan el `QFileSystemModel` acaba de carregar el directori

## Versió 6.0.2 - Abril 2026

### Ajuda ràpida (F1)

- **`QuickHelpDialog`**: Nou diàleg `src/ui/dialogs/quick_help.py` amb explicació ràpida de funcions i dreceres
- Botó **❓** al toolbar (substitueix l'antic botó ℹ️ Info)
- Drecera **F1** per obrir l'ajuda ràpida
- Es mostra com a popup posicionat sota el botó del toolbar
- Categories: Navegació, Operacions de fitxers, Selecció, Panells, Cerca i filtres, Ratolí
- **"Sobre JMComander"**: Disponible des del menú contextual del botó d'ajuda

### Correcció d'arxius comprimits (continuació)

- **`archive_handler.py`**: Corregit error que impedia obrir fitxers RAR i 7Z en mode exe compilat (PyInstaller)
- **`_get_assets_path()`**: Nou mètode estàtic que busca recursos (UnRAR64.dll, UnRAR.exe, 7z.exe) tant en mode desenvolupament com en mode frozen (`sys._MEIPASS`)
- **`_find_rar_exe()`**, **`_find_7z_exe()`**, **`_find_unrar_dll()`**: Ara usen `_get_assets_path()` en lloc de `Path(__file__).parent.parent / 'assets'`, que no funciona quan l'app està empaquetada

## Versió 6.0.0 - Abril 2026

### Millores d'Utilitat (inspirat en Total Commander) - Fase 4

#### Historial de carpetes (Alt+← / Alt+→)
- **`PathHistory`**: Nou mòdul `src/core/path_history.py` amb historial back/forward per panell (màx 50 entrades)
- Botons **Enrere** i **Endavant** a la barra de navegació de cada panell
- Dreceres **Alt+←** (enrere) i **Alt+→** (endavant) registrades com a QActions
- Els botons s'activen/desactiven segons l'estat de l'historial
- La navegació per historial no afegeix entrades duplicades

#### Folder tabs (Ctrl+T / Ctrl+W)
- **`FolderTabBar`**: Nou component `src/ui/components/folder_tab_bar.py` amb pestanyes per panell
- Dreceres **Ctrl+T** (nova pestanya) i **Ctrl+W** (tancar pestanya)
- Pestanyes mòbils, amb tancament individual i menú contextual
- Cada pestanya manté la seva ruta independent
- Canvi de pestanya navega automàticament a la ruta corresponent

#### Directory Hotlist (Ctrl+D)
- **`DirectoryHotlistDialog`**: Nou diàleg `src/ui/dialogs/directory_hotlist.py`
- Drecera **Ctrl+D** obre la llista de directoris freqüents
- Directoris per defecte: Escriptori, Documents, Descàrregues, Imatges, Música, Vídeos, Arrel, Usuari
- Afegir el directori actual a la llista
- Doble clic navega al directori seleccionat

#### Synchronize Dirs
- **`SyncDirsDialog`**: Nou diàleg `src/ui/dialogs/sync_dirs.py`
- Analitza diferències entre els dos panells (fitxers que falten, mides diferents)
- Copiar fitxers seleccionats d'un panell a l'altre (← o →)
- Interfície amb arbre de diferències i selecció per checkbox
- Acció "Sincronitzar directoris" disponible al menú

#### Filter by extension
- **Botó `*.ext`** a la barra de navegació de cada panell
- Menú desplegable amb categories: Documents, Imatges, Vídeo, Àudio, Arxius, Codi
- `FileSystemProxyModel.set_extension_filter()`: Filtra fitxers per llista d'extensions
- "Mostrar tots" per treure el filtre
- El botó mostra les extensions actives del filtre

## Versió 5.3.0 - Abril 2026

### Descompondre God Classes - Fase 3 (continuació)

#### DriveCombo extret de FilePanel (`src/ui/components/drive_combo.py`)
- **`DriveCombo(QComboBox)`**: Nou component independent que gestiona la detecció i visualització d'unitats
- Lògica de `update_drives()` i `_on_drive_activated()` moguda de `FilePanel` a `DriveCombo`
- Senyal `drive_activated(str)` per notificar canvis de unitat
- `win32file`/`win32api` imports eliminats de `panel.py` (ara només a `drive_combo.py`)
- Fallback a `QComboBox` bàsic si `DriveCombo` no disponible

#### ArchiveBrowser extret de FilePanel (`src/ui/components/archive_browser.py`)
- **`ArchiveBrowser(QListWidget)`**: Nou component independent per navegació d'arxius comprimits i shell (iPhone)
- `populate_from_path()`: Poblar des d'un directori muntat
- `populate_shell_items()`: Poblar des d'items shell (MTP/iPhone)
- `get_selected_paths()`, `select_item_by_path()`, `select_item_by_name()`: Selecció delegada
- `invert_selection()`, `filter_items()`: Operacions de selecció i filtratge
- Estil CSS integrat al component (eliminat de `panel.py`)
- `FilePanel` delega operacions a `ArchiveBrowser` quan està disponible

#### FilePanel simplificat
- `_populate_shell_browser()`: Delega a `ArchiveBrowser.populate_shell_items()` o fallback manual
- `_populate_archive_browser()`: Delega a `ArchiveBrowser.populate_from_path()` o fallback manual
- `get_selected_paths()`, `invert_selection()`, `select_and_focus()`, `_select_by_name()`: Deleguen a ArchiveBrowser
- `_on_filter_changed()`: Delega filtratge d'arxius a `ArchiveBrowser.filter_items()`
- Reducció de 1775 → 1717 línies (-58)

## Versió 5.2.0 - Abril 2026

### Descompondre God Classes - Fase 3

#### `jobs.py` - BaseJob + ConflictMixin
- **`BaseJob`**: Nova classe base amb mètodes comuns per tots els jobs (`cancel`, `_emit_progress`, `_check_cancelled`, `_finish_or_cancel`, `_emit_progress_for_item`)
- **`ConflictMixin`**: Mixin que consolida la lògica de conflictes (`check_conflicts`, `resolve_conflict`, `get_unique_dst`, `_apply_action_to_conflict`)
- `CopyJob`, `MoveJob`, `DeleteJob`, `SecureDeleteJob` ara hereten de `BaseJob`
- Eliminació de codi duplicat: cancel·lació, progrés i resolució de conflictes

#### `fs_utils.py` - Funcions extretes de jobs.py
- `should_overwrite_file()`: Comprovació de sobreescriptura condicional (abans dins `jobs.py`)
- `copytree_with_progress()`: Còpia d'arbre amb progrés (abans `_copytree_with_progress`)
- `get_tree_size()`: Càlcul de mida total d'un arbre (abans `_get_tree_size`)

#### `MainWindow` reestructurat
- Nous mètodes d'inicialització: `_init_core()`, `_init_window_geometry()`, `_init_ui_structure()`, `_init_panels()`, `_init_background_progress()`, `_init_quick_look()`, `_init_toolbar()`, `_init_bookmarks_bar()`, `_init_content()`, `_init_signals()`, `_init_quicklook_shortcut()`
- Eliminat `_run_with_dialog` i `_on_operation_finished` (duplicats de `run_operation_with_dialog`)
- Nou mètode `refresh_both_panels()` (unifica la lògica de refresc de tots dos panells)
- `keyPressEvent` simplificat: eliminades totes les F-keys hardcodejades, ara delegades a QActions registrades
- Afegides F-key actions que faltaven: F2 (rename), F4 (edit), F5 (copy), F6 (move), F7 (new folder), F8 (delete)

## Versió 5.1.0 - Abril 2026

### Sistema de plugins net - Fase 2

#### PluginAPI millorada (`src/core/plugin_api.py`)
- **`get_parent_window()`**: Nou mètode per obtenir la finestra Qt pare per a diàlegs (elimina `api._mw` directe)
- **`delete(paths)`**: Nou mètode per eliminar fitxers via l'engine (plugins ja no necessiten `os.remove()` directe)
- **`refresh_panel()`**: Drecera per refrescar el panell actiu

#### Contracte de plugins unificat (`src/core/plugin_interface.py`)
- **`execute(api)`**: El paràmetre ara és `api` (PluginAPI) en lloc de `main_window`
- **Benefici**: Tots els plugins reben la mateixa API neta, sense accés directe a Qt ni a MainWindow

#### MockMainWindow eliminat de tots els plugins
- Tots els 11 plugins HYBRID tenien una classe `MockMainWindow` interna que feia de pont entre `api` i l'antic `execute(main_window)`
- **Eliminat**: `compressor`, `disk_space`, `duplicate_finder`, `extractor`, `file_finder`, `hash_tool`, `image_converter`, `mini_grep`, `multi_rename`, `remote_conn`, `space_analyzer`
- **Nou patró**: Cada `run_xxx(api)` usa `api` directament (ex: `api.active_panel`, `api.get_parent_window()`, `api.active_panel.refresh()`)

#### Classes PluginInterface eliminades dels plugins
- Eliminades les classes `CompressorPlugin`, `DiskSpacePlugin`, `DuplicateFinderPlugin`, `MultiExtractorPlugin`, `FileFinderPlugin`, `HashPlugin`, `ImageConverterPlugin`, `MiniGrepPlugin`, `MultiRenamePlugin`, `RemoteConnPlugin`, `SpaceAnalyzerPlugin`
- Totes eren codi mort: el sistema nou crida `run_xxx(api)` via ActionRegistry, mai `execute()`
- Les funcions de configuració s'han convertit a funcions de mòdul (`_load_settings()`, `_save_settings()`)

#### Plugins ja nets actualitzats
- **`compare_dirs`**: Eliminat `QApplication.activeWindow()`, ara usa `api.get_parent_window()`
- **`organizer`**: Eliminat `QApplication.activeWindow()`, ara usa `api.get_parent_window()`

#### Bugs corregits
- **`file_finder`**: `QComboBox.addItems()` rebia tuples en lloc de strings. Ara usa `addItem(label, data)` amb `currentData()` correcte
- **`space_analyzer`**: `format_size()` propi eliminat, ara importa `format_size` de `src.core.utils`
- **`main_window.py`**: Les dues crides a `execute()` ara passen `api` en lloc de `self` (MainWindow)

#### Eliminació d'imports innecessaris
- Tots els plugins eliminen `from src.core.plugin_interface import PluginInterface`
- `QApplication` eliminat dels plugins que només l'usaven per obtenir la finestra pare

## Versió 5.0.0 - Abril 2026

### Refactorització SoC (Separation of Concerns) - Fase 1

#### Nou mòdul `src/core/json_store.py`
- **Base class CRUD**: `JsonStore` amb operacions `load`/`save`/`add`/`remove`/`update`/`move_up`/`move_down`/`get_all`
- **Benefici**: Elimina la duplicació entre `BookmarkManager` i `AppLauncher` que tenien codi idèntic

#### Nou mòdul `src/core/utils.py`
- **`format_size()`**: Utilitat centralitzada per formatar mides de fitxer (abans duplicada 3 vegades)
- **`is_windows_special_file()`**: Detecció centralitzada de fitxers especials de Windows (abans duplicada 2 vegades dins fs_utils.py)
- **`natural_sort_key()`**: Clau d'ordenació natural compartida

#### SoC: Qt eliminat de core/
- **`bookmarks.py`**: Eliminat `from PySide6.QtCore import QStandardPaths`. Ara usa `pathlib.Path` per a rutes per defecte
- **`config.py`**: `set_window_state()` ara accepta `(x, y, w, h, is_maximized)` en lloc de `QRect`
- **`plugin_api.py`**: `open_file()` ara usa `os.startfile()` en lloc de `QDesktopServices`. `show_message()` i `confirm()` accepten callbacks opcionals per desacoplar de QMessageBox
- **`native_menu.py`**: Mogut de `core/` a `ui/` (és codi de presentació Win32, no lògica de negoci)

#### SoC: Lògica de plugins separada d'actions.py
- **`run_compare_dirs()`** i **`run_organize()`**: Mogudes d'`actions.py` als seus plugins respectius, amb lazy-import
- **Benefici**: `actions.py` ara és un registre pur, sense lògica de negoci ni imports d'OS

#### Bugs corregits
- **`mtp_handler.py`**: `list_shell_folder()` duplicava items (iterava dues vegades: per iteració i per índex)
- **`jobs.py`**: `SecureDeleteJob` log deia `[CopyJob]` (error de copy-paste)
- **`jobs.py`**: Eliminat import `safe_copy` no utilitzat

#### DRY: format_size unificat
- Eliminades 3 implementacions duplicades de `format_size` a `panel.py`, `conflict_dialog.py`, `progress_dialog.py`
- Totes ara deleguen a `src.core.utils.format_size()`
- `human_readable_size` a `fs_utils.py` també delega a `utils.format_size()`

#### Canvi de versió
- **Versió**: 4.2.0 → 5.0.0 (canvi major per refactorització SoC significativa)

---

## Versió 4.2.0 - Abril 2026

### Actualització de Python i entorn Conda

- **Python 3.13**: Actualització de Python 3.12.12 a Python 3.13.12 sense perdre compatibilitat amb les llibreries.
- **Nou entorn Conda**: Creat entorn `jm_pyside_313` amb Python 3.13 i totes les dependències instal·lades (`PySide6 6.11.0`, `PyInstaller 6.19.0`, `Pillow 12.2.0`, etc.).
- **Compatibilitat verificada**: Totes les llibreries principals són compatibles amb Python 3.13: PySide6, PyInstaller, Pillow, pywin32, send2trash, rarfile, py7zr, psutil, paramiko, cryptography, bcrypt, mutagen, numpy, musicbrainzngs.
- **Build.bat actualitzat**: Script de build modificat per utilitzar l'entorn `jm_pyside_313` i Python 3.13.
- **Versió actualitzada**: Canvi de versió a 4.2.0 a `src/version.py`.

## Versió 4.1.0 - Abril 2026

### Correcció d'errors d'indentació crítics

- **`src/core/jobs.py`**: Eliminat codi duplicat (línies 124-139) que causava `IndentationError: unexpected indent` i `SyntaxError: expected 'except' or 'finally' block`. Corregit l'indent de `success, bytes_copied = _copytree_with_progress(...)` (línia 437, de 0 a 20 espais).
- **`src/ui/main_window.py`**: Corregit l'indent de ~640 línies de codi (de indent 8 a indent 4). Uns 50 mètodes de `MainWindow` estaven com a funcions anidades dins d'altres mètodes en lloc de ser mètodes de classe, causant `AttributeError: 'MainWindow' object has no attribute '_cancel_background_operation'`. Mètodes afectats: `refresh_main_toolbar`, `go_up`, `go_root`, `go_home`, `refresh_panel`, `select_all`, `invert_selection`, `deselect_all`, `rename_item`, `copy_path_to_clipboard`, `toggle_folders_only`, `open_terminal_here`, `open_powershell_here`, `open_in_explorer`, `go_to_folder`, `_toggle_quick_look`, `_update_quick_look_preview`, `_on_selection_changed`, `duplicate_selected`, `copy_files`, `move_files`, `delete_files`, `create_folder`, `_on_path_request`, `_on_path_changed`, `update_plugins_menu`, `open_plugin_config`, `run_action`, `update_recent_paths_menu`, `clear_recent_paths`, `update_view_mode_menu`, `update_bookmarks_menu`, `add_current_to_bookmarks`, `open_settings`, `open_bookmarks_manager`, `view_file`, `edit_file`, `show_about_dialog`, `open_search_dialog`, `setup_enhanced_status_bar`, `update_status_bar`, `run_operation_with_dialog`, `_cancel_operation`, `_flash_if_minimized`, `_run_in_background`, `_on_bg_progress`, `_on_bg_file_started`, `_on_bg_finished`, `_on_bg_error`, `_cancel_background_operation`, `_run_with_dialog`, `_on_operation_finished`, `_handle_copy_conflict`, `keyPressEvent`, `closeEvent`, `nativeEvent`, `refresh_drives`, `_create_settings_button`, `_create_view_mode_button`, `_create_recent_paths_button`, `_create_plugins_button`, `_create_bookmarks_button`, `_create_apps_button`, `swap_panels`, `equal_panels`, `equal_panels_reverse`.

### Refactorització arquitectònica (P2 - SoC)

#### Nou mòdul `src/core/mtp_handler.py`
- **Funcions extretes**: `get_iphone_storage_path()`, `list_shell_folder()`, `get_shell_display_name()`
- **Cache MTP**: Variables de cache per a detecció d'iPhone (`_iphone_cache`, `_iphone_cache_time`, `_IPHONE_CACHE_TIMEOUT`)
- **Benefici**: Codi de navegació MTP/iPhone ara està separat de la lògica UI del panell

#### Actualització de `src/ui/panel.py`
- Ara importa des de `src.core.mtp_handler` per a funcions MTP
- Eliminats ~175 línies de codi MTP duplicat
- Eliminat import redundant de `win32com.client` (ara només a mtp_handler)

---

## Versió 4.0.0 - Abril 2026

### Refactorització arquitectònica (P1 - SoC)

Objectiu: Millorar la utilitat, velocitat, simplicitat i mantenibilitat del codi complint amb el principi de Separation of Concerns.

#### Nou mòdul `src/core/file_constants.py`
- **Constants extretes**: `FILE_CATEGORIES`, `EXTENSION_CATEGORIES`, `FILE_TYPE_DISPLAY`, `CATEGORY_DISPLAY_NAMES`
- **Funcions de categorització**: `get_file_type_display()`, `get_file_category()`, `get_category_display_name()`, `get_extension()`
- **Benefici**: Constants de categorització ara estan centralitzades en lloc de duplicades a `panel.py`

#### Nou mòdul `src/assets/icon_utils.py`
- **Funció `load_icon()`**: Consolida la lògica de càrrega d'icones SVG
- **Funció `get_base_path()`**: Detecta automàticament si l'app està en mode development o frozen (PyInstaller)
- **Benefici**: Elimina la duplicació del patró `getattr(sys, 'frozen', False)` a `panel.py`

#### Actualització de `src/ui/panel.py`
- Ara utilitza `src.core.file_constants` per a les constants de categorització
- Ara utilitza `src.assets.icon_utils.load_icon()` per a la càrrega d'icones
- **Línies reduïdes**: ~200 línies menys de constants i lògica de càrrega d'icones

#### Canvi de versió
- **Versió**: 3.2.6 → 4.0.0 (canvi de versió major per refactorització significativa de l'arquitectura)

---

## Versió 3.2.6 - Abril 2026

### Millores estètiques al panell de detalls
- **Columna "Ext" més estreta**: Canviada de 60 a 40 pixels per mostrar només l'extensió bàsica (jpg, mp4, etc.).
- **Columna "Tipus" simplificada**: Ara mostra tipus simples: "Image", "Video", "Audio", "Text", "Word", "Excel", "Archive", "Exe", etc. (en lloc de "JPG Image", "MP4 Video", etc.).
- **Columna "Tipus" més estreta**: Canviada de 100 a 70 pixels.
- **Columna "Hora" més ample**: Canviada de 60 a 70 pixels per veure l'hora correctament.

## Versió 3.2.5 - Abril 2026

### Diàleg de conflicte simplificat
- **Nou diàleg**: Canviat el diàleg de conflicte per mostrar només 3 botons: "Todos", "Solo los más antiguos" i "Cancelar".
- **Botó "Todos"**: Sobreescriu tots els fitxers sense condicions.
- **Botó "Solo los más antics"**: Sobreescriu només quan el fitxer destí és més antic que l'origen (equivalent a "sobrescriu si origen és més nou").
- **Cancel·lar**: Atura l'operació.
- **Informació de dates**: El diàleg mostra la data i mida tant de l'origen com del destí, i indica si l'origen és "más NUEVO" o "más ANTIGUO".

## Versión 3.2.3 - Abril 2026

### Millores en el diàleg de conflicte de sobrescriptura
- **Mida dels directoris**: Ara el diàleg de conflict mostra correctament la mida dels directoris (abans mostrava "0,0 B").
- **Comparació de dates**: El diàleg ara mostra correctament si l'arxiu origen és "més nou" o "més antic" que el destí.

### Millores en operacions de copia/moure
- **Progrés en còpia de directoris**: Canviada la implementació de còpia de directoris per usar `os.walk` manual en lloc de `shutil.copytree`. Això permet mostrar progrés durant la còpia (abans es quedava congelat mostrant "Calculando...").
- **Verificació de cancel·lació**: Afegida verificació de cancel·lació durant el procés de còpia per permetre aturar l'operació en qualsevol moment.

### Sobrescriptura condicional per fitxer
- **Sobreescriure si más nou**: Quan tries aquesta opció amb un directori, ara nomes sobreescriu els fitxers individuals que son mes nous a l'origen que al destí.
- **Sobreescriure si más antic**: Quan tries aquesta opció amb un directori, ara nomes sobreescriu els fitxers individuals que son mes antics a l'origen que al destí.
- **Apply to all**: La decisió s'aplica a tots els fitxers del directori, no nomes al directori arrel.

## Versió 3.2.0 - Abril 2026

### Detección y navegación de iPhone mejorada
- **Detección vía Shell Namespace**: Cambiado de `item.GetFolder()` a `shell.NameSpace(item.Path)` para obtener el folder del dispositivo iPhone. El metode anterior fallava perquè els dispositius MTP retornen un string en lloc d'un objecte folder.
- **Ruta base del dispositiu**: Ara es retorna la ruta base del dispositiu iPhone (sense SID) en lloc de la ruta d'Internal Storage. Això permet que l'usuari vegi el dispositiu al selector d'unitats i pugui navegar manualment a "Internal Storage".
- **Detecció multilingüe**: Cercar "Internal Storage" en anglès, castellà ("Almacenamiento interno") i català ("Emmagatzematge").
- **Fallback MTP**: Quan la ruta shell conte `\SID-` (com rutes d'iPhone amb Internal Storage), el sistema fa fallback a la ruta base del dispositiu per permetre navegació manual.

### Finestra mult pantalla millorada
- **Detectar pantalla correcta**: Ara busca en totes les pantalles per veure si la finestra cabe en alguna. Abans nomes comprovava la pantalla actual.
- **Centrar finestra**: Si la geometria guardada no es valida a cap pantalla, centra la finestra a la pantalla principal en lloc de simplement fer resize.
- **Ajustar mida**: Si la pantalla es mes petita que 1200x800, ajusta la mida automaticament.

## Versión 3.1.0 - Abril 2026

### Refresco de directorios corregido (botón y auto-refresh)
- **Botón Refrescar funcional**: Corregido el problema donde el botón de refrescar (🔄) no recargaba el contenido del directorio. Ahora fuerza una relectura completa del modelo con `setRootPath("")` seguido de `setRootPath(current_path)`.
- **Auto-refresh mejorado**: El sistema de auto-refresh (QFileSystemWatcher) también recarga correctamente los subdirectorios y archivos cuando se detectan cambios externos.
- **Cache del proxy model**: Se limpia la caché de timestamps antes de cada refresco para garantizar datos actualizados.
- **Pol cache actualizado**: El cache de polling se actualiza tras cada refresco para mantener consistencia del sistema de fallback.

### Sobreescriptura de directorios corregida (copiar/pegar)
- **Native paste con dirs_exist_ok**: Corregido `shutil.copytree` en `native_menu.py` para usar `dirs_exist_ok=True`, permitiendo fusionar directorios existentes con sus subdirectorios y archivos.
- **safe_copy corregido**: Añadido `dirs_exist_ok=True` a `safe_copy()` en `fs_utils.py` para evitar fallos cuando el destino ya existe.

### Limpieza de scripts duplicados
- **Eliminados scripts redundantes**: `0_build_principal`, `9_compilar_ambos.bat`, `verify_regression.bat`, `verify_all_features.bat`, `README_Instalacion.md`.
- **build.bat como principal**: Movido a la raíz del proyecto como script de build único. Todas las referencias actualizadas.
- **scripts/README.md reescrito**: Documentación actualizada sin duplicados.

### Dependencias del entorno corregidas
- **pywin32 añadido**: Instaladas todas las dependencias faltantes (`pywin32`, `Pillow`, `send2trash`, `rarfile`, `py7zr`, `psutil`, `paramiko`, `cryptography`, `bcrypt`).
- **win32com.client en spec**: Añadido `win32com.client` a los `hiddenimports` de PyInstaller.

## Versión 3.0.8 - Abril 2026

### Menú contextual en diálogo de búsqueda
- **Clic derecho en resultados de búsqueda**: Añadido menú contextual con opciones para seleccionar todo, deseleccionar todo y eliminar archivos encontrados.
- **Selección múltiple**: Los usuarios pueden seleccionar varios archivos y eliminarlos directamente desde el diálogo de búsqueda.
- **Confirmación de eliminación**: Diálogo de confirmación antes de eliminar archivos.

### Bugfix en plugin Buscador de Archivos
- **Eliminación corregida**: Corregido bug que impedía eliminar archivos correctamente al seleccionar múltiples elementos.
- **Versión actualizada**: Plugin FileFinder actualizado a v1.0.1.

## Versión 3.0.1 - Abril 2026

### Optimización de rendimiento y robustez en operaciones de copia
- **Cálculo de tamaño optimizado**: Mejorada la función `_get_tree_size()` para usar `os.scandir()` en lugar de `os.listdir()`, reduciendo la sobrecarga de E/S y mejorando el rendimiento en directorios grandes.
- **Cancelación durante cálculo de tamaño**: Implementado soporte para cancelación mientras se calcula el tamaño total de directorios, evitando que la operación se congele si el usuario cancela durante esta fase.
- **Progreso durante cálculo**: Añadida retroalimentación de progreso mientras se calculan tamaños de directorios grandes, mostrando el directorio actual que se está escaneando.
- **Manejo de errores en operaciones en segundo plano**: Implementado método `_on_bg_error()` para capturar y mostrar errores que ocurran durante operaciones en segundo plano, evitando que fallen silenciosamente.
- **Throttling de actualizaciones de UI**: Limitadas las actualizaciones de progreso durante el cálculo de tamaño a una vez por segundo para evitar saturar la interfaz de usuario.
- **Compatibilidad con directorios anidados**: Mejorado el manejo de directorios profundamente anidados con cancelación y progreso granular.

## Versión 3.0.0 - Abril 2026

### Operaciones robustas con ventana minimizada y mejoras del menú contextual
- **Operaciones con ventana minimizada**: Implementado sistema inteligente que detecta cuando la ventana está minimizada y ejecuta operaciones de copiar/mover/eliminar en segundo plano con progreso en la barra de tareas de Windows.
- **Diálogos de conflicto visibles**: Cuando la ventana principal está minimizada, los diálogos de resolución de conflictos aparecen como ventanas independientes que se mantienen visibles y encima de otras aplicaciones.
- **Modo de operación en segundo plano**: Nuevo método `_run_operation()` que selecciona automáticamente entre mostrar diálogo de progreso (ventana normal) o ejecutar en segundo plano (ventana minimizada).
- **Integración con barra de tareas**: Progreso de operaciones en segundo plano visible en el icono de la barra de tareas usando la API nativa `ITaskbarList3` de Windows.
- **Menú contextual mejorado**: Eliminación automática de opciones rotas "Obrir al terminal" y submenú Terminal funcional con CMD y PowerShell.
- **Compatibilidad completa**: Las nuevas funcionalidades trabajan con cualquier entorno (Conda o pip) usando `subprocess.Popen` con directorio de trabajo correcto.

## Versión 2.9.98 - Abril 2026

### Menú contextual mejorado: eliminación de opciones rotas y terminal funcional
- **Eliminación de "Obrir al terminal" roto**: Detecta y elimina automáticamente la opción problemática del menú contextual nativo que causaba el error "Aquest fitxer no hi ha cap aplicació associada".
- **Submenú Terminal funcional**: Añadido submenú "Terminal" con opciones para abrir CMD o PowerShell en la ruta actual, tanto para archivos/carpetas seleccionados como para fondo del panel.
- **Autodetección de elementos problemáticos**: Nueva función `_remove_broken_shell_items()` que elimina entradas del menú con palabras como terminal, cmd, powershell, bash, git, wsl, evitando errores de aplicación no asociada.
- **Compatibilidad completa**: Las nuevas opciones de terminal funcionan con cualquier entorno (Conda o pip) usando `subprocess.Popen` con directorio de trabajo correcto.

## Versión 2.8.95 - Marzo 2026

### Logging portable
- **Logs en carpeta del ejecutable**: Los logs ahora se generan en `jmcomander.log` junto al ejecutable en lugar de en `%APPDATA%`.
- **Portabilidad**: La aplicación es completamente portable, sin dependencia de rutas del sistema.

## Versión 2.8.94 - Marzo 2026

### Corrección de error en diálogo de progreso
- **RuntimeError corregido**: Solucionado error "Internal C++ object (PySide6.QtCore.QTimer) already deleted" que ocurría al cerrar el diálogo de progreso.
- **Manejo seguro de timer**: Añadido try-except en closeEvent y reject para manejar el caso donde el timer ya ha sido eliminado.

## Versión 2.8.93 - Marzo 2026

### Depuración de copia de archivos
- **Logging de CopyJob**: Añadidos logs de depuración en el sistema de copia para diagnosticar archivos que no se copian.
- **Seguimiento de errores**: Registrados warnings cuando no se puede obtener el tamaño de archivos o directorios.
- **Registro de inicio**: Logs al iniciarCopyJob con lista de archivos y tamaño total.

## Versión 2.8.92 - Marzo 2026

### Progreso en barra de tareas de Windows
- **Taskbar Progress**: Implementada funcionalidad para mostrar progreso de operaciones (copiar, mover, eliminar) en la barra de tareas de Windows cuando la ventana está minimizada.
- **API nativa**: Utiliza `ITaskbarList3` de Windows para mostrar barra de progreso verde en el icono de la barra de tareas.
- **Integración con operaciones**: Conectado el sistema de progreso con los métodos de operaciones de archivo para actualizar visualmente durante transferencias.

## Versión 2.8.8 - Marzo 2026

### Mejora del comportamiento del menú contextual
- **Clic derecho en archivo/carpeta**: Mejorada la detección del elemento bajo el cursor para mostrar el menú contextual correcto de Windows.
- **Selección automática**: Al hacer clic derecho sobre un elemento no seleccionado, ahora se selecciona automáticamente (como Windows Explorer).
- **Menú de fondo**: Clic derecho en área vacía muestra el menú de fondo de carpeta correctamente.
- **Reorganización de carpetas**: Simplificada la estructura del proyecto eliminando carpeta JMComander redundante.

## Versión 2.7.4 - Marzo 2026

### Corrección de barra de progreso y mejoras de UI
- **Barra de progreso funcional**: Solucionado el problema crítico donde la barra de transferencias saltaba de 0% a 100% instantáneamente. Ahora muestra progreso gradual basado en bytes copiados, no en número de archivos.
- **Cálculo de progreso preciso**: Implementado sistema de progreso basado en tamaño total de datos, con soporte para directorios recursivos.
- **Botones más altos**: Aumentada la altura de los botones "Minimizar" y "Cancelar" en el diálogo de progreso para mejor legibilidad.
- **Mejoras de responsividad**: Timer de actualización reducido a 50ms y forzada actualización visual con `repaint()` y `processEvents()`.
- **Ventana más compacta**: Diálogo de progreso reducido a 400x150px para mejor integración visual.
- **Mejoras en menú contextual**: Añadido logging detallado y múltiples intentos de ejecución para verbos del shell como "Git Bash Here", "Git GUI", "Open Terminal". Solucionado problema donde solo se abría la carpeta.
- **Mensajes de error mejorados para archivos comprimidos**: Al fallar la apertura de archivos RAR/7Z, se muestra mensaje sugeriendo instalar WinRAR o 7-Zip.
- **Logging de diagnóstico**: Añadidos logs informativos en `native_menu.py` para facilitar la depuración de comandos shell.

## Versión 2.7.5 - Marzo 2026

### Mejoras de soporte de archivos y ordenación natural
- **Soporte de archivos comprimidos verificado**: Verificado que las bibliotecas UnRAR64.dll y UnRAR.exe están presentes en los assets, asegurando la extracción de archivos RAR. También verificado que py7zr y rarfile están instalados en el entorno.
- **Ordenación natural de nombres**: Implementada ordenación natural (natsort) para nombres de archivos, de modo que "file2" se ordena antes de "file10". La ordenación ahora considera secuencias numéricas como números, no como texto.
- **Corrección de ordenación alfabética**: La ordenación por nombre ahora utiliza una clave de ordenación natural que también es insensible a mayúsculas/minúsculas.
- **Verificación de soporte 7-Zip**: Confirmada la detección automática de 7z.exe en el sistema y la extracción mediante py7zr como fallback.

## Versión 2.7.6 - Marzo 2026

### Mejoras de usabilidad y plugin de comparación
- **Renombrado inteligente**: Al hacer F2 o clic para renombrar un archivo, ahora se selecciona automáticamente solo el nombre (sin extensión), facilitando la edición. La extensión permanece visible y se conserva a menos que el usuario la modifique explícitamente.
- **Plugin "Comparar directorios" mejorado**: 
  - Añadido modo recursivo con checkbox para analizar subdirectorios.
  - Nuevo diálogo de opciones antes de la comparación.
  - Mantenida la funcionalidad de selección automática de archivos únicos.
- **Filtro rápido con botón de limpiar**: El campo de filtro rápido ahora muestra un botón de cruz (×) para borrar fácilmente el texto filtrado, mejorando la usabilidad.
- **Integración de diálogos**: Mejorada la integración visual de diálogos en el plugin de comparación.

## Versión 2.7.7 - Marzo 2026

### Optimizaciones de rendimiento de arranque
- **Cache de detección de iPhone**: Implementado sistema de caché para la detección de dispositivos iPhone, reduciendo las llamadas repetidas a la API de Shell de Windows durante el inicio.
- **Reducción de operaciones COM**: Las detecciones de iPhone ahora se cachean por 30 segundos, eliminando múltiples llamadas redundantes durante la inicialización.
- **Control granular de refresco**: El combo de unidades ahora acepta parámetro `force_refresh` para optimizar cuándo se realiza la detección completa.
- **Tiempo de arranque mejorado**: Reducción significativa del tiempo de inicio gracias a la minimización de operaciones costosas de COM/Shell.

## Versión 2.7.8 - Marzo 2026

### Corrección del sistema de caché de iPhone
- **Cache de resultados negativos**: Corregido el sistema de caché para que también almacene resultados negativos (`None`) cuando no se detecta iPhone, evitando llamadas repetidas durante el mismo inicio.
- **Logs de depuración**: Añadidos logs detallados para diagnosticar el uso del caché durante el arranque.
- **Condición de caché mejorada**: La verificación ahora se basa en `_iphone_cache_time > 0` en lugar de `_iphone_cache is not None`, permitiendo reutilizar cache negativo.
- **Reducción adicional de llamadas COM**: Con la corrección, las 4 detecciones de iPhone durante el arranque se reducen a 1 (solo la primera llamada), mejorando aún más el tiempo de inicio.

## Versión 2.7.9 - Marzo 2026

### Optimización de inicialización y diagnóstico de refresco
- **Coordinación de inicialización**: Solo el panel izquierdo realiza detección real de iPhone (`force_refresh=True`), el panel derecho utiliza cache (`force_refresh=False`), reduciendo a una única detección durante el arranque.
- **Parámetro `detect_iphone_on_init`**: Nuevo parámetro en el constructor de `FilePanel` para controlar qué panel realiza la detección inicial.
- **Diagnóstico de botón "refrescar"**: Añadidos logs de depuración en métodos `refresh()` y `refresh_panel()` para identificar problemas de funcionalidad.

## Versión 2.8.3 - Marzo 2026

### Corrección de ordenación de columnas
- **Ordenación por Nombre y Tamaño corregida**: Solucionado el problema donde hacer clic en las cabeceras de columna "Nombre" y "Tamaño" no ordenaba correctamente.
- **Deshabilitado sorting nativo de QTreeView**: Cambiado `view.setSortingEnabled(True)` a `False` para evitar conflictos con el ordenamiento del proxy model.
- **Manejo defensivo mejorado**: Añadida protección adicional contra valores None en comparaciones de ordenación.
- **Debug logging añadido**: Añadidos logs de depuración para facilitar diagnóstico de problemas de ordenación en el futuro.

## Versión 2.8.7 - Marzo 2026

### Mejoras en diálogo de búsqueda
- **Path visible completo**: Corregido el corte de la columna "Ubicación" en resultados de búsqueda
- **Ir al archivo**: Mejorado para que haga scroll y muestre el archivo seleccionado
- **Tiempo de espera**: Aumentado de 50ms a 100ms para evitar race conditions
- **Contiene texto mejorado**: Ahora solo busca en archivos de texto (txt, py, js, html, etc.) y no en binarios
- **Ejemplos actualizados**: Cambiados los ejemplos del patrón de búsqueda
- **Tooltip añadido**: Explicación en "Contiene texto" sobre qué tipos de archivos busca
- **Default corregido**: "Contiene texto" ahora desmarcado por defecto

## Versión 2.8.5 - Marzo 2026

### Limpieza de código
- **Prints de debug convertidos a logging**: Todos los print() restantes en archivos principales ahora usan logging.debug() o logging.error()
- **Archivos limpiados**: toolbar_manager, panel, main_window, fs_utils, app_launcher, bookmarks, settings_dialog, extractor plugin, secure_delete
- **Función huérfana eliminada**: Eliminada `_flash_panel()` que ya no se usaba
- **Imports limpios**: Eliminado import de `weakref` no utilizado

## Versión 2.8.4 - Marzo 2026

### Corrección del sistema de refresco
- **Error "index from wrong model" corregido**: Solucionado el problema donde el refresco manual (F5) y automático causaba errores de Qt por índices de modelo incorrectos.
- **Validación en lessThan()**: Añadida validación para ignorar índices que no pertenecen al proxy model correcto.
- **Código duplicado eliminado**: Eliminada segunda definición de `_update_poll_cache()` que causaba confusión.
- **Refresh simplificado**: El método `refresh()` ahora usa `set_path()` para garantizar consistencia del modelo.
- **Auto-refresco mejorado**: `_do_refresh()` ahora fuerza actualización del layout sin recargar todo el modelo.
- **Fallback de polling**: Mejorado el sistema de polling para paths locales cuando el file watcher falla.
- **Función huérfana eliminada**: Eliminada `_flash_panel()` que ya no se usaba.
- **Imports limpios**: Eliminado import de `weakref` no utilizado.
- **Prints de debug eliminados**: Eliminados print() de debug en refresh y keypress.

## Versión 2.8.1 - Marzo 2026

### Corrección de crash al refrescar
- **Prevención de crash en refresco**: Solucionado el problema donde el botón de refrescar (🔄) causaba un crash inmediato al hacer clic.
- **Referencias débiles en timer**: Implementado uso de weakref para el timer de feedback visual en `_flash_panel()`, evitando crash si el panel es destruido.
- **Protección contra reentrada**: Añadido flag `_refresh_in_progress` para evitar llamadas recursivas al método `refresh()`.
- **Manejo de errores mejorado**: Refactorizado el método `refresh()` con bloques try/finally para garantizar limpieza de estado.
- **Logs mejorados**: Añadidos logs de depuración adicionales para diagnosticar problemas de refresco.

## Versión 2.8.2 - Marzo 2026

### Corrección de ordenación de columnas
- **Ordenación por Nombre y Extensión corregida**: Solucionado el problema donde ordenar por "Nombre" y "Ext" no funcionaba correctamente.
- **Mejoras en lógica de comparación**: Añadido manejo defensivo para valores None y comparaciones de fallback para mantener orden consistente.
- **Ordenación natural mejorada**: La función de ordenación natural ahora usa comparación de strings como fallback cuando las claves son iguales.

### Mejoras completas de plugins
- **Unificación del sistema de plugins**: Eliminados todos los archivos .py duplicados cuando existían versiones en carpetas (13 archivos removidos), resolviendo problemas de duplicación en el PluginManager.
- **Plugin "Buscador de duplicados" mejorado**:
  - Añadida funcionalidad de cancelación con botón "Cancelar" en la UI.
  - Manejo seguro de threads con señalización y timeout de 100ms.
  - Mejorada la experiencia de usuario durante el escaneo de archivos grandes.
- **Plugin "Convertidor de imágenes" mejorado**:
  - Añadido soporte para formatos BMP, TIFF y GIF (además de PNG, JPG, WebP).
  - Mejorada la detección de errores con mensajes informativos.
  - Reporte de éxito/fallo más detallado al finalizar la conversión.
- **Plugin "Multi-renombrado" mejorado**:
  - Añadido soporte para expresiones regulares (regex) en búsqueda y reemplazo.
  - Opción de coincidencia insensible a mayúsculas/minúsculas.
  - Formatos de contador mejorados: 001, 01, 1 (con ceros a la izquierda).
  - Actualizado a versión 1.3.0 con descripción ampliada.
- **Plugin "Organizador" mejorado**:
  - Añadido diálogo de progreso con barra de progreso y contador de archivos procesados.
  - Funcionalidad de cancelación durante la operación.
  - Nueva categoría "Otros" para archivos sin extensión coincidente.
  - Actualizado a versión 1.1.0 con descripción mejorada.
- **Plugin "Compresor" mejorado**:
  - Añadido diálogo de progreso con conteo de archivos para operaciones ZIP.
  - Cancelación soportada durante la compresión.
  - Actualizado a versión 1.0.4 con descripción mejorada.
- **Plugin "Extractor" mejorado**:
  - Añadido diálogo de progreso con funcionalidad de cancelación.
  - Soporte para archivos protegidos con contraseña (RAR/7Z/ZIP).
  - Actualizado a versión 1.0.2 con descripción mejorada.
- **Plugin "Herramienta de hash" mejorado**:
  - Expandidos algoritmos soportados: MD5, SHA1, SHA256, SHA512.
  - Actualizado a versión 1.2.0 con descripción mejorada.
- **Mejoras generales de plugins**:
  - Revisión sistemática de todos los 13 plugins para mejorar manejo de errores.
  - Mejoras de interfaz de usuario y experiencia del usuario.
  - Aumento de robustez y estabilidad del sistema de plugins.
  - Soporte para contraseñas en archivos RAR/7Z a nivel del sistema de archivos comprimidos.

## Versión 2.8.0 - Marzo 2026

### Corrección y mejora del botón de refresco
- **Refresco manual mejorado**: Solucionado el problema donde el botón de refrescar (🔄) no parecía funcionar. Ahora el refresco manual fuerza una actualización más agresiva del modelo de archivos y proporciona feedback visual.
- **Feedback visual**: El panel activo parpadea brevemente al refrescar, confirmando la acción.
- **Forzado de actualización**: El método `refresh()` ahora utiliza `fetchMore()` y `layoutChanged.emit()` para asegurar que el modelo QFileSystemModel actualice la lista de archivos.
- **Logs de diagnóstico**: Añadidos logs adicionales para monitorizar el proceso de refresco.

## Versión 2.7.3 - Marzo 2026

### Corrección de barra de transferencias
- **Progreso basado en bytes**: Reemplazado cálculo de progreso por número de archivos por cálculo basado en bytes copiados.
- **Eliminado throttling**: Removida la limitación de emisión de progreso cada 256KB, ahora se emite en cada cambio de porcentaje.
- **Soporte para directorios**: Implementado cálculo recursivo de tamaño total para copia de directorios.
- **Barra de fondo más estrecha**: Reducido el ancho de la barra de progreso en segundo plano de 250px a 200px.

## Versión 2.6.0 - Marzo 2026

### Copia de Carpertas Sin Delay
- **Copia Inmediata de Carpetas**: Corregido el delay inicial al copiar carpetas grandes. Antes, el sistema escaneaba toda la estructura de directorios antes de copiar ningún archivo. Ahora comienza a copiar inmediatamente mientras descubre los archivos.

## Versión 2.5.5 - Marzo 2026

### Corrección de Renombrado, Auto-Refresco, Layout y Ordenación
- **Renombrado con Puntos en Nombre**: Corregido el problema por el cual al renombrar archivos con un punto en medio del nombre (ej: "mi.archivo.txt"), el sistema trataba incorrectamente lo que había después del punto como extensión. Ahora solo considera como extensión si hay más de un punto en el nombre O si la extensión tiene 2-4 caracteres (extensiones típicas).
- **Auto-Refresco de Archivos**: Implementado sistema de monitoreo automático de cambios en el directorio actual usando `QFileSystemWatcher`. Cuando se añaden, modifican o eliminan archivos desde otro programa, JMComander detecta los cambios y refresca automáticamente la vista.
- **Paneles con Tamaños Iguales**: Corregido el problema por el cual los paneles izquierdo y derecho podían mostrarse con tamaños desproporcionados al iniciar. Ahora se inicializan con el mismo ancho.
- **Ordenación por Defecto**: Los archivos se muestran ordenados por fecha de modificación (más recientes primero), con carpetas siempre primero y archivos después.
- **Aviso de Archivo en Uso**: Al intentar eliminar archivos o carpetas que están siendo usados por otro proceso (como cuando tienes una carpeta abierta en el Explorador de Windows), ahora se muestra un aviso indicando qué archivos no se pueden eliminar y pidiendo que se cierren los programas que los estén usando.

## Versión 2.5.4 - Marzo 2026

### Instancia Única y Mejoras de iPhone
- **Instancia Única**: Implementada funcionalidad para permitir solo una instancia activa de JMComander. Si ya hay una instancia en ejecución y se intenta abrir otra, la ventana existente se traerá al primer plano.
- **Mutex Global**: Uso de mutex global en Windows (`Global\JMComander_SingleInstance_Mutex`) para detección de instancias.
- **Detección Mejorada de iPhone**: 
  - Ahora detecta tanto el almacenamiento interno ("Internal Storage") como otros almacenamiento del iPhone.
  - Muestra el nombre del volumen en el selector de unidades (ej: `[iPhone] iPhone Internal Storage (F:)`).
  - Evita duplicados en el selector de unidades.
- **Logging de Depuración**: Añadidos logs detallados para diagnosticar problemas con la detección y navegación del iPhone.

### Mejora de Sensibilidad de Interfaz
- **Focus Policy ClickFocus**: Cambiado a `ClickFocus` en el panel, TreeView, ListView y archive_browser para mayor sensibilidad al clic.
- **Hover Visual Mejorado**: Añadido efecto visual al pasar el ratón por encima de los elementos con borde y color de highlight.
- **Feedback Visual Reforzado**: Los elementos seleccionados ahora muestran un color más intenso al pasar el ratón encima (`#5A9FE8`).

## Versión 2.5.3 - Marzo 2026

### Mejoras en la Interfaz
- **Breadcrumb Compacto**: Limitado el ancho máximo de cada botón en la barra de ruta superior a 150px y reducido el número máximo de partes visibles a 5 para evitar que la ventana se haga demasiado ancha con rutas largas.

## Versión 2.5.2 - Marzo 2026

### Acceso a Almacenamiento Interno de iPhone
- **Navegación por Shell Namespace**: Implementado acceso al almacenamiento interno de dispositivos iPhone conectados vía USB (MTP). JMComander ahora puede explorar las carpetas del iPhone directamente desde el explorador de archivos.
- **Detección Automática**: El dispositivo iPhone aparece en el selector de unidades con la etiqueta "[iPhone] iPhone" y al seleccionarlo se navega directamente al almacenamiento interno.

## Versión 2.5.1 - Marzo 2026

### Corrección de Geometría de Ventana
- **Detección de Límites de Pantalla**: Al iniciar, JMComander ahora valida que la geometría guardada en config.json esté dentro de los límites de la pantalla actual. Si la ventana estaba configurada en otro ordenador con diferentes monitores o resolución, usará valores por defecto (1200x800) en lugar de mostrar la ventana fuera de la pantalla.

## Versión 2.5.0 - Marzo 2026

### Detección de USB y Diálogo de Conflicto Mejorado
- **Hot-Plug de USB**: Implementada la detección automática de conexión y desconexión de unidades de almacenamiento (USB, discos externos) mediante eventos nativos de Windows (`WM_DEVICECHANGE`). La lista de unidades se actualiza instantáneamente sin necesidad de reiniciar el programa.
- **Diálogo de Conflicto Avanzado**: Al copiar o mover archivos que ya existen, el nuevo diálogo muestra información detallada:
  - Fecha y hora de modificación de ambos archivos.
  - Tamaño de ambos archivos.
  - Indicador visual (color y texto) resaltando cuál de los archivos es más nuevo o si son idénticos.
- **Opciones de sobrescritura inteligente**: Nuevos botones "Sobrescribir si más nuevo" y "Sobrescribir si más antiguo" permiten tomar decisiones automáticas basadas en la fecha de modificación. La opción "Aplicar a todos" funciona con estas nuevas acciones.
- **Detección de dispositivos iPhone**: Mejora en la detección de unidades externas para incluir dispositivos iPhone conectados vía USB (MTP). Aparecerán en la lista de unidades con la etiqueta [iPhone].
- **Robustez**: Pequeño retardo de 1s al detectar nuevas unidades para asegurar que el sistema operativo ha terminado de montar la unidad antes de refrescar la UI.

## Versión 2.4.0 - Febrero 2026

### Quick Look (Vista Previa Rápida)
- **Panel de Vista Previa**: Nuevo panel docksable (derecha o abajo) que muestra vista previa de archivos seleccionados.
- **F3 para Activar/Desactivar**: Atajo de teclado F3 para mostrar/ocultar el panel Quick Look.
- **Soporte de Imágenes**: Previsualización de imágenes (PNG, JPG, JPEG, GIF, BMP, WebP, SVG) con escalado automático.
- **Soporte de Texto**: Vista previa de archivos de texto (txt, md, log, ini, json, py, xml, yml, yaml, csv).
- **Diseño Minimalista**: Widget ligero que solo carga el archivo seleccionado, 0 impacto cuando está oculto.

## Versión 2.3.0 - Febrero 2026

### Barra de Navegación (Breadcrumb) Estilo Altap Salamander
- **Barra de Path Compacta**: Nueva barra de navegación que muestra las carpetas como botones clickeables, estilo Altap Salamander.
- **Navegación Rápida**: Click en cualquier carpeta para navegar directamente a ella.
- **Entrada de Ruta**: Doble click en la barra abre un diálogo para introducir una ruta manualmente.
- **Diseño Compacto**: Cuando la ruta es muy profunda, muestra la unidad, "..." y las últimas carpetas para evitar expandir la ventana.

## Versión 2.2.0 - Febrero 2026

### Operacions en Segon Pla i Llançador d'Aplicacions
- **Operacions en Segon Pla**: Les operacions de copiar, moure i eliminar ara s'executen per defecte en segon pla, mostrant un petit panell de progrés a la part inferior de la finestra. L'usuari pot continuar treballant i cancel·lar l'operació en qualsevol moment.
- **Configuració**: Nova opció a Configuració > General per activar/desactivar les operacions en segon pla.
- **Llançador d'Aplicacions**: Nova barra sota els marcadors que permet executar programes des de JMComander. Ve amb programes per defecte (Notepad, Calculadora, Paint) i l'usuari pot afegir els seus propis executables amb arguments opcionals.
- **Diàleg de Gestió**: Nou diàleg per afegir, editar, eliminar i reordenar les aplicacions del llançador.

### Millores de Vista i Arxius Comprimits
- **Columna Extensió**: Nova columna "Ext" a la vista de detalls que mostra l'extensió dels fitxers separada del nom.
- **Nom Sense Extensió**: El nom del fitxer ara es mostra sense extensió a la columna "Nom", per evitar duplicació.
- **Ordre per Extensió i Tipus**: Nova ordenació per extensió i per categoria de fitxer (compressió, video, àudio, imatge, document, codi, executable).
- **Suport 7z i RAR**: Millorat el sistema d'extracció d'arxius comprimits amb suport per a 7-Zip i RAR mitjançant llibreries i executables del sistema.

## Versión 2.1.2 - Febrero 2026

### Correccions Filtre i Selecció
- **Fix: Filtre Recursiu**: Habilitat `setRecursiveFilteringEnabled(True)` perquè el filtre de cerca busqui a qualsevol lloc del nom del fitxer, no només al principi.
- **Fix: Selecció per Patró amb Filtre Actiu**: Corregit `_select_by_pattern()` per iterar sobre el `source_model` directament, permetent seleccionar fitxers per patró independentment del filtre de cerca ràpida actiu.
- **Fix: Restauració de Foco**: Afegit `processEvents()` i restauració de foco després del diàleg de selecció per patró per garantir que el focus torni correctament al panel.
- **Fix: Mode Solo Carpetes**: Corregit `filterAcceptsRow()` per tenir en compte el flag `folders_only`. Ara el botó "Solo carpetas" funciona correctament filtrant només directoris quan està activat.
- **Millora: Ordre de Carpetes**: Modificat `lessThan()` per mostrar sempre les carpetes primer a la vista de detalls (excepte quan s'ordena explícitament per tipus).
- **Millora: Logging**: Afegit logging informatiu (`logger.info`) per a les tecles `+` i `-` per facilitar el debug.

## Versión 2.1.1 - Febrero 2026

### Correcció d'Errors - Sistema de Filtre i Selecció
- **Fix: EventFilter Duplicat**: Resolt el problema crític on hi havia dos mètodes `eventFilter` a `panel.py`, el qual feia que el segon sobreescrivís el primer i les funcions de Quick Filter i Pattern Selection no funcionessin.
- **Fix: Captura Global de Tecles**: Implementat un `GlobalKeyFilter` a `main.py` que captura les tecles `+`, `-` i caràcters alfanumèrics des de qualsevol lloc de l'aplicació, no només quan el panel té el foco directe.
- **Fix: Protecció del Foco**: Millorada la detecció de foco per evitar que el filtre ràpid s'activi mentre s'escriu a la barra d'adreces (`path_input`) o al propi camp de filtre (`filter_input`).
- **Refactorització**: Creat el mètode `_trigger_pattern_selection()` a `FilePanel` per evitar duplicació de codi entre l'eventFilter local i el global.

## Versión 2.1.0 - Febrero 2026

### Productivitat Avançada - Filtre i Selecció Ràpida
- **Filtre Ràpid (As-You-Type)**: Nou camp de filtre a la barra de navegació que filtra fitxers en temps real mentre escrius. S'activa automàticament prement qualsevol tecla alfanumèrica i es tanca amb ESC.
- **Selecció per Patró (+/-)**: Implementades les dreceres clàssiques de Total Commander:
  - Tecla `+`: Obre diàleg per seleccionar fitxers per patró (ex: `*.jpg`)
  - Tecla `-`: Obre diàleg per deseleccionar fitxers per patró
  - Funciona tant en carpetes normals com dins d'arxius comprimits
- **Baix Impacte**: Ambdues funcions utilitzen el `QSortFilterProxyModel` existent, sense penalitzar l'arrancada ni el rendiment.

## Versión 2.0.1 - Febrero 2026

### Unificación de Menús Contextuales
- **Crea en el Menú Contextual**: Integrat el submenú "Crea (JMComander)" directament al menú del botó dret sobre el fons de la carpeta. Això assegura que les mateixes opcions ràpides del botó estiguin disponibles a qualsevol lloc.
- **Sincronització de Lògica**: Connectada la creació de documents des del menú natiu amb el motor de plantilles del JMComander, garantint consistència total.

## Versión 2.0.0 - Febrero 2026

### Gran Actualización de UI y Experiencia de Usuario
- **Compactación Final**: Selector d'unitats ajustat a 80 píxels per a una barra de navegació més neta.
- **Navegació Superior**: Afegit botó dedicat per pujar de nivell (fletxa amunt) amb suport per a icones SVG.
- **Creació Rápida**: Nou botó "Crea" que s'integra amb el menú natiu de Windows (ShellNew) per crear documents a l'instant.
- **Sincronització Intel·ligent**: El selector de disc ara es manté sincronitzat amb la ruta activa independentment de com es navegui.

## Versión 1.9.9 - Febrero 2026

### Ajustes de UI
- **Redimensionado de UI**: Ajustada l'amplada del selector d'unitats a 95 píxels per aprofitar millor l'espai sense tallar les etiquetes descriptives.

## Versión 1.9.8 - Febrero 2026

### Sincronización de Unidades
- **Fix Sincronización**: Corregido el error donde el selector de unidades no se actualizaba al cambiar de disco (ej: de C: a D:).
- **Normalización de Rutas**: Implementada la normalización de barras (`/` vs `\`) para asegurar que el selector identifique correctamente la unidad activa independientemente del formato de la ruta.

## Versión 1.9.6 - Febrero 2026

### Mejoras Visuales y de Compatibilidad
- **Icono de Creación**: Corregida la carga de `creation.svg` en entornos empaquetados (PyInstaller) mediante el uso de `sys._MEIPASS`.
- **Robustez de Rutas**: Implementado un sistema dual de localización de assets que funciona tanto en desarrollo como en el ejecutable final.
- **Botón Crea Mejorado**: Refinado el estilo del botón para asegurar que el icono SVG se visualice correctamente junto al texto.

## Versión 1.9.5 - Febrero 2026

### Botón de Creación Rápida
- **Nuevo Botón "Crea"**: Añadido un botón en la barra de navegación para crear carpetas y documentos rápidamente.
- **Integración con Windows (ShellNew)**: El menú desplegable escanea el registro de Windows para ofrecer los mismos tipos de archivos que el menú "Nuevo" nativo (Word, Excel, Text, etc.).
- **Nombres Dinámicos**: Implementada la resolución de nombres amigables (ej: "Document de Microsoft Word" en lugar de ".docx") consultando las clases de registro.
- **Creación Inteligente**: Soporte para la creación de archivos con extensión automática y refresco inmediato del panel con foco en el nuevo elemento.

## Versión 1.9.4 - Febrero 2026

### Distinción de Tipos de Unidades
- **Detección de Hardware**: Implementada la identificación de tipos de disco (Local, USB, Xarxa, CD) mediante la API `GetDriveType` de Windows.
- **UI Desplegable Mejorada**: El selector de unidades ahora muestra prefijos descriptivos (`[Local]`, `[USB]`, `[Xarxa]`) facilitando la identificación rápida de dispositivos conectados.
- **Estabilidad de Datos**: Migrado el selector de unidades a un sistema basado en `itemData` para asegurar que las etiquetas visuales no interfieran con las rutas de navegación.
- **Ajuste de Diseño**: Incrementado el ancho del selector de unidades para acomodar las nuevas etiquetas sin truncar texto.

## Versión 1.9.1 - Febrero 2026

### Mejoras en Navegación y Operaciones de Archivos Comprimidos
- **Navegación Superior Inteligente**: Corregida la función "Subir" (Backspace) dentro de archivos comprimidos. Ahora permite navegar por subcarpetas internas y solo sale del archivo cuando se está en la raíz del mismo.
- **Foco y Selección Corregidos**: Habilitada la emisión de foco al interactuar con el explorador de archivos comprimidos, asegurando que las teclas de función (F5, F6) detecten el panel correcto.
- **Estilo Unificado**: Aplicado el mismo estilo visual de selección a la vista de archivos comprimidos para una experiencia de usuario consistente.
- **Robustez en Operaciones**: Asegurada la captura correcta de rutas temporales para permitir copiar/mover archivos desde el interior de comprimidos.

## Versión 1.9.0 - Febrero 2026

### Corrección de Detección de Menú de Fondo
- **Fix Crítico en FilePanel**: Eliminada la restricción que impedía disparar el menú contextual al hacer clic en áreas vacías del panel.
- **Activación de Menú de Fondo**: Ahora el sistema identifica correctamente cuando el usuario desea interactuar con la carpeta contenedora.

## Versión 1.8.7 - Febrero 2026

### Rearquitectura de Menús Nativos (Estrategia de Máxima Estabilidad)
- **Eliminación de Subclassing de Qt**: Eliminado el Hook de la ventana principal de Qt para evitar crashes de memoria.
- **Menu Host Window**: Implementada una ventana Win32 invisible dedicada a la gestión de mensajes del Shell.
- **Firma de Invocación 64-bit**: Actualizada la estructura `InvokeCommand` a la firma estable de 8 elementos para Windows 11.

## Versión 1.8.6 - Febrero 2026
...
