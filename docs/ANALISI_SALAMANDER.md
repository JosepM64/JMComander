# Anàlisi: Open Salamander → JMComander

**Data:** 05/08/2026  
**Objectiu:** Identificar millores transferibles de Salamander v5.0 a JMComander mantenint SoC i simplicitat.

---

## 1. Copy/Move — Anàlisi Comparativa

### 1.1 Arquitectura JMComander (actual)

```
User (F5/F6) → ActionContext → OperationEngine (singleton)
  → QThreadPool(max=2) → CopyJob / MoveJob (QRunnable)
    → fs_utils.copytree_with_progress (ThreadPoolExecutor intern, 2 workers)
    → JobSignals (Qt signals cross-thread)
```

**Fitxers clau:**
- `src/core/engine.py` — OperationEngine, queue_copy/queue_move, start_job
- `src/core/jobs.py` — BaseJob, CopyJob, MoveJob, ConflictMixin
- `src/core/fs_utils.py` — copytree_with_progress, get_tree_size
- `src/ui/progress_dialog.py` — ProgressDialog (minimitzable)
- `src/ui/conflict_dialog.py` — ConflictDialog (3 opcions: Tot/Antics/Cancel·lar)

**Limitacions identificades:**
1. Sense velocitat/ETA (només % i nom d'arxiu)
2. Sense pause/resume
3. Sense cua d'operacions visual
4. MoveJob no gestiona bé errors parcials
5. get_tree_size timeout 1.5s → total_size=0 en USB lents
6. No detecció de symlinks abans de copiar

### 1.2 Arquitectura Salamander (extraïda del binari)

**Classes C++ identificades:**
- `COperationsQueue` — Cua amb AddOperation/OperationEnded/SetPaused/AutoPauseOperation
- `CProgressDialog` + `CProgressDlgArray` — Gestió de múltiples diàlegs de progrés
- `CProgressSpeedMeter` / `CTransferSpeedMeter` — Mesura de velocitat real
- `CSetSpeedLimDialog` — Límit de velocitat configurable (1 B/s a 4 GB/s)
- `CCopyMoveDialog` / `CCopyMoveMoreDialog` — Diàleg de copia/moviment
- `COverwriteDlg` — Overwrite/Skip/Overwrite Older
- `CHiddenOrSystemDlg` — Confirmació per fitxers de sistema
- `CConfirmADSLossDlg` — Pèrdua d'ADS (Alternate Data Streams)
- `CConfirmEncryptionLossDlg` — Pèrdua d'encryptació EFS
- `CConfirmLinkTgtCopyDlg` — Seguir/saltar symlinks
- `CErrorCopyingDirTimeDlg` / `CErrorCopyingPermissionsDlg` — Errors específics

**Funcionalitats destacades:**
| Feature | Evidència |
|---------|-----------|
| Cua d'operacions | `COperationsQueue::AddOperation/OperationEnded/SetPaused` |
| Pause/Resume | `&Pause`, `paused`, `SetPaused()` |
| Velocitat | `speed: %s/s` + `speed: %s/s (limit: %s/s)` |
| Límit velocitat | `CSetSpeedLimDialog`, 1 B/s a 4 GB/s |
| Múltiples progress dialogs | `CProgressDlgArray` gestiona N dialogs simultanis |
| Async network copy | `UseAsyncCopyAlg` — algoritme asíncron Win7+ |
| Integració plugins | `CopyOrMoveFromDiskToFS` / `CopyOrMoveFromFS` |
| Drag & Drop OLE | `CFakeDragDropDataObject`, `CImpDropTarget` |
| NetWare fast move | `NetwareFastDirMove` per directoris |

---

## 2. Altres Millores Transferibles

### 2.1 Color Highlighting Rules
**Salamander:** Regles per màscara amb prioritat (`*.pdf → blau`, `*.bak → gris`).  
**JMComander:** Cap suport.  
**Proposta:** Afegir `color_rules` al config.json + `ForegroundRole`/`BackgroundRole` al model.

### 2.2 Internal Viewer
**Salamander:** Viewer intern amb detecció d'encoding (UTF-8/16/32), modes hex/text, salts CR/LF.  
**JMComander:** quick_look bàsic (text + imatges).  
**Proposta:** Ampliar quick_look_handler amb chardet, mode hex, més tipus.

### 2.3 Export File List
**Salamander:** Exportar contingut del panell a fitxer.  
**JMComander:** Cap suport.  
**Proposta:** Nova acció `export_file_list` al ActionRegistry.

### 2.4 Batch Renamer amb variables
**Salamander:** Sistema de variables `$(Name)`, `$(Ext)`, `$(Counter:1:1)`, `$(Date:yyyy-MM-dd)`, regex backreferences.  
**JMComander:** multi_rename plugin existent (find/replace, prefix/suffix, counter).  
**Proposta:** Afegir sistema de variables al multi_rename existent.

---

## 3. Pla d'Implementació Proposat

### Fase 1: Velocitat al Progress Dialog (Impacte ALT, Esforç BAIX)
**On:** `src/core/jobs.py` + `src/ui/progress_dialog.py`

**Canvis:**
- `CopyJob`: afegir acumulador `bytes_copied` + timer 500ms per calcular `speed = delta_bytes / delta_time`
- Nou signal `speed(float)` a `JobSignals`
- `progress_dialog.py`: mostrar `2.3 MB/s` a l'info label

### Fase 2: Pause/Resume (Impacte ALT, Esforç MITJÀ)
**On:** `src/core/jobs.py` + `src/core/engine.py` + `src/ui/progress_dialog.py`

**Canvis:**
- `BaseJob`: afegir `_pause_event = threading.Event()` + flag `is_paused`
- `CopyJob.run()`: al buffer copy loop, `if self._pause_event.is_set(): self._pause_event.wait()`
- `OperationEngine`: `pause_job(job_id)` / `resume_job(job_id)`
- `progress_dialog.py`: botó Pause/Resume

### Fase 3: Cua d'Operacions (Impacte ALT, Esforç MITJÀ-ALT)
**On:** `src/core/engine.py` (nou `OperationQueue`)

**Canvis:**
- `OperationQueue` amb `deque` de pending jobs
- Quan un job acaba → llança el següent automàticament
- UI mostra llista d'operacions pendents (mini-llista al progress dialog)

### Fase 4: Color Highlighting (Impacte ALT, Esforç BAIX)
**On:** `src/core/config.py` + `src/ui/file_system_model.py` + `src/ui/panel.py`

**Canvis:**
- Config: nou dict `"color_rules": [{"mask": "*.pdf", "color": "#2196F3"}, ...]`
- Model: handlers per `ForegroundRole`/`BackgroundRole` al `data()`
- Panel: `ColorDelegate(QStyledItemDelegate)` si hi ha regles definides

### Fase 5: Export File List (Impacte MITJÀ, Esforç BAIX)
**On:** `src/core/actions.py`

**Canvis:**
- Nova acció `export_file_list` registrada al ActionRegistry
- Handler que genera .txt/.csv amb Nom, Mida, Data, Hora, Tipus

---

## 4. Referències

- **Open Salamander:** `C:\Mega\JOSEP\_swing\jm varis\_POST FEINA\Feines\Programació\ASalamander` v5.0.0.183 (x64)
- **JMComander:** `C:\Mega\JOSEP\_swing\jm varis\_POST FEINA\Feines\Programació\JMcomander` v6.8.3+
- **Font Salamander:** `D:\Documents\Programació\salamander\src\vcxproj\` (compilat amb MSVC v143)
- **Llicència:** Apache 2.0 (JMComander), GPLv2+ (Open Salamander)
