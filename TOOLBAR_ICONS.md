# Documentación de Iconos del Toolbar - JMComander

## Información General

- **Tema de iconos**: Material Design Icons (MDI) por defecto
- **Ubicación**: `src/assets/icons/`
- **Formato**: SVG
- **Fallback**: Si no se encuentra el icono, se genera uno con la inicial

---

## Lista Completa de Iconos

### Navegación

| # | Nombre | Icono SVG | Atajo | Descripción |
|---|--------|-----------|-------|-------------|
| 1 | **Subir** | `mdi-arrow-up.svg` | Backspace | Sube al directorio padre |
| 2 | **Enrere** | `mdi-arrow-left.svg` | Alt+← | Navega a la carpeta anterior (historial) |
| 3 | **Endavant** | `mdi-arrow-right.svg` | Alt+→ | Navega a la carpeta siguiente (historial) |
| 4 | **Raíz** | `mdi-harddisk.svg` | - | Navega a la raíz del sistema (C:\) |
| 5 | **Usuario** | `mdi-home.svg` | - | Navega al directorio personal del usuario |

### Vista y Actualización

| # | Nombre | Icono SVG | Atajo | Descripción |
|---|--------|-----------|-------|-------------|
| 6 | **Refrescar** | `mdi-refresh.svg` | F5 | Actualiza la lista de archivos |
| 7 | **Buscar** | `mdi-magnify.svg` | Alt+F7 | Abre el diálogo de búsqueda |

### Selección

| # | Nombre | Icono SVG | Atajo | Descripción |
|---|--------|-----------|-------|-------------|
| 6 | **Sel. Todo** | `mdi-select-all.svg` | Ctrl+A | Selecciona todos los elementos |
| 7 | **Invertir** | `mdi-select-inverse.svg` | Ctrl+I | Invierte la selección actual |
| 8 | **Deselec.** | `mdi-selection-off.svg` | Ctrl+Shift+A | Deselecciona todo |
| 9 | **Solo Carpetas** | `mdi-folder.svg` | Ctrl+Shift+F | Alterna vista solo carpetas/archivos |

### Operaciones con Archivos

| # | Nombre | Icono SVG | Atajo | Descripción |
|---|--------|-----------|-------|-------------|
| 10 | **Nueva Carpeta** | `mdi-folder-plus.svg` | F7 | Crea una carpeta nueva |
| 11 | **Copiar Ruta** | `mdi-content-copy-outline.svg` | - | Copia la ruta al portapapeles |
| 12 | **Ir a** | `mdi-folder-open.svg` | Ctrl+G | Navega a una ruta específica |
| 13 | **Duplicar** | `mdi-content-duplicate.svg` | Ctrl+D | Duplica archivos/carpetas seleccionados |

### Terminal y Consola

| # | Nombre | Icono SVG | Atajo | Descripción |
|---|--------|-----------|-------|-------------|
| 14 | **Terminal** | `mdi-terminal-outline.svg` | - | Abre CMD en la ruta actual |
| 15 | **PowerShell** | `mdi-console.svg` | - | Abre PowerShell en la ruta actual |

### Pestanyes de Carpeta

| # | Nombre | Icono SVG | Atajo | Descripción |
|---|--------|-----------|-------|-------------|
| 16 | **Nova pestanya** | `mdi-tab-plus.svg` | Ctrl+T | Obre una nova pestanya al panell actiu |
| 17 | **Tancar pestanya** | `mdi-tab-remove.svg` | Ctrl+W | Tanca la pestanya actual del panell |

### Directoris Freqüents i Sincronització

| # | Nombre | Icono SVG | Atajo | Descripción |
|---|--------|-----------|-------|-------------|
| 18 | **Hotlist** | `mdi-folder-star.svg` | Ctrl+D | Obre la llista de directoris freqüents |
| 19 | **Sync Dirs** | `mdi-sync.svg` | - | Compara i sincronitza els dos panells |

### Filtre per Extensió

| # | Nombre | Icono SVG | Atajo | Descripción |
|---|--------|-----------|-------|-------------|
| 20 | **\*.ext** | (botó text) | - | Filtra fitxers per categoria d'extensió (Documents, Imatges, Vídeo, Àudio, Arxius, Codi) |

### Gestión de Paneles

| # | Nombre | Icono SVG | Atajo | Descripción |
|---|--------|-----------|-------|-------------|
| 21 | **Intercambiar** | `mdi-swap-horizontal.svg` | Ctrl+U | Intercambia las rutas de ambos paneles |
| 22 | **Igualar** | `mdi-arrow-right-bold.svg` | - | Copia ruta del panel activo al inactivo |
| 23 | **IgualarInv** | `mdi-arrow-left-bold.svg` | Ctrl+Alt+Left | Copia ruta del panel inactivo al activo |
| 24 | **Explorer** | `mdi-monitor.svg` | - | Abre la ruta en el Explorador de Windows |

