# Scripts de JMComander

Esta carpeta contiene los scripts necesarios para compilar, verificar y distribuir JMComander.

## Build Principal

### `build.bat` (raiz del proyecto) ⚡
**Build rápido automático (RECOMENDADO)**

- **Que hace**: Detecta Conda, limpia builds, compila con PyInstaller, copia DLLs
- **Característica**: Todo automático, sin pausas
- **Uso**: Para desarrollo diario y builds rápidos
- **Tiempo**: 3-5 minutos

---

## Scripts Auxiliares

### `scripts\3_copy_qt_dlls.bat` 📋
**Copia DLLs de Qt6 desde entorno Conda**

- **Que hace**: Copia todas las DLLs necesarias a `_internal/`
- **Uso**: Solo si hay errores de "ImportError: could not import module 'PySide6.QtGui'"
- **Nota**: El `build.bat` ya lo hace automáticamente

### `scripts\5_lanzar_final.bat` 🚀
**Ejecutar JMComander**

- **Que hace**: Busca JMComander.exe y lo ejecuta
- **Uso**: Para probar la aplicación rápidamente sin verificaciones

### `scripts\6_crear_distribucion.bat` 📦
**Crear paquete ZIP para distribuir**

- **Que hace**: Verifica el build, crea ZIP en `releases/` con fecha en el nombre
- **Uso**: Cuando quieres distribuir la aplicación a usuarios finales
- **Salida**: `releases/JMComander_v1.0_YYYYMMDD.zip`

### `scripts\7_verificar_iconos.bat` 🔍
**Verifica iconos en el build**

- **Que hace**: Comprueba que los iconos SVG existen y están en el bundle
- **Uso**: Si hay problemas visuales con los iconos

### `scripts\8_cambiar_tema.bat` 🎨
**Selector de tema de iconos**

- **Que hace**: Cambia entre Material Design y Phosphor Icons
- **Uso**: Antes de compilar para elegir el estilo visual

### `scripts\9_compilar_ambos_auto.bat` 🔄
**Compila ambas versiones de iconos**

- **Que hace**: Compila JMComander-Material.exe y JMComander-Phosphor.exe
- **Uso**: Para distribuir ambas variantes visuales

---

## Scripts de Verificación

### `scripts\verify_automatica.py` 🧪
**Verificación automatizada (82 tests)**

- **Que hace**: Verifica estructura, imports, funcionalidades y plugins
- **Uso**: Antes de cada release para confirmar que nada se ha roto
- **Ejecución**: `python scripts\verify_automatica.py`

---

## Flujo de Trabajo Recomendado

### Desarrollo diario:
```batch
build.bat
```

### Build de producción:
```batch
build.bat
python scripts\verify_automatica.py
```

### Distribución:
```batch
build.bat
python scripts\verify_automatica.py
scripts\6_crear_distribucion.bat
```

## Guía Rápida para Nuevos Usuarios

**¿Primera vez?**
1. Ejecuta: `build.bat`
2. Espera 3-5 minutos
3. ¡Listo!

**¿Error con las DLLs?**
1. Ejecuta: `scripts\3_copy_qt_dlls.bat`
2. Vuelve a compilar si es necesario

**¿Quieres distribuir?**
1. Ejecuta: `scripts\6_crear_distribucion.bat`
2. El ZIP estará en la carpeta `releases/`

## Requisitos

- Windows 10/11
- Conda con entorno `jm_pyside_313`
- Python 3.13
- PySide6 instalado en el entorno

## Estructura de Salida

```
dist/
└── JMComander/
    ├── JMComander.exe          ← Ejecutable principal
    ├── _internal/              ← DLLs y dependencias
    │   ├── Qt6Core.dll
    │   ├── Qt6Gui.dll
    │   ├── PySide6/
    │   └── ...
    └── src/
        └── plugins/            ← Plugins de la aplicación
```

## Solución de Problemas

### Error: "ImportError: could not import module 'PySide6.QtGui'"
**Solución**: Ejecutar `scripts\3_copy_qt_dlls.bat`

### Error: "No se encuentra JMComander.exe"
**Solución**: Ejecutar primero `build.bat`

### Error: "DLL faltante"
**Solución**:
1. Verificar entorno Conda: `conda activate jm_pyside_313`
2. Ejecutar `scripts\3_copy_qt_dlls.bat`
3. Recompilar si es necesario

## Notas

- Todos los builds son para **Windows** usando **PySide6**
- La distribución se hace como **ZIP** (no requiere instalación)
- Las DLLs de Qt6 se incluyen automáticamente en `_internal/`
- El usuario final solo necesita descomprimir y ejecutar

## Portabilidad (Trabajar en Otros Ordenadores)

**Los scripts usan rutas relativas y detectan Conda automáticamente.**

Esto significa que funcionan en cualquier ordenador donde:
1. El proyecto esté clonado/copiado
2. Conda esté instalado y en el PATH
3. El entorno `jm_pyside_312` exista

### Detección Automática de Conda

Los scripts detectan automáticamente dónde está instalado Conda usando:
```batch
where conda
conda info --base
```

**Si esto falla** (Conda no está en el PATH), verás este error:
```
[ERROR] No se pudo detectar la instalacion de Conda.
```

### Solución: Archivo CONFIG.bat

Si Conda está en una ubicación no estándar, edita `scripts\CONFIG.bat`:

```batch
REM Descomenta y modifica esta linea:
set CONDA_BASE=C:\Tu\Ruta\Conda
```

También puedes personalizar:
- `CONDA_ENV`: Nombre del entorno (por defecto: jm_pyside_312)
- `EXE_NAME`: Nombre del ejecutable (por defecto: JMComander)
- `VERSION`: Versión para el ZIP (por defecto: 1.0)

### ¿Por qué Rutas Relativas?

Las rutas como `%~dp0..` significan:
- `%~dp0`: Carpeta donde está el script
- `..`: Subir un nivel (directorio raíz del proyecto)

Esto permite mover la carpeta del proyecto a cualquier lugar:
```
C:\Users\Juan\Proyectos\JMcomander\
D:\Trabajo\JMcomander\
C:\Program Files\JMcomander\
```

Y todo seguirá funcionando igual.