### Menús Desplegables

| # | Nombre | Icono SVG | Tipo | Descripción |
|---|--------|-----------|------|-------------|
| 25 | **Vista** | `mdi-view-list.svg` | Menu | Cambia modo de visualización |
| 26 | **Recientes** | `mdi-history.svg` | Menu | Historial de carpetas visitadas |
| 27 | **Marcadores** | `mdi-bookmark.svg` | Menu | Gestión de marcadores favoritos |
| 28 | **Plugins** | `mdi-puzzle.svg` | Menu | Herramientas y plugins adicionales |

### Sistema

| # | Nombre | Icono SVG | Atajo | Descripción |
|---|--------|-----------|-------|-------------|
| 29 | **Configuración** | `mdi-cog.svg` | - | Abre el diálogo de configuración |
| 30 | **Info** | `mdi-information.svg` | - | Muestra información del programa |

---

## Alias de Iconos (Phosphor Theme)

Cuando se usa el tema **Phosphor**, los iconos MDI se mapean a nombres alternativos:

| MDI Original | Phosphor Alias |
|-------------|-----------------|
| `mdi-arrow-up` | `arrow-up` |
| `mdi-arrow-left` | `arrow-left` |
| `mdi-arrow-right` | `arrow-right` |
| `mdi-harddisk` | `folder` |
| `mdi-home` | `home` |
| `mdi-refresh` | `refresh` |
| `mdi-magnify` | `search` |
| `mdi-tab-plus` | `tab-plus` |
| `mdi-tab-remove` | `tab-remove` |
| `mdi-folder-star` | `folder-star` |
| `mdi-sync` | `sync` |
| `mdi-swap-horizontal` | `swap` |
| `mdi-arrow-right-bold` | `arrow-right` |
| `mdi-arrow-left-bold` | `arrow-left` |
| `mdi-monitor` | `monitor` |
| `mdi-terminal-outline` | `terminal` |
| `mdi-console` | `terminal` |
| `mdi-content-duplicate` | `files` |
| `mdi-folder-open` | `folder` |
| `mdi-select-all` | `select-all` |
| `mdi-content-copy-outline` | `copy` |
| `mdi-folder-plus-outline` | `folder-plus` |
| `mdi-select-inverse` | `select-all` |
| `mdi-selection-off` | `select-none` |
| `mdi-information` | `info` |
| `mdi-puzzle` | `plugins` |
| `mdi-bookmark` | `bookmark` |

---

## Atajos de Teclado Completos

| Tecla | Acción |
|-------|---------|
| Backspace | Subir un nivel |
| Alt+← | Enrere (historial de carpetas) |
| Alt+→ | Endavant (historial de carpetas) |
| F5 | Refrescar |
| Alt+F7 | Buscar |
| Ctrl+A | Seleccionar todo |
| Ctrl+I | Invertir selección |
| Ctrl+Shift+A | Deseleccionar todo |
| Ctrl+Shift+F | Solo carpetas |
| F7 | Nueva carpeta |
| Ctrl+G | Ir a ruta |
| Ctrl+T | Nueva pestanya |
| Ctrl+W | Cerrar pestanya |
| Ctrl+D | Directorios frecuentes (Hotlist) |
| Ctrl+U | Intercambiar paneles |
| Ctrl+Alt+Left | Igualar inverso |
| F2 | Renombrar |
| F3 | Ver archivo |
| F4 | Editar archivo |
| F5 | Copiar |
| F6 | Mover |
| F7 | Nueva carpeta |
| F8 | Borrar |
| F9 | Duplicar |

---

## Barra de Funciones (F2-F9)

La barra inferior contiene botones adicionales con funciones rápidas:

| Botón | Función | Atajo Teclado |
|-------|----------|---------------|
| F2 Renombrar | `rename_item()` | F2 |
| F3 Ver | `view_file()` | F3 |
| F4 Editar | `edit_file()` | F4 |
| F5 Copiar | `copy_files()` | F5 |
| F6 Mover | `move_files()` | F6 |
| F7 Carpeta | `create_folder()` | F7 |
| F8 Borrar | `delete_files()` | F8 |
| F9 Duplicar | `duplicate_selected()` | F9 |

---

## Notas Técnicas

### Carga de Iconos
- Los iconos se buscan en el siguiente orden:
  1. `src/assets/icons/[nombre].svg`
  2. `_internal/src/assets/icons/[nombre].svg`
  3. Generar fallback con iniciales

### Formato SVG
- Los iconos son archivos SVG vectoriales
- Se escalan sin pérdida de calidad
- Compatibles con Material Design Icons

### Fallback
- Si no se encuentra un icono SVG, se genera uno dinámicamente
- Color de respaldo: `#9E9E9E` (gris neutro)
- Letra inicial del texto del botón

---

## Actualizado
- **Fecha**: 2026-07-29
- **Versión JMComander**: 6.8.3
